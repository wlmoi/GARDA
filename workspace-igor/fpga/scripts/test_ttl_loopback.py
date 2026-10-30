"""Physical USB-TTL loopback test. Disconnect FPGA; short adapter TX to RX first."""
import argparse
import json
import time
from pathlib import Path
import serial

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port',required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
logs=root/'evidence/jp7_uart'/time.strftime('loopback_%Y%m%dT%H%M%SZ',time.gmtime())
logs.mkdir(parents=True,exist_ok=True)
pattern=bytes.fromhex('55 aa 5a a5 00 ff 01 7f 80 fe')+b'IGOR-TTL-LOOPBACK\r\n'
results=[]
for baud in [9600,115200,921600]:
    with serial.Serial(args.port,baud,timeout=.05,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False) as port:
        port.reset_input_buffer()
        port.write(pattern);port.flush()
        received=bytearray();deadline=time.monotonic()+1
        while len(received)<len(pattern) and time.monotonic()<deadline:
            received.extend(port.read(len(pattern)-len(received)))
    ok=bytes(received)==pattern
    results.append({'baud':baud,'passed':ok,'tx_hex':pattern.hex(' '),'rx_hex':received.hex(' ')})
    print(f'{baud}: {"PASS" if ok else "FAIL"} TX={len(pattern)} RX={len(received)}; RX={received.hex(" ")}',flush=True)
(logs/'results.json').write_text(json.dumps({'port':args.port,'setup':'FPGA disconnected, adapter TX shorted to RX by user','results':results},indent=2)+'\n')
print(f'Evidence: {logs}')
raise SystemExit(0 if all(x['passed'] for x in results) else 1)
