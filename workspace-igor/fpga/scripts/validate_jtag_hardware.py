"""Exercise the physical JTAG console with the installed Quartus Windows DLL.

No simulator/model is substituted. Close other JTAG terminals before running.
The MSVC x64 export names below are from Quartus Standard 25.1's installed DLL.
"""
import ctypes as C
import json
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
evidence = root/'evidence/jtag_parallel8'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
evidence.mkdir(parents=True,exist_ok=True)
lib = C.CDLL(r'D:\Quartus-Program\quartus\bin64\jtag_atlantic.dll')
def bind(name, result, args):
    f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
open_uart=bind('?jtagatlantic_open@@YAPEAUJTAGATLANTIC@@PEBDHH0@Z', C.c_void_p,[C.c_char_p,C.c_int,C.c_int,C.c_char_p])
close_uart=bind('?jtagatlantic_close@@YAXPEAUJTAGATLANTIC@@@Z',None,[C.c_void_p])
read_uart=bind('?jtagatlantic_read@@YAHPEAUJTAGATLANTIC@@PEADI@Z',C.c_int,[C.c_void_p,C.c_void_p,C.c_uint])
write_uart=bind('?jtagatlantic_write@@YAHPEAUJTAGATLANTIC@@PEBDI@Z',C.c_int,[C.c_void_p,C.c_char_p,C.c_uint])
flush_uart=bind('?jtagatlantic_flush@@YAHPEAUJTAGATLANTIC@@@Z',C.c_int,[C.c_void_p])
handle=open_uart(b'DE-SoC [USB-1]',2,0,b'IGOR hardware validation')
if not handle:
    raise SystemExit('Cannot open physical JTAG UART device 2, instance 0. Close other terminals.')
raw=[]
def receive(seconds=8, prompt=True):
    result=bytearray();deadline=time.monotonic()+seconds
    buffer=C.create_string_buffer(4096)
    while time.monotonic()<deadline:
        n=read_uart(handle,buffer,len(buffer))
        if n<0: raise RuntimeError('Physical JTAG read failed')
        if n:
            result.extend(buffer.raw[:n])
            if prompt and b'\r\n> ' in result: break
        time.sleep(.01)
    text=result.decode('ascii',errors='replace')
    raw.append(text);print(text,flush=True)
    return text
def send(data):
    offset=0;deadline=time.monotonic()+10
    while offset<len(data):
        n=write_uart(handle,data[offset:],len(data)-offset)
        if n<0:raise RuntimeError('Physical JTAG write failed')
        offset+=n
        if time.monotonic()>deadline:raise TimeoutError('Physical JTAG write timed out')
        time.sleep(.01)
    if flush_uart(handle)<0:raise RuntimeError('JTAG flush failed')
results=[]
try:
    receive(.3,False) # Discard any previous prompt before each command test.
    for i,command in enumerate([b'r',b'r\r',b'r\r\n']):
        send(command);text=receive()
        ok='5A A5 02 06 D2 FF 3C 00 22 00 61' in text and 'cycles=0x00001B04' in text and 'CHECK=PASS' in text
        results.append({'test':f'physical_demo_{i+1}','pass':ok})
        if not ok:raise AssertionError(results[-1])
        extra=receive(.25,False)
        ok='RX count=' not in extra
        results.append({'test':f'no_extra_report_after_demo_{i+1}','pass':ok})
        if not ok:raise AssertionError(results[-1])
    send(b'\r\n'*20);text=receive(.25,False)
    ok='RX count=' not in text
    results.append({'test':'twenty_blank_CRLF_pairs_ignored','pass':ok})
    if not ok:raise AssertionError(results[-1])
    send(b'!');text=receive()
    ok='RX count=0x0 FPGA bytes: -- -- -- -- -- -- -- -- -- -- --' in text and 'error=0x06 CHECK=PASS' in text
    results.append({'test':'physical_bad_crc','pass':ok})
    if not ok:raise AssertionError(results[-1])
    manifest=json.loads((root/'experiments/parallel8_jtag/source_manifest.json').read_text())
    send(manifest['demo_request_hex'].encode()+b'\r\n');text=receive()
    ok='5A A5 02 06 D2 FF 3C 00 22 00 61' in text and 'CHECK=DATA' in text
    results.append({'test':'physical_pasted_hex','pass':ok})
    if not ok:raise AssertionError(results[-1])
    extra=receive(.25,False)
    ok='RX count=' not in extra
    results.append({'test':'custom_frame_CRLF_single_report','pass':ok})
    if not ok:raise AssertionError(results[-1])
    print(f'PASS: all {len(results)} physical JTAG checks; evidence: {evidence}',flush=True)
finally:
    close_uart(handle)
    (evidence/'physical_commands.log').write_text('\n'.join(raw))
    image=json.loads((root/'bitstreams/igor_parallel8_jtag.json').read_text(encoding='utf-8-sig'))
    (evidence/'physical_commands.json').write_text(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'image_sha256':image['sha256'],'cable':'DE-SoC [USB-1]','device':2,'instance':0,'results':results},indent=2)+'\n')
