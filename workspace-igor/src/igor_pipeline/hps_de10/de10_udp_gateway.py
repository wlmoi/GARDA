#!/usr/bin/env python3
"""HPS UDP gateway. Real backend uses a LOCAL USB-UART adapter to fabric UART.
No /dev/mem, fabricated cycle counter, or automatic mock fallback.
"""
import argparse
from collections import OrderedDict
import json
import math
from pathlib import Path
import signal
import socket
import struct
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'igor_controller/igor_controller'))
from ethernet_protocol import (parse_request,build_response,ProtocolError,
    STATUS_OK,STATUS_PL_TIMEOUT,STATUS_TEST_ONLY,STATUS_BACKEND_FAULT)

def crc8(data):
    c=0
    for byte in data:
        c^=byte
        for _ in range(8):c=(c>>1)^(0x8c if c&1 else 0)
    return c

class UARTBackend:
    def __init__(self,port,baud,timeout):
        import serial
        if timeout<1640/baud+.01:raise ValueError('Backend timeout shorter than UART wire time + 10 ms margin')
        self.timeout=timeout;self.failed=False
        self.serial=serial.Serial(port,baud,timeout=timeout,write_timeout=timeout,
            exclusive=True,bytesize=8,parity='N',stopbits=1,xonxoff=False,rtscts=False,dsrdtr=False)
    def infer(self,values):
        if self.failed:return STATUS_BACKEND_FAULT,[0,0,0]
        try:
            body=bytes([1,148])+struct.pack('<74h',*values)
            packet=bytes.fromhex('5a a5')+body+bytes([crc8(body)])
            deadline=time.monotonic()+self.timeout
            self.serial.reset_input_buffer()
            if self.serial.write(packet)!=153:raise ProtocolError('Short UART write')
            self.serial.flush()
            remaining=deadline-time.monotonic()
            if remaining<=0:raise ProtocolError('UART write deadline expired')
            self.serial.timeout=remaining
            raw=self.serial.read(11)
            if time.monotonic()>deadline:raise ProtocolError('UART deadline exceeded')
            if len(raw)!=11 or raw[:4]!=bytes.fromhex('5a a5 02 06') or raw[-1]!=crc8(raw[2:-1]):
                raise ProtocolError(f'Invalid UART response: {raw.hex(" ")}')
            result=list(struct.unpack('<3h',raw[4:10]))
            if any(abs(v)>256 for v in result):raise ProtocolError('UART output domain violation')
            return STATUS_OK,result
        except Exception as exc:
            self.failed=True
            print(f'BACKEND LATCHED: {exc}; reset FPGA and restart gateway',file=sys.stderr,flush=True)
            return STATUS_PL_TIMEOUT,[0,0,0]
    def close(self):self.serial.close()

class MockBackend:
    def infer(self,values):return STATUS_TEST_ONLY,[0,0,0]
    def close(self):pass

class Gateway:
    def __init__(self,host,port,backend,allowed_client=None,log=None):
        self.backend=backend;self.log=log;self.allowed_client=allowed_client
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:self.socket.bind((host,port))
        except Exception:self.socket.close();backend.close();raise
        self.socket.settimeout(.1);self.running=True
        self.backend_failed=False
        self.peers=OrderedDict()
    @property
    def address(self):return self.socket.getsockname()
    def serve(self):
        while self.running:
            try:raw,peer=self.socket.recvfrom(65535)
            except socket.timeout:continue
            if self.allowed_client and peer[0]!=self.allowed_client:continue
            try:request=parse_request(raw)
            except ProtocolError as exc:
                print(f'DROP {peer}: {exc}',file=sys.stderr,flush=True);continue
            # One outstanding request per peer. Duplicates/out-of-order datagrams
            # must not trigger the unsequenced UART accelerator again.
            stamp=request['timestamp_ns']
            if stamp<=self.peers.get(peer,-1):continue
            self.peers[peer]=stamp;self.peers.move_to_end(peer)
            while len(self.peers)>128:self.peers.popitem(last=False)
            start=time.monotonic()
            try:
                status,values=(STATUS_BACKEND_FAULT,[0,0,0]) if self.backend_failed else self.backend.infer(request['observation_q88'])
            except Exception as exc:
                print(f'Backend exception: {exc}',file=sys.stderr,flush=True)
                status,values=STATUS_BACKEND_FAULT,[0,0,0]
                self.backend_failed=True
                # Unexpected backend errors cannot permit later hardware actions.
                if hasattr(self.backend,'failed'):self.backend.failed=True
            response=build_response(request['frame_id'],stamp,values,status=status,cycles=0)
            self.socket.sendto(response,peer)
            if self.log:
                self.log.write(json.dumps({'peer':peer,'frame_id':request['frame_id'],
                    'timestamp_ns':stamp,'status':status,'observation_q88':request['observation_q88'],
                    'actual_q88':values if status==0 else None,'elapsed_ms':(time.monotonic()-start)*1000})+'\n')
                self.log.flush()
    def close(self):
        self.running=False;self.socket.close();self.backend.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind',default='0.0.0.0')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--backend',choices=('uart','mock'),required=True)
    parser.add_argument('--serial')
    parser.add_argument('--baud',type=int,choices=(9600,921600),default=9600)
    parser.add_argument('--timeout',type=float,default=.5)
    parser.add_argument('--allow-client',help='Only accept datagrams from this IPv4 address')
    parser.add_argument('--log',type=Path,help='New JSONL file')
    args=parser.parse_args()
    if not 1<=args.port<=65535 or not math.isfinite(args.timeout) or args.timeout<=0:
        parser.error('Invalid port/timeout')
    if args.backend=='uart' and not args.serial:parser.error('--serial is required for UART hardware backend')
    log=None;gateway=None
    try:
        if args.log:log=args.log.open('x',encoding='utf-8')
        backend=UARTBackend(args.serial,args.baud,args.timeout) if args.backend=='uart' else MockBackend()
        gateway=Gateway(args.bind,args.port,backend,args.allow_client,log)
        def stop(*_):gateway.running=False
        signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
        print(f'UDP {gateway.address}, backend={args.backend}, RX=492 TX=50 bytes, Q8.8; cycles=unknown/0',flush=True)
        if args.backend=='mock':print('NETWORK TEST ONLY: status=6; production clients reject this response',flush=True)
        gateway.serve()
        return 0
    except (OSError,ValueError,ImportError) as exc:
        print(f'Gateway startup/runtime failed: {exc}',file=sys.stderr);return 1
    finally:
        if gateway:gateway.close()
        if log:log.close()

if __name__=='__main__':raise SystemExit(main())
