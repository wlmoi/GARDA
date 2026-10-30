#!/usr/bin/env python3
"""Jetson UART isolation test. Default mode NEVER transmits.

Idle: keep normal FPGA wiring and run --mode idle.
Loopback: DISCONNECT FPGA TX/RX from Jetson, then join the Jetson UART's
TX directly to its RX. Use --mode loopback only with that isolated jumper.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

import serial


def summarize(data):
    return {'bytes': len(data), 'zero_bytes': data.count(0),
            'zero_fraction': data.count(0) / len(data) if data else 0,
            'most_common': [(f'{v:02x}', n) for v, n in Counter(data).most_common(8)],
            'first_128_hex': data[:128].hex(' ')}


def collect(port, seconds, limit=262144):
    end = time.monotonic() + seconds
    data = bytearray()
    while time.monotonic() < end and len(data) < limit:
        port.timeout = min(0.02, max(0, end - time.monotonic()))
        data.extend(port.read(min(max(port.in_waiting, 1), 4096, limit - len(data))))
    return bytes(data)


def open_port(name, baud):
    options = dict(port=name, baudrate=baud, timeout=0.02, write_timeout=2,
                   bytesize=8, parity='N', stopbits=1, xonxoff=False,
                   rtscts=False, dsrdtr=False)
    if os.name == 'posix':
        options['exclusive'] = True
    return serial.Serial(**options)


def environment(port):
    info = {'port': port, 'resolved_port': os.path.realpath(port)}
    for name in ('model', 'compatible'):
        path = Path('/proc/device-tree') / name
        if path.exists():
            info[name] = path.read_bytes().replace(b'\0', b' ').decode(errors='replace').strip()
    for name in ('cmdline',):
        path = Path('/proc') / name
        if path.exists():
            info[name] = path.read_text().strip()
    if shutil.which('fuser'):
        result = subprocess.run(['fuser', '-v', port], capture_output=True, text=True, timeout=5)
        info['port_owners_before_open'] = result.stdout + result.stderr
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', default='/dev/ttyTHS1')
    parser.add_argument('--baud', type=int, default=921600)
    parser.add_argument('--mode', choices=('idle', 'loopback'), default='idle')
    parser.add_argument('--seconds', type=float, default=2)
    parser.add_argument('--output', help='New JSON report path; existing files are preserved')
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 30 or args.baud <= 0:
        parser.error('Use positive baud and 0 < seconds <= 30')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report = {'utc': stamp, 'mode': args.mode, 'environment': environment(args.port), 'checks': []}
    output = Path(args.output or f'uart_{args.mode}_{stamp}.json')
    # Reserve output before any writes to UART, preventing a lost report.
    with output.open('x', encoding='utf-8') as destination:
        try:
            bauds = [args.baud] if args.mode == 'idle' else [115200, 921600]
            for baud in bauds:
                with open_port(args.port, baud) as port:
                    port.reset_input_buffer()
                    idle = collect(port, args.seconds)
                    check = {'baud': baud, 'settings': port.get_settings(), 'idle': summarize(idle)}
                    report['checks'].append(check)
                    print(f'{baud}: no-TX idle RX = {len(idle)} bytes, zeros = {idle.count(0)}')
                    if args.mode == 'idle':
                        print('UNEXPECTED activity: investigate signal/source/port owner.' if idle else
                              'Quiet RX. Next isolate Jetson TX/RX for loopback testing.')
                        continue
                    if idle:
                        check['loopback_pass'] = False
                        check['reason'] = 'Background RX before transmission; loopback not attempted'
                        print(check['reason'])
                        continue
                    payload = bytes(range(256)) + bytes([0x55, 0xaa, 0, 0xff]) * 64
                    count = port.write(payload)
                    port.flush()
                    received = collect(port, args.seconds)
                    check.update(tx_bytes=count, rx=summarize(received),
                                 loopback_pass=(count == len(payload) and received == payload))
                    print(f'{baud}: isolated loopback {"PASS" if check["loopback_pass"] else "FAIL"}; '
                          f'TX={count}, RX={len(received)} (expected 512 exact bytes)')
        except (OSError, serial.SerialException) as exc:
            report['error'] = str(exc)
            print(f'UART diagnostic error: {exc}')
        finally:
            json.dump(report, destination, indent=2)
            destination.write('\n')
            print(f'Report: {output.resolve()}')
    if 'error' in report:
        return 1
    if args.mode == 'loopback':
        return 0 if all(c.get('loopback_pass') for c in report['checks']) else 1
    return 0 if all(c['idle']['bytes'] == 0 for c in report['checks']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
