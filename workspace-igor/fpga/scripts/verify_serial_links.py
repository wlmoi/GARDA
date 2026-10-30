"""Record STM USB traffic and verify FPGA JP7 independently; never relay to STM."""
import argparse
import concurrent.futures
import datetime
import importlib.util
import json
import time
from pathlib import Path
import serial
from serial.tools import list_ports

ROOT=Path(__file__).resolve().parents[1]

def crc8(data):
    c=0
    for b in data:
        c^=b
        for _ in range(8):c=(c>>1)^(0x8c if c&1 else 0)
    return c

def packets(data):
    """Resynchronize on AA55; accept only complete CRC-valid STM frames."""
    frames=[];bad=0;i=0
    while i+4<=len(data):
        if data[i:i+2]!=b'\xaa\x55':i+=1;continue
        end=i+5+data[i+3]
        if end>len(data):i+=1;continue
        frame=data[i:end]
        if crc8(frame[2:-1])!=frame[-1]:bad+=1;i+=1;continue
        frames.append({'offset':i,'type':frame[2],'length':frame[3],
                       'payload_hex':frame[4:-1].hex(' '),'frame_hex':frame.hex(' ')})
        i=end
    return frames,bad

def capture_stm(port,bauds,seconds,directory):
    results=[]
    for baud in bauds:
        data=bytearray();chunks=[];error=None
        try:
            # No application bytes are transmitted to STM. Set modem outputs
            # before opening to avoid intentional DTR/RTS reset pulses.
            dev=serial.Serial(baudrate=baud,timeout=.05,xonxoff=False,rtscts=False,dsrdtr=False)
            dev.dtr=False;dev.rts=False;dev.port=port
            with dev:
                start=time.monotonic()
                while time.monotonic()-start<seconds:
                    block=dev.read(min(max(dev.in_waiting,1),4096))
                    if block:
                        chunks.append({'elapsed_s':time.monotonic()-start,'rx_hex':block.hex(' ')})
                        data.extend(block)
        except (OSError,serial.SerialException) as exc:error=str(exc)
        frames,bad=packets(data)
        (directory/f'stm_{baud}.bin').write_bytes(data)
        (directory/f'stm_{baud}_chunks.json').write_text(json.dumps(chunks,indent=2))
        result={'port':port,'baud':baud,'bytes_received':len(data),'crc_valid_frames':len(frames),
                'crc_bad_candidates':bad,'first_96_bytes_hex':data[:96].hex(' '),
                'ascii_preview':''.join(chr(b) if 32<=b<127 else '.' for b in data[:160]),
                'frames':frames,'error':error,'application_tx_bytes':0}
        results.append(result)
        print(f'STM {port} {baud}: RX={len(data)} bytes, AA55 CRC-valid={len(frames)}, error={error}',flush=True)
    return results

def test_fpga(port,baud,directory):
    path=ROOT.parent/'src/igor_pipeline/scripts/uart_test.py'
    spec=importlib.util.spec_from_file_location('igor_reference_uart',path)
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    request=reference.build_sensor_packet_q88(reference.DEFAULT_OBS_Q88)
    result={'port':port,'baud':baud,'tx_hex':request.hex(' '),'expected_q88':[-46,60,34],'passed':False}
    received=bytearray()
    try:
        with serial.Serial(port,baud,timeout=.02,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False) as dev:
            dev.reset_input_buffer();start=time.monotonic()
            result['tx_bytes']=dev.write(request);dev.flush()
            deadline=time.monotonic()+1
            while time.monotonic()<deadline:
                received.extend(dev.read(min(max(dev.in_waiting,1),4096)))
                offset=received.find(reference.RESPONSE_HEADER)
                if offset>=0 and len(received)>=offset+11:
                    response=reference.parse_response_packet(bytes(received[offset:offset+11]))
                    result.update(response,rtt_ms=(time.monotonic()-start)*1000)
                    result['passed']=response['q8_8_results']==[-46,60,34]
                    break
    except (OSError,serial.SerialException,ValueError) as exc:result['error']=str(exc)
    result['all_rx_hex']=received.hex(' ');result['rx_bytes']=len(received)
    (directory/'fpga_rx.bin').write_bytes(received)
    print(f'FPGA {port} {baud}: TX={result.get("tx_bytes",0)} RX={len(received)} PASS={result["passed"]}',flush=True)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stm-port',default='COM9');parser.add_argument('--fpga-port',default='COM12')
    parser.add_argument('--stm-bauds',default='1000000,115200,921600,9600')
    parser.add_argument('--seconds',type=float,default=2)
    parser.add_argument('--fpga-baud',type=int,default=921600)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:
        body=bytes.fromhex('10 03 aa 55 00');frame=b'\xaa\x55'+body+bytes([crc8(body)])
        frames,bad=packets(b'noise'+frame+frame[:-1]+bytes([frame[-1]^1])+frame[:3])
        assert crc8(b'123456789')==0xa1 and len(frames)==1 and bad>=1
        print('PASS: CRC vector, noise resync, embedded header, bad CRC and incomplete tail');return 0
    if args.stm_port.upper()==args.fpga_port.upper():parser.error('STM and FPGA ports must be distinct')
    if not 0<args.seconds<=30:parser.error('--seconds must be in (0,30]')
    bauds=[int(x) for x in args.stm_bauds.split(',')]
    if len(bauds)>8 or any(x<=0 for x in bauds):parser.error('Provide 1..8 positive STM baud rates')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory=ROOT/'evidence/serial_links'/stamp;directory.mkdir(parents=True)
    inventory=[{'port':p.device,'description':p.description,'hwid':p.hwid} for p in list_ports.comports()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        stm=pool.submit(capture_stm,args.stm_port,bauds,args.seconds,directory)
        fpga=pool.submit(test_fpga,args.fpga_port,args.fpga_baud,directory)
        result={'utc':stamp,'ports':inventory,'stm':stm.result(),'fpga':fpga.result(),
                'forwarding_enabled':False,'interpretation':'STM USB capture and FPGA inference are separate tests; no STM payload is mapped to neural observations.'}
    (directory/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'Evidence: {directory}',flush=True)
    return 0 if result['fpga']['passed'] and any(x['crc_valid_frames'] for x in result['stm']) else 1

if __name__=='__main__':raise SystemExit(main())
