import importlib.util
import struct
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('uart_test', Path(__file__).parents[1] / 'src/igor_pipeline/scripts/uart_test.py')
uart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uart)

class UARTTests(unittest.TestCase):
    def response(self):
        body = bytes.fromhex('02 06') + struct.pack('<3h', -256, 0, 256)
        return bytes.fromhex('5a a5') + body + bytes([uart.crc8_maxim(body)])

    def test_wire_contract(self):
        self.assertEqual(uart.crc8_maxim(b'123456789'), 0xa1)
        packet = uart.build_sensor_packet(0, [0.8] * 64 + [0.] * 10)
        self.assertEqual(len(packet), 153)
        self.assertEqual(packet[:4], bytes.fromhex('5a a5 01 94'))
        self.assertEqual(struct.unpack('<74h', packet[4:-1]), (205,) * 64 + (0,) * 10)
        self.assertEqual(packet[-1], uart.crc8_maxim(packet[2:-1]))
        self.assertEqual(uart.parse_response_packet(self.response())['ai_results'], [-1, 0, 1])

    def test_resync_corruption_and_fragments(self):
        damaged = bytearray(self.response())
        damaged[-1] ^= 1
        data = bytearray(b'noise\x5a' + damaged + self.response())
        class Stream:
            def read(self, size):
                value = bytes(data[:1])
                del data[:1]
                return value
        self.assertEqual(uart.read_response(Stream(), 0.2)['ai_results'], [-1, 0, 1])

    def test_reject_invalid(self):
        for packet in (b'', self.response()[:-1], b'x' + self.response()[1:]):
            with self.assertRaises(ValueError):
                uart.parse_response_packet(packet)
        for obs in ([0.] * 73, [-0.1] * 74, [float('nan')] * 74):
            with self.assertRaises(ValueError):
                uart.build_sensor_packet(0, obs)
        class Empty:
            def read(self, size): return b''
        with self.assertRaises(ValueError):
            uart.read_response(Empty(), 0.001)

if __name__ == '__main__':
    unittest.main()
