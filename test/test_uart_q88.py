import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'src/igor_pipeline/scripts'
sys.path.insert(0,str(SCRIPTS))
import uart_test as uart
import uart_validate_q88 as offline
import uart_validate_hardware_q88 as hardware

class Q88Tests(unittest.TestCase):
    def test_integer_endian_and_domains(self):
        obs=[256]*64+[-256,-1,0,1,256]*2
        raw=uart.build_sensor_packet_q88(obs)
        self.assertEqual(raw[132:142],bytes.fromhex('00 ff ff ff 00 00 01 00 00 01'))
        self.assertEqual(list(struct.unpack('<74h',raw[4:-1])),obs)
        for bad in (None,[0]*73,[0.0]*74,[True]*74,[-1]*74,[257]*74):
            with self.assertRaises(ValueError):uart.build_sensor_packet_q88(bad)
        self.assertIn('0xFFD2',uart.format_q88([-46,60,34]))

    def test_fixture_integrity(self):
        data=offline.load_vectors(offline.DEFAULT_VECTORS)
        self.assertEqual(len(data['cases']),16)
        self.assertEqual(data['cases'][0]['expected_q88'],[-46,60,34])
        with tempfile.TemporaryDirectory() as tmp:
            data['cases'][0]['rx_hex']='00'*11
            path=Path(tmp)/'bad.json';path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):offline.load_vectors(path)

    def capture(self,case):
        return {'frame_id':0,'format':'Q8.8','baud':9600,
                'observation_q88':case['observation_q88'],'expected_q88':case['expected_q88'],
                'actual_q88':case['expected_q88'],'rx_hex':case['rx_hex'],'passed':True}

    def test_capture_rejects_tampering_and_missing_frames(self):
        data=offline.load_vectors(offline.DEFAULT_VECTORS)
        item=self.capture(data['cases'][0])
        with tempfile.TemporaryDirectory() as tmp,patch('builtins.print'):
            path=Path(tmp)/'capture.jsonl'
            path.write_text(json.dumps(item)+'\n')
            self.assertTrue(offline.validate_capture(path,data,1))
            self.assertFalse(offline.validate_capture(path,data,2))
            for field,value in [('actual_q88',[0,0,0]),('passed',False),('rx_hex','00 '*11),
                                ('expected_q88',[0,0,0]),('actual_q88',[-46.0,60,34])]:
                bad=copy.deepcopy(item);bad[field]=value
                path.write_text(json.dumps(bad)+'\n')
                self.assertFalse(offline.validate_capture(path,data))
            path.write_text(json.dumps(item)+'\n'+json.dumps(item)+'\n')
            self.assertFalse(offline.validate_capture(path,data))
            path.write_text('')
            self.assertFalse(offline.validate_capture(path,data))

    def test_hardware_suite_with_simulated_serial_fixture(self):
        data=offline.load_vectors(offline.DEFAULT_VECTORS)
        responses={bytes.fromhex(c['tx_hex']):bytes.fromhex(c['rx_hex']) for c in data['cases']}
        class Link:
            writes=[]
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def reset_input_buffer(self):self.pending=b''
            def write(self,packet):
                self.writes.append(packet);self.pending=responses[packet];return len(packet)
            def flush(self):pass
            def read(self,size):
                chunk=self.pending[:size];self.pending=self.pending[size:];return chunk
        with tempfile.TemporaryDirectory() as tmp,patch.object(hardware.serial,'Serial',return_value=Link()),patch('builtins.print'):
            path=Path(tmp)/'capture.jsonl'
            self.assertTrue(hardware.run('TEST',9600,2,.1,offline.DEFAULT_VECTORS,path))
            self.assertEqual(len(Link.writes),32)
            self.assertTrue(offline.validate_capture(path,data,32))

    def test_main_test_marks_numeric_mismatch_failed(self):
        class Link:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        response=uart.parse_response_packet(bytes.fromhex('5a a5 02 06 d2 ff 3c 00 22 00 61'))
        with tempfile.TemporaryDirectory() as tmp,patch.object(uart.serial,'Serial',return_value=Link()), \
             patch.object(uart,'exchange_q88',return_value=(response,100)),patch('builtins.print'):
            path=Path(tmp)/'wrong.jsonl'
            self.assertFalse(uart.run_uart_test('TEST',9600,1,expected=[0,0,0],jsonl=path))
            self.assertFalse(json.loads(path.read_text())['passed'])
            with self.assertRaises(FileExistsError):uart.run_uart_test('TEST',9600,1,jsonl=path)

    def test_hardware_valid_crc_wrong_model_is_failure(self):
        data=offline.load_vectors(offline.DEFAULT_VECTORS)
        responses=[(uart.parse_response_packet(bytes.fromhex(c['rx_hex'])),100)
                   for c in data['cases']]
        responses[0]=responses[1]
        class Link:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with tempfile.TemporaryDirectory() as tmp,patch.object(hardware.serial,'Serial',return_value=Link()), \
             patch.object(uart,'exchange_q88',side_effect=responses),patch('builtins.print'):
            path=Path(tmp)/'capture.jsonl'
            self.assertFalse(hardware.run('TEST',9600,1,.1,offline.DEFAULT_VECTORS,path))
            self.assertFalse(offline.validate_capture(path,data,16))

    def test_portable_installer_and_repeat_backup(self):
        root=SCRIPTS.parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)
            scripts=destination/'src/igor_pipeline/scripts'
            scripts.mkdir(parents=True)
            (scripts/'uart_test.py').write_text('# previous version\n')
            for _ in range(2):
                result=subprocess.run([sys.executable,str(root/'tools/install_igor_uart_q88.py'),str(destination)],
                                      capture_output=True,text=True,check=True)
                self.assertIn('PASS installed all Q8.8 tools',result.stdout)
            self.assertEqual((scripts/'uart_test.py').read_bytes(),(SCRIPTS/'uart_test.py').read_bytes())
            self.assertEqual(len(list(scripts.glob('uart_test.py.backup-*'))),1)
            self.assertTrue((scripts/'uart_validate_hardware_q88.py').is_file())

if __name__=='__main__':unittest.main()
