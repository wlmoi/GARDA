"""Windows RPLIDAR A1 identity/scan and passive STM32 telemetry checks. No chassis writes."""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
import statistics
from collections import Counter
import struct
import time

import serial
from serial.tools import list_ports
from verify_serial_links import packets
from lidar_express import validate as validate_capsule, decode_pair

ROOT = Path(__file__).resolve().parents[1]


def read_exact(port, size, seconds=2):
    data = bytearray()
    end = time.monotonic() + seconds
    while len(data) < size and time.monotonic() < end:
        data.extend(port.read(size - len(data)))
    return bytes(data)


def decode_node(raw):
    if len(raw) != 5 or (raw[0] & 1) == ((raw[0] >> 1) & 1) or not raw[1] & 1:
        raise ValueError('Invalid standard A1 node flags')
    angle = (int.from_bytes(raw[1:3], 'little') >> 1) / 64
    distance = int.from_bytes(raw[3:5], 'little') / 4000
    if angle >= 360:
        raise ValueError('Angle outside full rotation')
    return dict(start=bool(raw[0] & 1), quality=raw[0] >> 2, angle_deg=angle, distance_m=distance)


def lidar_check(name, output, seconds, on_scan=None, scan_mode='express'):
    if scan_mode not in ('standard', 'express'):
        raise ValueError('Unknown scan mode')
    result = dict(port=name, baud=115200, identity_ok=False, health_ok=False, scan_ok=False,
                  commands=[], scan_count=0, motor_commands_to_chassis=0, scan_mode=scan_mode)
    port = serial.Serial(None, 115200, timeout=.05, write_timeout=1, xonxoff=False, rtscts=False, dsrdtr=False)
    port.port = name
    port.dtr = False
    port.rts = False
    def send(raw):
        count = port.write(raw)
        port.flush()
        result['commands'].append(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(), tx=raw.hex(' '), bytes_written=count))
        if count != len(raw):
            raise OSError('Short LiDAR command write')
    try:
        port.open()
        send(b'\xa5\x25')
        time.sleep(.15)
        port.reset_input_buffer()
        send(b'\xa5\x50')
        info = read_exact(port, 27)
        result['info_hex'] = info.hex(' ')
        if len(info) != 27 or info[:7] != bytes.fromhex('a5 5a 14 00 00 00 04'):
            raise RuntimeError(f'No valid A1 device-info descriptor: received {len(info)} bytes')
        result.update(identity_ok=True, model=info[7], firmware_minor=info[8], firmware_major=info[9], hardware=info[10], serial_hex=info[11:].hex())
        send(b'\xa5\x52')
        health = read_exact(port, 10)
        result['health_hex'] = health.hex(' ')
        result['health_ok'] = len(health) == 10 and health[:7] == bytes.fromhex('a5 5a 03 00 00 00 06') and health[7] == 0
        if not result['health_ok']:
            raise RuntimeError('A1 health not OK; no scan started')
        send(b'\xa5\x20' if scan_mode == 'standard' else bytes.fromhex('a5 82 05 00 00 00 00 00 22'))
        descriptor = read_exact(port, 7)
        result['scan_descriptor_hex'] = descriptor.hex(' ')
        expected = 'a5 5a 05 00 00 40 81' if scan_mode == 'standard' else 'a5 5a 54 00 00 40 82'
        if descriptor != bytes.fromhex(expected):
            raise RuntimeError('Unexpected ' + scan_mode + ' scan descriptor')
        pending, current, completed = bytearray(), [], []
        synced = False
        invalid = 0
        last_rotation = None
        periods = []
        previous_capsule = None
        packet_size = 5 if scan_mode == 'standard' else 84
        end = time.monotonic() + seconds
        with (output / 'lidar_stream.bin').open('wb') as binary, (output / 'lidar_scans.jsonl').open('w', encoding='utf-8') as scans, (output / 'lidar_points.csv').open('w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=['timestamp_utc','rotation','angle_deg','distance_m','quality','valid_distance'])
            writer.writeheader()
            while time.monotonic() < end:
                block = port.read(min(max(port.in_waiting, 1), 4096))
                binary.write(block)
                pending.extend(block)
                decoded = []
                while len(pending) >= packet_size:
                    try:
                        packet = bytes(pending[:packet_size])
                        if scan_mode == 'standard':
                            decoded.append(decode_node(packet))
                        else:
                            validate_capsule(packet)
                            if previous_capsule is not None:
                                decoded.extend(decode_pair(previous_capsule, packet))
                            previous_capsule = packet
                    except ValueError:
                        del pending[0]
                        invalid += 1
                        previous_capsule = None
                        continue
                    del pending[:packet_size]
                for node in decoded:
                    if node['start']:
                        now = time.monotonic()
                        if synced:
                            valid = [n for n in current if n['quality'] > 0 and n['distance_m'] > .05]
                            span = max((n['angle_deg'] for n in current), default=0) - min((n['angle_deg'] for n in current), default=0)
                            record = dict(timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(), nodes=current,
                                          valid_points=len(valid), angle_span_deg=span, period_ms=(now-last_rotation)*1000,
                                          minimum_m=min((n['distance_m'] for n in valid), default=None))
                            scans.write(json.dumps(record) + '\n')
                            scans.flush()
                            for point in current:
                                writer.writerow(dict(timestamp_utc=record['timestamp_utc'], rotation=len(completed)+1,
                                                     angle_deg=point['angle_deg'], distance_m=point['distance_m'], quality=point['quality'],
                                                     valid_distance=point['quality']>0 and point['distance_m']>.05))
                            csvfile.flush()
                            if on_scan is not None:
                                on_scan(record)
                            completed.append(record)
                            periods.append(record['period_ms'])
                        synced = True
                        current = []
                        last_rotation = now
                    if synced:
                        current.append(node)
        good = [r for r in completed if r['valid_points'] >= 80 and r['angle_span_deg'] > 300]
        transport_good = [r for r in completed if len(r['nodes']) >= 80 and r['angle_span_deg'] > 300]
        result.update(scan_count=len(completed), good_scan_count=len(good), invalid_alignment_bytes=invalid,
                      scan_transport_ok=len(transport_good) >= 5,
                      min_valid_points_per_rotation=min((r['valid_points'] for r in completed), default=0),
                      max_valid_points_per_rotation=max((r['valid_points'] for r in completed), default=0),
                      minimum_observed_distance_m=min((r['minimum_m'] for r in completed if r['minimum_m'] is not None), default=None),
                      scan_ok=len(good) >= 5, maximum_period_ms=max(periods, default=None),
                      supervised_150ms_lease_met=bool(periods) and max(periods) <= 150,
                      minimum_distance_m=min((r['minimum_m'] for r in good if r['minimum_m'] is not None), default=None))
        if not result['scan_ok']:
            result['quality_gate_reason'] = 'Fewer than five rotations meeting >=80 valid distance points and >300 degree span; transport success alone is not navigation readiness'
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        if port.is_open:
            try:
                send(b'\xa5\x25')
            except Exception as exc:
                result['stop_error'] = str(exc)
            port.close()
    return result


def stm_check(name, output, seconds):
    result = dict(port=name, baud=1000000, application_tx_bytes=0, imu_ok=False)
    data = bytearray()
    port = serial.Serial(None, 1000000, timeout=.05, xonxoff=False, rtscts=False, dsrdtr=False)
    port.port = name
    port.dtr = False
    port.rts = False
    try:
        with port, (output / 'stm_chunks.jsonl').open('w', encoding='utf-8') as log:
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                block = port.read(min(max(port.in_waiting, 1), 4096))
                if block:
                    data.extend(block)
                    log.write(json.dumps(dict(timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(), rx_hex=block.hex(' '))) + '\n')
        frames, bad = packets(data)
        imu = []
        for frame in frames:
            if frame['type'] == 7 and frame['length'] >= 24:
                values = struct.unpack('<6f', bytes.fromhex(frame['payload_hex'])[:24])
                if all(math.isfinite(v) for v in values):
                    imu.append(values)
        result.update(bytes_received=len(data), crc_valid_frames=len(frames), bad_crc_candidates=bad,
                      frame_shapes={f'type_{kind}_length_{length}': count for (kind, length), count in Counter((f['type'], f['length']) for f in frames).items()},
                      finite_imu_frames=len(imu), imu_ok=len(imu) >= 5)
        if imu:
            median = [statistics.median(v[k] for v in imu) for k in range(6)]
            norm = math.sqrt(sum(v*v for v in median[:3]))
            result.update(imu_median_raw=median, acceleration_norm_raw=norm,
                          unit_hint='near_g' if .7 < norm < 1.3 else 'near_m_per_s2' if 7 < norm < 12 else 'undetermined',
                          unit_contract_verified=False,
                          note='Unit hint from samples is not firmware/calibration proof; no chassis commands sent')
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        if port.is_open:
            port.close()
        (output / 'stm_stream.bin').write_bytes(data)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lidar-port', default='auto')
    parser.add_argument('--stm-port', default='auto')
    parser.add_argument('--scan-mode', choices=['standard', 'express'], default='express')
    parser.add_argument('--seconds', type=float, default=5)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 30:
        parser.error('--seconds must be within 1..30')
    output = args.output or ROOT / 'evidence/laptop_sensors' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output.mkdir(parents=True, exist_ok=False)
    inventory = [dict(port=p.device, description=p.description, vid=p.vid, pid=p.pid, serial=p.serial_number, hwid=p.hwid) for p in list_ports.comports()]
    (output / 'ports.json').write_text(json.dumps(inventory, indent=2) + '\n')
    def resolve(value, vid, pid):
        candidates = [p['port'] for p in inventory if (p['vid'], p['pid']) == (vid, pid) and (value == 'auto' or p['port'].upper() == value.upper())]
        if len(candidates) != 1:
            raise RuntimeError(f'Expected exactly one USB {vid:04x}:{pid:04x} for {value}; found {candidates}')
        return candidates[0]
    result = dict(timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(), motor_application_tx_bytes=0)
    for label, value, vid, pid, check in [('lidar', args.lidar_port, 0x1a86, 0x7523, lidar_check), ('stm', args.stm_port, 0x1a86, 0x55d4, stm_check)]:
        try:
            name = resolve(value, vid, pid)
            result[label] = check(name, output, args.seconds, scan_mode=args.scan_mode) if label == 'lidar' else check(name, output, args.seconds)
        except Exception as exc:
            result[label] = dict(error=str(exc))
        print(label.upper() + ':', json.dumps(result[label]), flush=True)
    result['passed'] = result['lidar'].get('scan_ok', False) and result['stm'].get('imu_ok', False)
    result['motion_permit'] = False
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('Evidence:', output, flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
