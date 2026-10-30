"""Query actual FPGA RX counters through JTAG and test COM12 pad echo/inference."""
import ctypes as C
import argparse
import datetime
import importlib.util
import json
import time
from pathlib import Path
import serial
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port',default='COM12')
parser.add_argument('--header',choices=['JP7','JP1_3_4','JP1_1_2'],default='JP7')
args=parser.parse_args()
folder={'JP7':'jp7_monitor','JP1_3_4':'jp1_3_4_monitor','JP1_1_2':'jp1_1_2_monitor'}[args.header]
out=root/'evidence'/folder/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True)
lib=C.CDLL(r'D:\Quartus-Program\quartus\bin64\jtag_atlantic.dll')
def bind(name,result,args):
 f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
open_jtag=bind('?jtagatlantic_open@@YAPEAUJTAGATLANTIC@@PEBDHH0@Z',C.c_void_p,[C.c_char_p,C.c_int,C.c_int,C.c_char_p])
close_jtag=bind('?jtagatlantic_close@@YAXPEAUJTAGATLANTIC@@@Z',None,[C.c_void_p])
read_jtag=bind('?jtagatlantic_read@@YAHPEAUJTAGATLANTIC@@PEADI@Z',C.c_int,[C.c_void_p,C.c_void_p,C.c_uint])
write_jtag=bind('?jtagatlantic_write@@YAHPEAUJTAGATLANTIC@@PEBDI@Z',C.c_int,[C.c_void_p,C.c_char_p,C.c_uint])
flush_jtag=bind('?jtagatlantic_flush@@YAHPEAUJTAGATLANTIC@@@Z',C.c_int,[C.c_void_p])
handle=open_jtag(b'DE-SoC [USB-1]',2,0,b'GARDA JP7 physical diagnostics')
if not handle:raise SystemExit('JTAG monitor unavailable; close other JTAG terminals.')
records=[]
echo_enabled=False
def command(c):
 if write_jtag(handle,c,1)!=1:raise RuntimeError('JTAG write failed')
 flush_jtag(handle)
 data=bytearray();deadline=time.monotonic()+3;buffer=C.create_string_buffer(4096)
 while time.monotonic()<deadline:
  n=read_jtag(handle,buffer,len(buffer))
  if n<0:raise RuntimeError('JTAG read failed')
  if n:data.extend(buffer.raw[:n])
  if b'\r\n> ' in data:break
  time.sleep(.01)
 text=data.decode('ascii',errors='replace');print(text,flush=True)
 records.append({'command':c.decode(),'status':text})
 return text
try:
 initial=command(b'q')
 expected_header={'JP7':'JP7 q=status','JP1_3_4':'JP1 pins 3/4 q=status','JP1_1_2':'JP1 pins 1/2 q=status'}[args.header]
 if expected_header not in initial:raise RuntimeError('Wrong or unresponsive FPGA monitor image; diagnostic stopped before echo testing.')
 command(b'e');echo_enabled=True
 pattern=bytes.fromhex('55 aa 00 ff 5a a5')+b'GARDA-JP7'
 for baud in [9600,115200,921600]:
  with serial.Serial(args.port,baud,timeout=.05,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False) as port:
   port.reset_input_buffer();port.write(pattern);port.flush()
   rx=bytearray();deadline=time.monotonic()+.5
   while len(rx)<len(pattern) and time.monotonic()<deadline:rx.extend(port.read(len(pattern)-len(rx)))
  result={'test':'physical_pad_echo','baud':baud,'tx_hex':pattern.hex(' '),'rx_hex':rx.hex(' '),'passed':bytes(rx)==pattern}
  print(result,flush=True);records.append(result);command(b'q')
 command(b'i');echo_enabled=False
 spec=importlib.util.spec_from_file_location('garda_uart_reference',root.parent/'src/garda_pipeline/scripts/uart_test.py')
 ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
 with serial.Serial(args.port,921600,timeout=.02,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False) as port:
  try:
   response,elapsed=ref.exchange_q88(port,ref.DEFAULT_OBS_Q88,1)
   result={'test':'inference','passed':response['q8_8_results']==[-46,60,34],'response':response,'elapsed_us':elapsed}
  except ValueError as exc:result={'test':'inference','passed':False,'error':str(exc)}
  records.append(result);print(result,flush=True)
 command(b'q')
finally:
 if echo_enabled:
  try:command(b'i')
  except Exception as exc:records.append({'cleanup_error':str(exc)})
 close_jtag(handle)
 (out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
 print(f'Evidence: {out}',flush=True)
raise SystemExit(0 if len([x for x in records if x.get('passed') is True])==4 else 1)
