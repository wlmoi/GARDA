#!/usr/bin/env python3
"""Validate Q8.8 fixtures offline, or independently validate a JSONL UART capture."""
import argparse
import json
from pathlib import Path
import struct
import sys

import uart_test as uart

DEFAULT_VECTORS=Path(__file__).with_name('uart_q88_vectors.json')

def load_vectors(path):
    data=json.loads(Path(path).read_text())
    if data.get('schema')!=1 or data.get('format')!='Q8.8' or data.get('fractional_bits')!=8:
        raise ValueError('Expected schema 1 / Q8.8 / 8 fractional bits')
    cases=data.get('cases',[])
    if not cases:
        raise ValueError('No validation cases')
    names=set()
    for case in cases:
        if case['name'] in names:
            raise ValueError('Duplicate case name')
        names.add(case['name'])
        tx=uart.build_sensor_packet_q88(case['observation_q88'])
        expected=case['expected_q88']
        if len(expected)!=3 or any(type(v) is not int or not -256<=v<=256 for v in expected):
            raise ValueError(f'Invalid expected Q8.8 values: {case["name"]}')
        if tx.hex(' ')!=case['tx_hex'] or list(struct.unpack('<74h',tx[4:-1]))!=case['observation_q88']:
            raise ValueError(f'TX encoding mismatch: {case["name"]}')
        rx=uart.parse_response_packet(bytes.fromhex(case['rx_hex']))
        if rx['q8_8_results']!=expected:
            raise ValueError(f'RX/expected mismatch: {case["name"]}')
    if uart.crc8_maxim(b'123456789')!=0xa1:
        raise ValueError('CRC8 standard check failed')
    return data


def validate_capture(path,data,expected_frames=None):
    oracle={tuple(c['observation_q88']):c['expected_q88'] for c in data['cases']}
    count=0; failures=0; ids=set()
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            count+=1
            try:
                item=json.loads(line)
                obs=item['observation_q88']
                uart.build_sensor_packet_q88(obs)
                expected=oracle[tuple(obs)]
                frame=item['frame_id']
                if type(frame) is not int or frame<0 or frame in ids:
                    raise ValueError('Invalid/duplicate frame_id')
                ids.add(frame)
                if item.get('format')!='Q8.8' or item.get('baud') not in (9600,921600):
                    raise ValueError('Invalid format/baud metadata')
                if item.get('passed') is not True or 'error' in item:
                    raise ValueError('Transaction was marked failed')
                actual=uart.parse_response_packet(bytes.fromhex(item['rx_hex']))['q8_8_results']
                if any(type(v) is not int for v in item['actual_q88']):
                    raise ValueError('actual_q88 must contain integers')
                if actual!=expected or item['actual_q88']!=actual:
                    raise ValueError(f'Expected {expected}, wire decoded {actual}, logged {item["actual_q88"]}')
                if item.get('expected_q88') is not None and item['expected_q88']!=expected:
                    raise ValueError('Logged expected result differs from independent fixture')
            except (ValueError,KeyError,TypeError,struct.error) as exc:
                failures+=1
                print(f'Line {count}: FAIL {exc}')
    if not count or (expected_frames is not None and count!=expected_frames):
        failures+=1
        print(f'FAIL frame count: {count}, expected {expected_frames or "at least one"}')
    print(f'Capture: {count} frames, {failures} validation failures')
    return failures==0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors',type=Path,default=DEFAULT_VECTORS)
    parser.add_argument('--capture',type=Path)
    parser.add_argument('--expected-frames',type=int)
    args=parser.parse_args()
    try:
        data=load_vectors(args.vectors)
        print(f'PASS offline: {len(data["cases"])} Q8.8 cases, TX/RX layout, signed values, CRC8')
        if args.capture:
            return 0 if validate_capture(args.capture,data,args.expected_frames) else 1
        for case in data['cases']:
            print(f'{case["name"]}: {uart.format_q88(case["expected_q88"])}')
        return 0
    except (OSError,ValueError,KeyError,TypeError,struct.error) as exc:
        print(f'FAIL: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
