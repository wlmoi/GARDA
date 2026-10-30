#!/usr/bin/env python3
"""Test DE10-Nano source-policy UART (9600 or 921600, matching FPGA image).

Request: 5a a5 01 94 + 74 little-endian Q8.8 words + CRC8 Maxim.
Response: 5a a5 02 06 + 3 little-endian Q8.8 words + CRC8 Maxim.
The CRC covers opcode, length and payload. Protocol V2/CRC32 is for the
HPS/UDP service, not this FPGA image. This test does not drive motors.
"""
import argparse
import math
import struct
import time
import hashlib
import json
import sys
from pathlib import Path

import serial

SENSOR_PKT_SIZE = 153
RESP_PKT_SIZE = 11
RESPONSE_HEADER = bytes.fromhex('5a a5 02 06')
DEFAULT_OBS_Q88 = [205] * 64 + [0] * 10
DEFAULT_EXPECTED_Q88 = [-46, 60, 34]


def format_q88(values):
    return (f'Q8.8={list(values)} | HEX16={[f"0x{v & 0xffff:04X}" for v in values]} '
            f'| decimal={[v / 256 for v in values]}')


def build_sensor_packet_q88(obs):
    """Accept signed raw Q8.8 integers; no float conversion on this path."""
    if not isinstance(obs, (list, tuple)) or len(obs) != 74:
        raise ValueError('Expected 74 Q8.8 integers')
    for i, value in enumerate(obs):
        if type(value) is not int or not (0 if i < 64 else -256) <= value <= 256:
            raise ValueError(f'Q8.8 observation {i}: expected integer in '
                             f'[{0 if i < 64 else -256}, 256], got {value!r}')
    body = bytes([1, 148]) + struct.pack('<74h', *obs)
    return bytes.fromhex('5a a5') + body + bytes([crc8_maxim(body)])


def crc8_maxim(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x8c if crc & 1 else 0)
    return crc


def build_sensor_packet(frame_id, obs):
    # frame_id is a local counter; the fabric protocol has no sequence field.
    if len(obs) != 74:
        raise ValueError('Expected 74 observations')
    for i, value in enumerate(obs):
        if not math.isfinite(value) or not (0 if i < 64 else -1) <= value <= 1:
            raise ValueError(f'Observation {i} is outside the FPGA normalized domain')
    return build_sensor_packet_q88([round(v * 256) for v in obs])


def parse_response_packet(raw):
    if len(raw) != RESP_PKT_SIZE:
        raise ValueError(f'Expected 11 response bytes, got {len(raw)}')
    if raw[:4] != RESPONSE_HEADER:
        raise ValueError(f'Bad response header: {raw[:4].hex(" ")}')
    if raw[-1] != crc8_maxim(raw[2:-1]):
        raise ValueError(f'CRC8 mismatch: {raw.hex(" ")}')
    values = struct.unpack('<3h', raw[4:10])
    if any(abs(v) > 256 for v in values):
        raise ValueError(f'Residual outside [-1, 1]: {values}')
    return {'q8_8_results': list(values), 'ai_results': [v / 256 for v in values],
            'rx_hex': raw.hex(' ')}


def read_response(ser, timeout):
    """Resynchronize after noise and collect fragmented reads within one deadline."""
    deadline = time.monotonic() + timeout
    pending = bytearray()
    diagnostic = bytearray()
    while time.monotonic() < deadline:
        ser.timeout = min(0.02, max(0, deadline - time.monotonic()))
        chunk = ser.read(1)
        if not chunk:
            continue
        diagnostic.extend(chunk)
        pending.extend(chunk)
        while pending and not RESPONSE_HEADER.startswith(pending[:4]):
            del pending[0]
        if len(pending) == RESP_PKT_SIZE:
            try:
                return parse_response_packet(bytes(pending))
            except ValueError:
                del pending[0]
                while pending and not RESPONSE_HEADER.startswith(pending[:4]):
                    del pending[0]
    raise ValueError(f'Timeout/no valid CRC8 response; received {len(diagnostic)} bytes; '
                     f'RX first 64 bytes: {diagnostic[:64].hex(" ") or "(none)"}')


def exchange_q88(ser, observation, timeout=1.0):
    packet = build_sensor_packet_q88(observation)
    ser.reset_input_buffer()
    start = time.perf_counter()
    if ser.write(packet) != len(packet):
        raise serial.SerialException('Incomplete UART write')
    ser.flush()
    response = read_response(ser, timeout)
    return response, (time.perf_counter() - start) * 1e6


def run_uart_test(port, baud, iterations, timeout=1.0, observation=None,
                  expected=None, dump_hex=False, jsonl=None):
    source = Path(__file__).resolve()
    print(f'Script: {source} | SHA256: {hashlib.sha256(source.read_bytes()).hexdigest()}')
    print(f'IGOR source-policy UART | {port} | {baud} baud | TX=153B RX=11B CRC8 Maxim')
    obs = DEFAULT_OBS_Q88 if observation is None else observation
    build_sensor_packet_q88(obs)
    print(f'TX Q8.8: {obs}')
    if expected is not None:
        print(f'Expected: {format_q88(expected)}')
    received = 0
    validated = 0
    latencies = []
    from contextlib import ExitStack
    with ExitStack() as stack:
        log = stack.enter_context(Path(jsonl).open('x', encoding='utf-8')) if jsonl else None
        options = {'exclusive': True} if sys.platform.startswith('linux') else {}
        ser = stack.enter_context(serial.Serial(port, baud, timeout=0.02, write_timeout=timeout,
                       bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                       stopbits=serial.STOPBITS_ONE, xonxoff=False, rtscts=False,
                       dsrdtr=False, **options))
        for frame_id in range(iterations):
            record = {'frame_id': frame_id, 'baud': baud, 'format': 'Q8.8',
                      'observation_q88': obs, 'expected_q88': expected}
            try:
                response, elapsed = exchange_q88(ser, obs, timeout)
            except ValueError as exc:
                print(f'[Frame {frame_id:4d}] FAIL: {exc}')
                record.update(passed=False, error=str(exc))
                if log:
                    log.write(json.dumps(record) + '\n'); log.flush()
                continue
            received += 1
            latencies.append(elapsed)
            passed = expected is None or response['q8_8_results'] == expected
            validated += int(passed)
            record.update(actual_q88=response['q8_8_results'], rx_hex=response['rx_hex'],
                          rtt_us=elapsed, passed=passed)
            label = ('PASS' if expected is not None else 'CRC_OK') if passed else 'MISMATCH'
            print(f'[Frame {frame_id:4d}] {label} | '
                  f'{format_q88(response["q8_8_results"])} | RTT: {elapsed:.0f} us')
            if dump_hex:
                print(f'  TX: {build_sensor_packet_q88(obs).hex(" ")}\n  RX: {response["rx_hex"]}')
            if log:
                log.write(json.dumps(record) + '\n'); log.flush()
    print(f'Frames sent: {iterations} | received: {received} | dropped: {iterations-received}')
    print(f'{"Validation" if expected is not None else "Transport"} passed: {validated}/{iterations}')
    if latencies:
        print(f'Mean RTT: {sum(latencies)/len(latencies):.0f} us (includes UART transfer)')
    if received != iterations:
        print('Check image/baud match and LED7:4 error code. Release KEY1 and press/release KEY0.')
    return validated == iterations


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='/dev/ttyTHS1')
    parser.add_argument('--baud', type=int, default=9600)
    parser.add_argument('--iter', type=int, default=50)
    parser.add_argument('--timeout', type=float, default=1.0)
    parser.add_argument('--obs-q88', type=Path, help='JSON array of 74 raw signed Q8.8 integers')
    parser.add_argument('--expected-q88', help='Three raw expected integers, e.g. --expected-q88=-46,60,34')
    parser.add_argument('--dump-hex', action='store_true')
    parser.add_argument('--jsonl', type=Path, help='New JSONL capture file; existing files are preserved')
    parser.add_argument('--self-check', action='store_true',
                        help='Verify protocol locally without opening a UART')
    args = parser.parse_args()
    if args.self_check:
        assert crc8_maxim(b'123456789') == 0xa1
        packet = build_sensor_packet(0, [0.8] * 64 + [0.] * 10)
        assert len(packet) == 153 and packet[:4] == bytes.fromhex('5a a5 01 94')
        assert packet[-1] == crc8_maxim(packet[2:-1])
        body = bytes.fromhex('02 06') + struct.pack('<3h', -256, 0, 256)
        response = bytes.fromhex('5a a5') + body + bytes([crc8_maxim(body)])
        assert parse_response_packet(response)['ai_results'] == [-1, 0, 1]
        print(f'PASS: source-policy-v1 | baud={args.baud} | TX=153B RX=11B | CRC8 Maxim')
        print(f'Script: {Path(__file__).resolve()}')
        raise SystemExit(0)
    if args.iter <= 0 or args.baud <= 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--iter, --baud and --timeout must be positive')
    if args.baud not in (9600, 921600):
        parser.error('Use --baud 9600 for the 9600 image or --baud 921600 for the original image')
    try:
        obs = json.loads(args.obs_q88.read_text()) if args.obs_q88 else None
        expected = ([int(v) for v in args.expected_q88.split(',')]
                    if args.expected_q88 else DEFAULT_EXPECTED_Q88 if obs is None else None)
        if expected is not None and (len(expected) != 3 or any(abs(v) > 256 for v in expected)):
            raise ValueError('Expected three Q8.8 integers in [-256, 256]')
        ok = run_uart_test(args.port, args.baud, args.iter, args.timeout, obs,
                           expected, args.dump_hex, args.jsonl)
    except ValueError as exc:
        parser.exit(1, f'Invalid Q8.8 data: {exc}\n')
    except (serial.SerialException, OSError) as exc:
        parser.exit(1, f'UART error: {exc}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'UART test interrupted\n')
    raise SystemExit(0 if ok else 1)
