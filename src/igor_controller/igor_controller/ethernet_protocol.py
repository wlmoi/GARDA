"""IGOR Protocol V2: packed little endian UDP, 492-byte request / 50-byte response.

Q8.8 is authoritative. Redundant float fields must agree with its quantization.
No retries, mock fallback, or unverified zero actions are permitted.
"""
import math
import socket
import struct
import time
import zlib

MAGIC=0x49474F52
REQUEST=struct.Struct('<IIQ3f3fI74f74hI')
RESPONSE=struct.Struct('<IIQII3f3hII')
STATUS_OK=0
STATUS_PL_TIMEOUT=4
STATUS_TEST_ONLY=6
STATUS_BACKEND_FAULT=7

class ProtocolError(RuntimeError):pass

def crc32(data):return zlib.crc32(data)&0xffffffff

def validate_q88(values,count=74):
    if len(values)!=count or any(type(v) is not int for v in values):
        raise ProtocolError(f'Expected {count} raw Q8.8 integers')
    if any(not (0 if i<64 and count==74 else -256)<=v<=256 for i,v in enumerate(values)):
        raise ProtocolError('Q8.8 value outside normalized domain')
    return list(values)

def build_request_q88(values,frame_id,timestamp_ns,linear=(0.,0.,0.),angular=(0.,0.,0.)):
    values=validate_q88(values)
    if len(linear)!=3 or len(angular)!=3 or not all(math.isfinite(v) for v in (*linear,*angular)):
        raise ProtocolError('Velocity metadata must contain six finite scalars')
    body=REQUEST.pack(MAGIC,frame_id,timestamp_ns,*linear,*angular,74,
                      *(v/256 for v in values),*values,0)[:-4]
    return body+struct.pack('<I',crc32(body))

def parse_request(raw):
    if len(raw)!=REQUEST.size:raise ProtocolError(f'Request length {len(raw)} != {REQUEST.size}')
    fields=REQUEST.unpack(raw)
    if fields[0]!=MAGIC or fields[9]!=74:raise ProtocolError('Request magic/dimension mismatch')
    if fields[-1]!=crc32(raw[:-4]):raise ProtocolError('Request CRC32 mismatch')
    floats=fields[10:84]; values=validate_q88(list(fields[84:158]))
    if not all(math.isfinite(v) for v in fields[3:9]+floats):raise ProtocolError('Nonfinite request')
    if any(not (0 if i<64 else -1)<=v<=1 or round(v*256)!=q for i,(v,q) in enumerate(zip(floats,values))):
        raise ProtocolError('Float/Q8.8 observation mismatch')
    return {'frame_id':fields[1],'timestamp_ns':fields[2],'observation_q88':values}

def build_response(frame_id,timestamp_ns,values=(0,0,0),status=STATUS_OK,cycles=0):
    values=validate_q88(list(values),3)
    if status!=STATUS_OK:values=[0,0,0]
    body=RESPONSE.pack(MAGIC,frame_id,timestamp_ns,status,3,*(v/256 for v in values),*values,cycles,0)[:-4]
    return body+struct.pack('<I',crc32(body))

def parse_response(raw):
    if len(raw)!=RESPONSE.size:raise ProtocolError(f'Response length {len(raw)} != {RESPONSE.size}')
    f=RESPONSE.unpack(raw)
    if f[0]!=MAGIC or f[4]!=3:raise ProtocolError('Response magic/dimension mismatch')
    if f[-1]!=crc32(raw[:-4]):raise ProtocolError('Response CRC32 mismatch')
    values=validate_q88(list(f[8:11]),3)
    if any(not math.isfinite(v) or v!=q/256 for v,q in zip(f[5:8],values)):
        raise ProtocolError('Response float/Q8.8 mismatch')
    return {'frame_id':f[1],'timestamp_ns':f[2],'status_code':f[3],
            'q8_8_results':values,'execution_cycles':f[11]}

class UDPLink:
    def __init__(self,address,timeout=.3):
        if not address.startswith('udp://'):raise ProtocolError('Use udp://IPv4-or-hostname:port')
        host,separator,port=address[6:].rpartition(':')
        if not separator or not host or not port.isdigit() or not 1<=int(port)<=65535:
            raise ProtocolError('Invalid UDP endpoint')
        if not math.isfinite(timeout) or timeout<=0:raise ProtocolError('Invalid timeout')
        self.timeout=timeout;self.counter=0;self.last_stamp=0;self.last_response=None;self.failed=False
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:self.socket.connect((host,int(port)))
        except Exception:self.socket.close();raise
    def infer_q88(self,values,allow_test=False):
        if self.failed:raise ProtocolError('UDP fault latched; reset FPGA/backend and recreate link')
        # Validate before transmission. A local invalid input does not consume a transaction.
        validate_q88(values)
        self.counter=(self.counter+1)&0xffffffff
        # Some hosts have a coarse monotonic clock. Consecutive requests must
        # still have distinct strictly increasing identities.
        stamp=max(time.monotonic_ns(),self.last_stamp+1)
        self.last_stamp=stamp
        packet=build_request_q88(values,self.counter,stamp)
        deadline=time.monotonic()+self.timeout
        try:
            if self.socket.send(packet)!=len(packet):raise ProtocolError('Short UDP send')
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise ProtocolError('UDP exchange deadline expired')
                self.socket.settimeout(remaining)
                raw=self.socket.recv(65535)
                response=parse_response(raw)
                if time.monotonic()>deadline:raise ProtocolError('UDP response exceeded deadline')
                if response['frame_id']!=self.counter or response['timestamp_ns']!=stamp:
                    continue # Old datagram cannot satisfy this request.
                if response['status_code']!=STATUS_OK and not (allow_test and response['status_code']==STATUS_TEST_ONLY):
                    raise ProtocolError(f'Backend status {response["status_code"]}; no valid FPGA action')
                self.last_response=response
                self.last_raw_response=raw
                return response['q8_8_results']
        except Exception as exc:
            self.failed=True
            raise ProtocolError(f'UDP exchange failed: {exc}') from exc
    def close(self):self.socket.close()
