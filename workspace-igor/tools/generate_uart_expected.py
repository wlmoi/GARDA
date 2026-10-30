"""Generate the exact UART oracle for uart_test.py's fixed observation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/uart_expected'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    OUT.mkdir(exist_ok=True)
    uart=load('uart',ROOT/'src/igor_pipeline/scripts/uart_test.py')
    reference=load('reference',ROOT/'fpga/verification/src_policy/run.py')
    model_path=ROOT/'src/igor_navigation/igor_navigation/weights/model_weights.json'
    model=json.loads(model_path.read_text())
    q={}
    for name in ('w1','b1','w2','b2','w3','b3'):
        q[name]=[min(32767,max(-32768,round(float(v)*256))) for v in reference.flatten(model[name])]
    obs=[0.8]*64+[0.0]*10
    packet=uart.build_sensor_packet(0,obs)
    quantized=list(struct.unpack('<74h',packet[4:-1]))
    _,_,actions,_=reference.golden(quantized,q)
    body=bytes.fromhex('02 06')+struct.pack('<3h',*actions)
    response=bytes.fromhex('5a a5')+body+bytes([uart.crc8_maxim(body)])
    parsed=uart.parse_response_packet(response)
    record={'scope':'Expected reference result, not a physical Jetson measurement',
            'baud':9600,'format':'8N1','numeric_format':'Q8.8','observation':[0.8]*64+[0.0]*10,
            'quantized_observation':quantized,'q8_8_results':actions,
            'residuals':parsed['ai_results'],'tx_bytes':len(packet),'tx_hex':packet.hex(' '),
            'rx_bytes':len(response),'rx_hex':response.hex(' '),
            'model_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),
            'expected_frames_sent':50,'expected_frames_received':50,'expected_frames_dropped':0,
            'expected_total_response_bytes':550}
    (OUT/'expected.json').write_text(json.dumps(record,indent=2)+'\n')
    (OUT/'request.bin').write_bytes(packet)
    (OUT/'response.bin').write_bytes(response)
    lines=['EXPECTED OUTPUT EXAMPLE -- RTT and script hash depend on the actual run.',
           'IGOR source-policy UART | /dev/ttyTHS1 | 9600 baud | TX=153B RX=11B CRC8 Maxim']
    lines += [f'[Frame {n:4d}] PASS | {uart.format_q88(parsed["q8_8_results"])} | RTT: <measured> us' for n in range(50)]
    lines += ['Frames sent: 50 | received: 50 | dropped: 0','Validation passed: 50/50','Mean RTT: <measured> us (includes UART transfer)']
    (OUT/'expected_terminal.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:record[k] for k in ('q8_8_results','residuals','rx_hex')},indent=2))

if __name__=='__main__': main()
