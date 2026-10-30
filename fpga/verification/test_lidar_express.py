import functools
import operator
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lidar_express import validate, decode_pair


def capsule(angle, distance=1, correction=0, reset=False):
    b = bytearray(84)
    b[2:4] = (round(angle*64) | (0x8000 if reset else 0)).to_bytes(2, 'little')
    value = round(distance*4000) | (correction >> 4)
    for i in range(4, 84, 5):
        b[i:i+2] = value.to_bytes(2, 'little')
        b[i+2:i+4] = value.to_bytes(2, 'little')
        b[i+4] = (correction & 15) * 17
    check = functools.reduce(operator.xor, b[2:], 0)
    b[0], b[1] = 0xa0 | (check & 15), 0x50 | (check >> 4)
    return bytes(b)


class ExpressTest(unittest.TestCase):
    def test_known_32_samples_distance_and_spacing(self):
        rows = decode_pair(capsule(10), capsule(42))
        self.assertEqual(len(rows), 32)
        self.assertEqual([r['angle_deg'] for r in rows], list(range(10, 42)))
        self.assertTrue(all(r['distance_m'] == 1 for r in rows))
        self.assertFalse(any(r['start'] for r in rows))

    def test_wrap_crossing_and_q3_angle_correction(self):
        rows = decode_pair(capsule(350, correction=8), capsule(22))
        self.assertEqual(rows[0]['angle_deg'], 349)
        self.assertEqual(rows[10]['angle_deg'], 359)
        self.assertEqual(rows[11]['angle_deg'], 0)
        self.assertEqual(sum(r['start'] for r in rows), 1)

    def test_high_correction_bits_and_zero_distance(self):
        rows = decode_pair(capsule(10, correction=32), capsule(42))
        self.assertEqual(rows[0]['angle_deg'], 6)
        rows = decode_pair(capsule(10, distance=0), capsule(42))
        self.assertTrue(all(r['quality'] == 0 for r in rows))

    def test_corruption_and_truncation_rejected(self):
        bad = bytearray(capsule(10)); bad[25] ^= 1
        for value in (bad, capsule(10)[:-1], bytes(84), capsule(361)):
            with self.assertRaises(ValueError):
                validate(value)

    def test_reset_discards_previous_capsule(self):
        self.assertEqual(decode_pair(capsule(10), capsule(42, reset=True)), [])


if __name__ == '__main__':
    unittest.main()
