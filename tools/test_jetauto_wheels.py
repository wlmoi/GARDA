#!/usr/bin/env python3
"""Short individual, pair and four-wheel pulses; dry-run default."""
import argparse
from itertools import combinations
import json
import math
from pathlib import Path
import signal
import struct
import time


def crc8(data):
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ (0x8c if crc & 1 else 0)
    return crc


def packet(speeds):
    if len(speeds) != 4 or any(not math.isfinite(x) or abs(x) > 1 for x in speeds):
        raise ValueError('Four finite wheel speeds within +/-1 RPS required')
    body = bytes([3, 22, 1, 4]) + b''.join(struct.pack('<Bf', i, x) for i, x in enumerate(speeds))
    return b'\xaa\x55' + body + bytes([crc8(body)])


def make_plans(rps, groups):
    labels = ['M1 front-left', 'M2 rear-left', 'M3 front-right', 'M4 rear-right']
    plans = []
    for group, count in [('singles', 1), ('pairs', 2), ('four', 4)]:
        if group not in groups:
            continue
        for indices in combinations(range(4), count):
            speeds = [0.] * 4
            for i in indices:
                speeds[i] = rps if i < 2 else -rps
            plans.append((' + '.join(labels[i] for i in indices), speeds))
    return plans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='/dev/serial/by-id/usb-1a86_USB_Single_Serial_5917012181-if00')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--wheels-raised', action='store_true')
    parser.add_argument('--rps', type=float, default=.5)
    parser.add_argument('--seconds', type=float, default=.75)
    parser.add_argument('--groups', nargs='+', choices=['singles', 'pairs', 'four'],
                        default=['singles'], help='Test singles, all six pairs, and/or all four together')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not math.isfinite(args.rps) or not 0 < args.rps <= 1 or not math.isfinite(args.seconds) or not 0 < args.seconds <= 2:
        parser.error('Use 0 < rps <= 1 and 0 < seconds <= 2')
    if args.run and not args.wheels_raised:
        parser.error('--run requires --wheels-raised')
    plans = make_plans(args.rps, args.groups)
    for label, speeds in plans:
        print(label, speeds, flush=True)
    if not args.run:
        print('DRY RUN: no serial port opened')
        return
    import serial
    from serial.tools import list_ports
    resolved = str(Path(args.port).resolve())
    ports = [p for p in list_ports.comports() if p.device == resolved]
    if len(ports) != 1 or (ports[0].vid, ports[0].pid, ports[0].serial_number) != (0x1a86, 0x55d4, '5917012181'):
        raise RuntimeError('Expected JetAuto STM32 identity not present; no command sent')
    events = []
    report = {'port': resolved, 'baud': 1000000, 'rps': args.rps, 'seconds': args.seconds,
              'groups': args.groups, 'planned_pulses': len(plans),
              'physical_observation': 'pending user observation; host writes do not prove wheel rotation',
              'events': events, 'final_stop_sent': False}
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, interrupted)
    with args.output.open('x') as log:
        connection = serial.Serial(None, 1000000, timeout=.01, write_timeout=.1, exclusive=True)
        connection.port = args.port
        connection.dtr = False
        connection.rts = False
        def send(speeds):
            raw = packet(speeds)
            if connection.write(raw) != len(raw):
                raise RuntimeError('Short motor packet write')
            connection.flush()
        def stop():
            for _ in range(3):
                send([0.] * 4)
                time.sleep(.02)
        try:
            connection.open()
            stop()
            for label, speeds in plans:
                print('NOW:', label, 'for', args.seconds, 'seconds', flush=True)
                events.append({'wheel': label, 'speeds': speeds, 'start_monotonic': time.monotonic()})
                try:
                    deadline = time.monotonic() + args.seconds
                    while time.monotonic() < deadline:
                        send(speeds)
                        time.sleep(min(.05, max(0, deadline-time.monotonic())))
                finally:
                    stop()
                    events[-1]['stop_monotonic'] = time.monotonic()
                    print('STOP', flush=True)
                time.sleep(.75)
        finally:
            try:
                if connection.is_open:
                    stop()
                    report['final_stop_sent'] = True
            finally:
                connection.close()
                json.dump(report, log, indent=2)
                log.write('\n')
    print(f'Completed {len(events)} wheel-group pulses; final STOP sent. Confirm physical movement.', flush=True)


if __name__ == '__main__':
    main()
