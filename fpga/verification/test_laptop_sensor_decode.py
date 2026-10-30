"""Protocol field checks independent of physical sensor acceptance."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from laptop_sensor_preflight import decode_node


class A1DecodeTests(unittest.TestCase):
    def test_standard_node_flags_angle_and_distance_units(self):
        packet = bytes([(10 << 2) | 1]) + ((800 << 1) | 1).to_bytes(2, 'little') + (5000).to_bytes(2, 'little')
        node = decode_node(packet)
        self.assertTrue(node['start'])
        self.assertEqual(node['quality'], 10)
        self.assertEqual(node['angle_deg'], 12.5)
        self.assertEqual(node['distance_m'], 1.25)

    def test_bad_flags_truncation_and_invalid_angle_rejected(self):
        for packet in (b'\x00\x01\x00\x00\x00', b'\x01\x00\x00\x00\x00', b'\x01',
                       b'\x01' + ((360*64 << 1) | 1).to_bytes(2, 'little') + b'\x00\x00'):
            with self.assertRaises(ValueError):
                decode_node(packet)


if __name__ == '__main__':
    unittest.main()
