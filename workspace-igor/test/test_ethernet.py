"""Localhost UDP + fixture UART integration. No physical FPGA/network acceptance."""
import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'src/igor_controller/igor_controller'
sys.path.insert(0,str(PACKAGE))
import ethernet_protocol as protocol

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

gateway=load('eth_gateway',ROOT/'src/igor_pipeline/hps_de10/de10_udp_gateway.py')
client=load('eth_client',ROOT/'src/igor_pipeline/scripts/ethernet_test.py')
bridge=load('eth_bridge',PACKAGE/'fpga_bridge.py')
VECTORS=ROOT/'src/igor_pipeline/scripts/uart_q88_vectors.json'
CASES=json.loads(VECTORS.read_text())['cases']

class FixtureSerial:
    def __init__(self,*args,**kwargs):self.pending=b'';self.writes=[];self.bad=False
    def reset_input_buffer(self):self.pending=b''
    def write(self,packet):
        assert packet[:4]==bytes.fromhex('5a a5 01 94') and len(packet)==153
        assert packet[-1]==gateway.crc8(packet[2:-1])
        obs=list(struct.unpack('<74h',packet[4:-1]))
        case=next(c for c in CASES if c['observation_q88']==obs)
        self.pending=bytes.fromhex(case['rx_hex']) if not self.bad else b'\x00'*11
        self.writes.append(packet);return len(packet)
    def flush(self):pass
    def read(self,size):
        data=self.pending[:size];self.pending=self.pending[size:];return data
    def close(self):pass

class EthernetTests(unittest.TestCase):
    def server(self,backend):
        server=gateway.Gateway('127.0.0.1',0,backend)
        thread=threading.Thread(target=server.serve,daemon=True);thread.start()
        def cleanup():server.running=False;thread.join(1);server.close()
        self.addCleanup(cleanup)
        return server
    def link(self,server,timeout=.3):
        link=protocol.UDPLink(f'udp://127.0.0.1:{server.address[1]}',timeout)
        self.addCleanup(link.close);return link
    def uart_backend(self):
        fixture=FixtureSerial()
        with patch('serial.Serial',return_value=fixture):backend=gateway.UARTBackend('TEST',9600,.3)
        return backend,fixture

    def test_exact_protocol_sizes_roundtrip_all_cases(self):
        self.assertEqual(protocol.REQUEST.size,492);self.assertEqual(protocol.RESPONSE.size,50)
        for case in CASES:
            raw=protocol.build_request_q88(case['observation_q88'],7,123456)
            self.assertEqual(protocol.parse_request(raw)['observation_q88'],case['observation_q88'])
            response=protocol.build_response(7,123456,case['expected_q88'])
            self.assertEqual(protocol.parse_response(response)['q8_8_results'],case['expected_q88'])

    def test_reject_lengths_crc_nonfinite_and_redundant_float(self):
        raw=protocol.build_request_q88(CASES[0]['observation_q88'],1,1)
        for bad in (raw[:-1],raw+b'x',b'\x00'+raw[1:]):
            with self.assertRaises(protocol.ProtocolError):protocol.parse_request(bad)
        for value in (float('nan'),float('inf'),.1):
            body=bytearray(raw[:-4]);struct.pack_into('<f',body,44,value)
            bad=body+struct.pack('<I',protocol.crc32(body))
            with self.assertRaises(protocol.ProtocolError):protocol.parse_request(bad)
        response=protocol.build_response(1,1,[-46,60,34])
        for bad in (response[:48],response+b'xx',response[:-1]+bytes([response[-1]^1])):
            with self.assertRaises(protocol.ProtocolError):protocol.parse_response(bad)

    def test_real_localhost_udp_to_uart_fixture_16_cases(self):
        backend,fixture=self.uart_backend();server=self.server(backend);link=self.link(server)
        for case in CASES:self.assertEqual(link.infer_q88(case['observation_q88']),case['expected_q88'])
        self.assertEqual(len(fixture.writes),16)
        self.assertEqual(link.last_response['execution_cycles'],0)

    def test_production_bridge_uses_same_udp_protocol(self):
        backend,_=self.uart_backend();server=self.server(backend)
        b=bridge.FPGABridge(port=f'udp://127.0.0.1:{server.address[1]}',timeout=.3)
        self.addCleanup(b.close)
        result=b.infer([v/256 for v in CASES[0]['observation_q88']])
        self.assertEqual(list(result),[-46/256,60/256,34/256]);self.assertTrue(b.last_exchange_ok)

    def test_mock_explicitly_not_production_success(self):
        server=self.server(gateway.MockBackend());link=self.link(server)
        with self.assertRaises(protocol.ProtocolError):link.infer_q88(CASES[0]['observation_q88'])
        self.assertTrue(link.failed)
        diagnostic=self.link(server)
        self.assertEqual(diagnostic.infer_q88(CASES[0]['observation_q88'],allow_test=True),[0,0,0])
        self.assertEqual(diagnostic.last_response['status_code'],6)

    def test_uart_error_latches_server_and_client(self):
        backend,fixture=self.uart_backend();fixture.bad=True;server=self.server(backend);link=self.link(server)
        with self.assertRaises(protocol.ProtocolError):link.infer_q88(CASES[0]['observation_q88'])
        with self.assertRaises(protocol.ProtocolError):link.infer_q88(CASES[0]['observation_q88'])
        fixture.bad=False;other=self.link(server)
        with self.assertRaises(protocol.ProtocolError):other.infer_q88(CASES[0]['observation_q88'])
        self.assertEqual(len(fixture.writes),1)

    def test_malformed_request_never_reaches_uart(self):
        backend,fixture=self.uart_backend();server=self.server(backend)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.settimeout(.03)
            raw=protocol.build_request_q88(CASES[0]['observation_q88'],1,1)
            s.sendto(raw+b'oversized',server.address)
            with self.assertRaises(socket.timeout):s.recv(4096)
        self.assertEqual(fixture.writes,[])

    def test_duplicate_datagram_does_not_trigger_uart_again(self):
        backend,fixture=self.uart_backend();server=self.server(backend)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.settimeout(.1);raw=protocol.build_request_q88(CASES[0]['observation_q88'],1,1)
            s.sendto(raw,server.address);self.assertEqual(len(s.recv(4096)),50)
            s.sendto(raw,server.address)
            with self.assertRaises(socket.timeout):s.recv(4096)
        self.assertEqual(len(fixture.writes),1)

    def test_stale_identity_ignored_and_timeout_latched(self):
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',0))
        def worker():
            raw,peer=sock.recvfrom(4096);r=protocol.parse_request(raw)
            sock.sendto(protocol.build_response(r['frame_id']-1,r['timestamp_ns'],[0,0,0]),peer)
            sock.sendto(protocol.build_response(r['frame_id'],r['timestamp_ns'],[-46,60,34]),peer)
        thread=threading.Thread(target=worker);thread.start()
        link=protocol.UDPLink(f'udp://127.0.0.1:{sock.getsockname()[1]}',.2)
        try:self.assertEqual(link.infer_q88(CASES[0]['observation_q88']),[-46,60,34])
        finally:link.close();thread.join(1);sock.close()
        silent=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);silent.bind(('127.0.0.1',0))
        link=protocol.UDPLink(f'udp://127.0.0.1:{silent.getsockname()[1]}',.02)
        try:
            with self.assertRaises(protocol.ProtocolError):link.infer_q88(CASES[0]['observation_q88'])
            self.assertTrue(link.failed)
        finally:link.close();silent.close()

    def test_cli_capture_redecode_and_network_only_labels(self):
        backend,_=self.uart_backend();server=self.server(backend)
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()):
            path=Path(tmp)/'eth.jsonl'
            self.assertTrue(client.run('127.0.0.1',server.address[1],16,.3,VECTORS,True,False,path))
            self.assertTrue(client.check_log(path,VECTORS))
            rows=path.read_text().splitlines();row=json.loads(rows[0]);row['rx_udp_hex']='00 '*50
            rows[0]=json.dumps(row);path.write_text('\n'.join(rows)+'\n')
            with self.assertRaises(protocol.ProtocolError):client.check_log(path,VECTORS)
        mock=self.server(gateway.MockBackend())
        with redirect_stdout(io.StringIO()):
            self.assertTrue(client.run('127.0.0.1',mock.address[1],2,.3,VECTORS,False,True))
            self.assertFalse(client.run('127.0.0.1',mock.address[1],1,.3,VECTORS))

    def test_source_and_packaged_clients_identical(self):
        for name in ('fpga_bridge.py','ethernet_protocol.py'):
            self.assertEqual((PACKAGE/name).read_bytes(),(ROOT/'fpga/software_integration/src/igor_controller/igor_controller'/name).read_bytes())

    def test_coarse_clock_still_produces_unique_transactions(self):
        backend,fixture=self.uart_backend();server=self.server(backend);link=self.link(server)
        with patch.object(protocol.time,'monotonic_ns',return_value=100):
            for _ in range(3):self.assertEqual(link.infer_q88(CASES[0]['observation_q88']),[-46,60,34])
        self.assertEqual(link.last_response['timestamp_ns'],102)
        self.assertEqual(len(fixture.writes),3)

    def test_uart_total_deadline_not_just_read_timeout(self):
        fixture=FixtureSerial()
        with patch('serial.Serial',return_value=fixture):backend=gateway.UARTBackend('TEST',921600,.02)
        with patch.object(gateway.time,'monotonic',side_effect=[10.,10.03]):
            status,values=backend.infer(CASES[0]['observation_q88'])
        self.assertEqual(status,4);self.assertEqual(values,[0,0,0]);self.assertTrue(backend.failed)
        self.assertEqual(backend.infer(CASES[0]['observation_q88'])[0],7)

    def test_source_controller_transport_handler_commands_full_stop(self):
        tree=ast.parse((PACKAGE/'controller_node.py').read_text(encoding='utf-8-sig'))
        handler=next(n for n in ast.walk(tree) if isinstance(n,ast.ExceptHandler)
                     and isinstance(n.type,ast.Name) and n.type.id=='FPGACommunicationError')
        function=ast.parse('def handle(self,exc):\n    pass').body[0]
        function.body=handler.body
        def message(**kwargs):return SimpleNamespace(**kwargs)
        context={'Twist':message,'Bool':message,'String':message,'json':json}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'controller handler','exec'),context)
        calls=[];published=[]
        pub=SimpleNamespace(publish=lambda value:published.append(value))
        node=SimpleNamespace(mcu=SimpleNamespace(send_motor_speeds=lambda *args:calls.append(args)),
            pub_safe_twist=pub,pub_safety_alert=pub,pub_diag=pub,
            get_logger=lambda:SimpleNamespace(error=lambda *args:None))
        context['handle'](node,RuntimeError('timeout'))
        self.assertEqual(calls,[(0.,0.,0.,0.)])
        self.assertFalse(json.loads(published[-1].data)['safety_permit'])

    def test_old_hal_cannot_map_unreserved_physical_ddr(self):
        compiler=shutil.which('gcc')
        if not compiler:self.skipTest('gcc not installed')
        code='#include "de10_shared_mem_ext.h"\nint main(void){SoC_HAL_Context c;int r=hal_init(&c,0);if(r!=-10 || c.mem_fd!=-1)return 1;hal_cleanup(&c);return 0;}\n'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'hal.c').write_text(code)
            folder=ROOT/'src/igor_pipeline/hps_de10'
            result=subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-I',str(folder),
                str(p/'hal.c'),str(folder/'de10_shared_mem_ext.c'),'-o',str(p/'hal.exe')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(p/'hal.exe')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_c_struct_interoperability(self):
        compiler=shutil.which('gcc')
        if not compiler:self.skipTest('gcc not installed')
        source=r'''#include "protocol_v2.h"
#include <stdio.h>
int main(int argc,char **argv){
 if(argc!=2)return 1;
 SensorPacketV2 in;InferenceResponsePacketV2 out={0};
 FILE *f=fopen(argv[1],"rb");if(!f)return 2;
 if(fread(&in,1,sizeof(in),f)!=sizeof(in))return 3;fclose(f);
 if(validate_sensor_packet(&in))return 4;
 out.frame_id=in.frame_id;out.timestamp_ns=in.timestamp_ns;
 out.q8_8_results[0]=-46;out.q8_8_results[1]=60;out.q8_8_results[2]=34;
 for(int i=0;i<3;i++)out.ai_results[i]=out.q8_8_results[i]/256.0f;
 serialize_response_packet(&out);
 return fwrite(&out,1,sizeof(out),stdout)==sizeof(out)?0:5;
}'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'layout.c').write_text(source)
            build=subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror',
                '-Wno-misleading-indentation','-I',str(ROOT/'src/igor_pipeline/protocol'),
                str(p/'layout.c'),'-o',str(p/'layout.exe')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            packet=protocol.build_request_q88(CASES[0]['observation_q88'],42,1234567)
            (p/'request.bin').write_bytes(packet)
            result=subprocess.run([str(p/'layout.exe'),str(p/'request.bin')],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,protocol.build_response(42,1234567,[-46,60,34]))

if __name__=='__main__':unittest.main()
