"""Acquisition integrity tests use a serial fixture; they are not board evidence."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_hardware_safety as capture


def response(opcode, value):
    body = bytes([0x5a, opcode]) + struct.pack('<I', value)
    return body + bytes([capture.crc8(body), 0xa5])


class SerialFixture:
    def __init__(self, frames):
        self.frames = iter(frames)
        self.writes = []
        self.short_write = False

    def write(self, frame):
        self.writes.append(frame)
        return len(frame) - int(self.short_write)

    def flush(self):
        pass

    def read(self, count):
        return next(self.frames)


def sample():
    status = 2 << 8
    return capture.snapshot(SerialFixture([
        response(7, status), response(15, 3), response(16, 2),
        response(14, 0), response(16, 2), response(15, 3), response(7, status),
    ]))


class AcquisitionTests(unittest.TestCase):
    def test_crc_reference(self):
        # CRC-8/SMBUS check value for ASCII 123456789.
        self.assertEqual(capture.crc8(b'123456789'), 0xf4)

    def test_exact_request_and_response(self):
        link = SerialFixture([response(7, 0x12345678)])
        value, raw = capture.transact(link, 7)
        self.assertEqual(value, 0x12345678)
        self.assertEqual(raw, response(7, value).hex())
        frame = link.writes[0]
        self.assertEqual(frame[:6], b'\xa5\x07\0\0\0\0')
        self.assertEqual(frame[6:], bytes([capture.crc8(frame[:6]), 0x5a]))

    def test_short_write_rejected(self):
        link = SerialFixture([response(7, 0)])
        link.short_write = True
        with self.assertRaisesRegex(RuntimeError, 'Incomplete serial write'):
            capture.transact(link, 7)

    def test_corruption_truncation_opcode_and_markers_rejected(self):
        good = response(7, 0)
        invalid = [b'', good[:7], response(14, 0), b'\x00' + good[1:],
                   good[:6] + bytes([good[6] ^ 1]) + good[7:], good[:7] + b'\x00']
        for frame in invalid:
            with self.subTest(frame=frame.hex()):
                with self.assertRaises(RuntimeError):
                    capture.transact(SerialFixture([frame]), 7)

    def test_stable_fault_and_logger_checked(self):
        row = sample()
        self.assertTrue(capture.validate_sample(row, True, 2))
        self.assertFalse(row['sample_atomic'])
        self.assertEqual(row['raw_frame_opcodes'], [7, 15, 16, 14, 16, 15, 7])

    def test_unstable_brackets_are_not_accepted(self):
        for key in ('status_unchanged', 'logger_unchanged'):
            row = sample()
            row[key] = False
            self.assertFalse(capture.validate_sample(row, True, 2))

    def test_nonzero_outputs_and_enabled_zero_rejected(self):
        for key in ('v_command', 'omega_command', 'motor_enable'):
            row = sample()
            if key == 'motor_enable':
                row['status_after'][key] = True
            else:
                row[key] = -1 if key == 'omega_command' else 1
            with self.subTest(signal=key):
                with self.assertRaisesRegex(RuntimeError, 'Fail-closed'):
                    capture.validate_sample(row, True, 2)

    def test_current_fault_retained_cause_and_event_count_required(self):
        for target, key in [('status_after', 'fault_code'), (None, 'last_fault'), (None, 'event_count')]:
            row = sample()
            (row[target] if target else row)[key] = 0
            with self.subTest(key=key):
                with self.assertRaises(RuntimeError):
                    capture.validate_sample(row, True, 2)

    def test_signed_omega_boundaries(self):
        for omega in (-64, -1, 0, 63):
            status = (2 << 8)
            frames = [response(7, status), response(15, 3), response(16, 2),
                      response(14, ((omega & 127) << 5) | 31), response(16, 2),
                      response(15, 3), response(7, status)]
            row = capture.snapshot(SerialFixture(frames))
            self.assertEqual((row['v_command'], row['omega_command']), (31, omega))

    def test_logger_change_during_sampling_is_detected(self):
        frames = [response(7, 512), response(15, 3), response(16, 2),
                  response(14, 0), response(16, 2), response(15, 4), response(7, 512)]
        row = capture.snapshot(SerialFixture(frames))
        self.assertTrue(row['status_unchanged'])
        self.assertFalse(row['logger_unchanged'])
        self.assertFalse(capture.validate_sample(row, True, 2))


if __name__ == '__main__':
    unittest.main(verbosity=2)
