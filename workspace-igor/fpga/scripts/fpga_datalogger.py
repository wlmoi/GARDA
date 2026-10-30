"""Read FPGA telemetry over USB-Blaster JTAG; never programs or sends observations."""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
import re
import time

from verify_board_jtag import Jtag, ROOT


def parse_snapshot(text):
    if 'JP1 pins 1/2' not in text or not text.endswith('\r\n> '):
        raise ValueError('Wrong FPGA image or incomplete JTAG snapshot')
    values = dict(re.findall(r'\b(mode|stop|pin|accepted|rejected|error|cycles|seq|a0|a1|a2)=([A-Z0-9]+)', text))
    required = {'mode', 'stop', 'pin', 'accepted', 'rejected', 'error', 'cycles', 'seq', 'a0', 'a1', 'a2'}
    if set(values) != required or values['mode'] not in ('I', 'E'):
        raise ValueError('Incomplete FPGA telemetry fields')
    result = {k: int(v, 16) for k, v in values.items() if k != 'mode'}
    result['mode'] = values['mode']
    for k in ('a0', 'a1', 'a2'):
        if not 0 <= result[k] <= 65535:
            raise ValueError('Action outside 16-bit range')
        if result[k] >= 32768:
            result[k] -= 65536
    return result


def classify(previous, current):
    if previous is None:
        return 'existing_result' if current['seq'] else 'no_result', None
    if any(current[k] < previous[k] for k in ('seq', 'accepted', 'rejected')):
        return 'counter_discontinuity_reset_or_wrap', None
    delta = current['seq'] - previous['seq']
    return ('new_result' if delta else 'unchanged'), max(0, delta - 1)


class PassiveJtag(Jtag):
    def snapshot(self):
        # Only q: no echo/inference mode switch and no core input injection.
        if self.write(self.h, b'q', 1) != 1:
            raise OSError('JTAG status request failed')
        self.flush(self.h)
        import ctypes as C
        buffer = C.create_string_buffer(4096)
        data = bytearray()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            n = self.read(self.h, buffer, len(buffer))
            if n < 0:
                raise OSError('JTAG disconnected')
            data.extend(buffer.raw[:n])
            if data.endswith(b'\r\n> '):
                raw = data.decode('ascii', errors='strict')
                return parse_snapshot(raw), raw
            time.sleep(.005)
        raise TimeoutError('No complete JTAG status; close other JTAG terminals and check monitor SOF')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--location', default='BELUM_DIISI', help='Manual site/room/robot location label')
    parser.add_argument('--prompt-location', action='store_true')
    parser.add_argument('--latitude', type=float)
    parser.add_argument('--longitude', type=float)
    parser.add_argument('--interval', type=float, default=.25, help='Minimum start-to-start polling period in seconds')
    parser.add_argument('--duration', type=float, default=0, help='Seconds; 0 runs until Ctrl+C')
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval < .05:
        parser.error('--interval must be finite and >= 0.05 seconds')
    if not math.isfinite(args.duration) or args.duration < 0:
        parser.error('--duration must be finite and >= 0')
    if (args.latitude is None) != (args.longitude is None):
        parser.error('Provide both latitude and longitude')
    if args.latitude is not None and not (-90 <= args.latitude <= 90 and -180 <= args.longitude <= 180):
        parser.error('Coordinates outside valid latitude/longitude range')
    if args.prompt_location:
        args.location = input('Lokasi pengujian (contoh Lab ITB / meja A; Enter = BELUM_DIISI): ').strip() or 'BELUM_DIISI'
    directory = ROOT / 'evidence/datalogger' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory.mkdir(parents=True)
    metadata = dict(location_label=args.location, latitude=args.latitude, longitude=args.longitude,
                    location_source='manual' if args.location != 'BELUM_DIISI' or args.latitude is not None else 'not_provided',
                    time_source='laptop OS clock; not FPGA event time', transport='USB-Blaster JTAG status query',
                    interval_seconds=args.interval, scope='Last completed inference snapshot; no UART writes, no programming, no GPS')
    (directory / 'session.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    fields = ['timestamp_utc', 'timestamp_local', 'elapsed_s', 'read_duration_ms', 'location_label', 'latitude', 'longitude',
              'event', 'unobserved_results', 'mode', 'stop', 'pin', 'accepted', 'rejected', 'error', 'cycles', 'seq',
              'a0', 'a1', 'a2', 'action0_float', 'action1_float', 'action2_float']
    connection = None
    start = time.monotonic()
    previous = None
    count = fresh = missed = 0
    status = 'completed'
    failure = None
    print(f'Log: {directory}\nLocation: {args.location}\nFPGA -> laptop, JTAG. Ctrl+C untuk berhenti.', flush=True)
    try:
        connection = PassiveJtag()
        with (directory / 'telemetry.csv').open('w', newline='', encoding='utf-8-sig') as csvfile, (directory / 'telemetry.jsonl').open('w', encoding='utf-8') as rawfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)
            writer.writeheader()
            while args.duration == 0 or time.monotonic() - start < args.duration:
                began = time.monotonic()
                snapshot, raw = connection.snapshot()
                now = dt.datetime.now(dt.timezone.utc)
                event, gap = classify(previous, snapshot)
                row = dict(timestamp_utc=now.isoformat(timespec='milliseconds'), timestamp_local=now.astimezone().isoformat(timespec='milliseconds'),
                           elapsed_s=round(time.monotonic() - start, 6), read_duration_ms=round((time.monotonic() - began) * 1000, 3),
                           location_label=args.location, latitude=args.latitude, longitude=args.longitude,
                           event=event, unobserved_results=gap, **snapshot,
                           **{f'action{k}_float': snapshot[f'a{k}'] / 256 for k in range(3)})
                writer.writerow(row)
                rawfile.write(json.dumps(dict(**row, raw_snapshot=raw), ensure_ascii=False) + '\n')
                csvfile.flush()
                rawfile.flush()
                count += 1
                fresh += event == 'new_result'
                missed += gap or 0
                if event != 'unchanged' or previous is None or count % 20 == 0 or any(snapshot[k] != previous[k] for k in ('stop', 'error', 'mode', 'rejected')):
                    print(f"{row['timestamp_local']} | {args.location} | {event} seq={snapshot['seq']} actions={[snapshot[f'a{k}'] for k in range(3)]} stop={snapshot['stop']} error=0x{snapshot['error']:02X}", flush=True)
                previous = snapshot
                time.sleep(max(0, args.interval - (time.monotonic() - began)))
    except KeyboardInterrupt:
        status = 'stopped_by_user'
    except Exception as exc:
        status, failure = 'error', str(exc)
        print('LOGGER ERROR:', failure, flush=True)
    finally:
        if connection is not None:
            connection.close(connection.h)
        summary = dict(status=status, error=failure, snapshots=count, new_results_observed=fresh,
                       unobserved_results_at_least=missed, duration_s=round(time.monotonic() - start, 3))
        (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(summary, indent=2), '\nLog:', directory, flush=True)
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
