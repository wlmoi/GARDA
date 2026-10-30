"""Real A1 scans -> timestamped 64-feature candidates. Never sends motor/FPGA commands."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from serial.tools import list_ports
from laptop_sensor_preflight import lidar_check

FPGA = Path(__file__).resolve().parents[1]


def features(record, yaw_deg=0):
    # A fresh grid per revolution prevents stale measurements surviving a lost return.
    grid = np.full(360, 3.5, dtype=np.float32)
    measured = np.zeros(360, dtype=bool)
    for node in record['nodes']:
        distance, angle = node['distance_m'], node['angle_deg']
        if node['quality'] <= 0 or not math.isfinite(distance) or not math.isfinite(angle):
            continue
        if not .15 <= distance <= 12:
            continue
        index = round((angle + yaw_deg) % 360) % 360
        # Same last-sample-per-bin policy as the software driver.
        grid[index] = distance
        measured[index] = True
    angles = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    wrapped = (angles + np.pi) % (2 * np.pi) - np.pi
    order = np.argsort(wrapped)
    targets = np.linspace(-np.pi / 2, np.pi / 2, 64)
    beams = np.clip(np.interp(targets, wrapped[order], grid[order]), .15, 3.5).astype(np.float32)
    normalized = np.clip(beams / 3.5, 0, 1).astype(np.float32)
    # Interpolation is supported only when both contributing bins were measured now.
    right = np.searchsorted(wrapped[order], targets, side='left').clip(0, 359)
    left = np.maximum(right - 1, 0)
    exact = np.isclose(wrapped[order][right], targets, atol=1e-12, rtol=0)
    support = measured[order][right] & (exact | measured[order][left])
    q88 = [round(float(value) * 256) for value in normalized]
    error = np.abs(np.array(q88) / 256 - normalized)
    return dict(timestamp_utc=record['timestamp_utc'], period_ms=record['period_ms'],
                yaw_offset_deg=yaw_deg, front_definition='sensor angle 0 plus explicit yaw offset',
                measured_bins=int(measured.sum()), supported_features=int(support.sum()),
                measured_support_mask=support.tolist(), distances_m=beams.tolist(),
                normalized_candidates=normalized.tolist(), q88_candidates=q88,
                quantization_mae_normalized=float(error.mean()),
                quantization_max_error_normalized=float(error.max()),
                valid_points=record['valid_points'], minimum_observed_m=record['minimum_m'],
                feature_contract_ok=bool(np.isfinite(normalized).all() and len(q88) == 64 and all(0 <= v <= 256 for v in q88)),
                complete_live_observation=False, missing_features=['acceleration[3]', 'gyro[3]', 'nominal_velocity[3]', 'heading[1]'],
                motion_permit=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='auto')
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--repeat', action='store_true', help='Repeat finite capture sessions until Ctrl+C')
    parser.add_argument('--sessions', type=int, default=0, help='Limit repeated sessions for a soak test; 0 means unlimited')
    parser.add_argument('--location', default='Operator location unspecified')
    parser.add_argument('--yaw-deg', type=float, default=0)
    parser.add_argument('--output', type=Path, help='Explicit evidence folder for one capture session')
    parser.add_argument('--scan-mode', choices=['standard', 'express'], default='express')
    args = parser.parse_args()
    if args.output and args.repeat:
        parser.error('--output is for one session; omit it with --repeat')
    if args.sessions < 0:
        parser.error('--sessions must be nonnegative')
    if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 30 or not math.isfinite(args.yaw_deg):
        parser.error('seconds must be 1..30 and yaw must be finite')
    completed_sessions = 0
    all_communication_passed = True
    while True:
        out = args.output or FPGA / 'evidence/lidar_ai' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        out.mkdir(parents=True)
        inventory = [dict(port=p.device, vid=p.vid, pid=p.pid, description=p.description) for p in list_ports.comports()]
        sources = [Path(__file__), Path(__file__).with_name('lidar_express.py'),
                   Path(__file__).with_name('laptop_sensor_preflight.py'),
                   FPGA.parent / 'src/igor_navigation/igor_navigation/drivers/lidar_subsampler.py']
        (out / 'session.json').write_text(json.dumps(dict(location=args.location, inventory=inventory,
            yaw_deg=args.yaw_deg, scan_mode=args.scan_mode,
            source_sha256={str(p.relative_to(FPGA.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}), indent=2))
        candidates = [p['port'] for p in inventory if (p['vid'], p['pid']) == (0x1a86, 0x7523) and (args.port == 'auto' or args.port.upper() == p['port'].upper())]
        print('Evidence:', out, flush=True)
        if len(candidates) != 1:
            result = dict(error=f'Expected one CH340 LiDAR port; found {candidates}', motion_permit=False)
        else:
            rows = []
            last_print = 0
            with (out / 'ai_features.jsonl').open('w', encoding='utf-8') as log:
                def capture(record):
                    nonlocal last_print
                    row = features(record, args.yaw_deg)
                    row.update(location=args.location, timestamp_local=dt.datetime.now().astimezone().isoformat())
                    rows.append(row)
                    log.write(json.dumps(row) + '\n')
                    log.flush()
                    if time.monotonic() - last_print >= 1:
                        last_print = time.monotonic()
                        print(f"{row['timestamp_local']} RX=OK rotation={len(rows)} period={row['period_ms']:.1f}ms "
                              f"min={row['minimum_observed_m']}m fresh_bins={row['measured_bins']}/360 "
                              f"supported_AI={row['supported_features']}/64 Q8.8={row['q88_candidates'][:8]} "
                              'FPGA=NOT_CONNECTED_BY_THIS_TOOL motion=OFF', flush=True)
                result = lidar_check(candidates[0], out, args.seconds, on_scan=capture, scan_mode=args.scan_mode)
            result.update(feature_rows=len(rows), feature_contract_ok=bool(rows) and all(r['feature_contract_ok'] for r in rows),
                          min_supported_features=min((r['supported_features'] for r in rows), default=0),
                          max_supported_features=max((r['supported_features'] for r in rows), default=0),
                          complete_live_observation=False, motion_permit=False)
        result['communication_ok'] = bool(result.get('identity_ok') and result.get('health_ok') and result.get('scan_transport_ok'))
        result['navigation_ready'] = False
        result['pass_scope'] = 'Serial transport and numeric feature format only; see scan_ok and support masks for measurement quality'
        (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k not in ('commands', 'serial_hex', 'info_hex', 'health_hex')}, indent=2), flush=True)
        all_communication_passed &= result['communication_ok'] and result.get('feature_contract_ok', False)
        completed_sessions += 1
        if not args.repeat or (args.sessions and completed_sessions >= args.sessions):
            return 0 if all_communication_passed else 1
        print('Next session in 2 seconds; Ctrl+C stops. Logs contain candidates AND validity masks.', flush=True)
        time.sleep(2)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nStopped by operator; completed rotations remain logged.')
