import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('diagnose', Path(__file__).parents[1] / 'tools/uart_diagnose.py')
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)


class DiagnosticTests(unittest.TestCase):
    def run_diagnostic(self, mode, captures):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'report.json'
            port = Mock()
            port.__enter__ = Mock(return_value=port)
            port.__exit__ = Mock(return_value=False)
            port.get_settings.return_value = {'baudrate': 921600}
            port.write.side_effect = len
            argv = ['uart_diagnose.py', '--mode', mode, '--output', str(output)]
            with patch('sys.argv', argv), patch.object(diag, 'environment', return_value={}), \
                 patch.object(diag, 'open_port', return_value=port), \
                 patch.object(diag, 'collect', side_effect=captures), patch('builtins.print'):
                code = diag.main()
            return code, port, json.loads(output.read_text())

    def test_idle_never_transmits_and_records_noise(self):
        code, port, report = self.run_diagnostic('idle', [b'\x00' * 300])
        port.write.assert_not_called()
        self.assertEqual(code, 1)
        self.assertEqual(report['checks'][0]['idle']['zero_fraction'], 1)

    def test_exact_loopback_both_bauds(self):
        payload = bytes(range(256)) + bytes([0x55, 0xaa, 0, 0xff]) * 64
        code, port, report = self.run_diagnostic('loopback', [b'', payload, b'', payload])
        self.assertEqual(code, 0)
        self.assertEqual(port.write.call_count, 2)
        self.assertEqual([c['baud'] for c in report['checks']], [115200, 921600])

    def test_noise_blocks_loopback_transmission(self):
        code, port, _ = self.run_diagnostic('loopback', [b'noise', b'noise'])
        self.assertEqual(code, 1)
        port.write.assert_not_called()

    def test_corrupted_echo_fails(self):
        code, _, _ = self.run_diagnostic('loopback', [b'', b'wrong', b'', b'wrong'])
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
