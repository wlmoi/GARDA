"""Offline cargo envelope test against actual packaged controller methods."""
import csv
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import numpy as np

FPGA = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hardware', action='store_true', help='Require physical FPGA UART; no fallback')
    args = parser.parse_args()
    out = FPGA / 'evidence/mock_ai_surge_cargo' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    source = FPGA / 'verification/run_host_regression.py'
    spec = importlib.util.spec_from_file_location('cargo_mock_host', source)
    host = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = host
    spec.loader.exec_module(host)
    hardware = None
    if args.hardware:
        from disturbance_hardware import HardwareInference
        hardware = HardwareInference(out, host)
        print('PHYSICAL FPGA REQUIRED; maximum action is injected AFTER verified board inference.', flush=True)
    # Independent expected values, including positive controls outside the close zone.
    cases = [(.15, 0), (.2199, 0), (.22, 0), (.2201, .0000833333333),
             (.23, .0083333333333), (.30, .0666666666667), (.35, .1083333333333),
             (.3999, .1499166666667), (.40, .15), (.4001, .15),
             (.8, .15), (1.2, .15), (1.5, .15), (3.5, .15)]
    rows = []
    print(('PHYSICAL FPGA + synthetic obstacle/post-inference surge; no physical motor commands.\n' if hardware else
           'OFFLINE MOCK: actual controller; synthetic LiDAR and AI; no hardware commands.\n') +
          'CARGO MODE ENABLED: forward <=0.15 m/s at EVERY distance; <=0.22 m: STOP.', flush=True)
    groups = [
        ('CARGO_HARD_CAP_ALL_DISTANCES', [(d, v, False) for d, v in cases]),
        ('ZERO_COMMAND_STOP', [(.4, 0, True)]),
    ]
    for group, group_cases in groups:
        print('\n=== ' + group + ' ===', flush=True)
        if group == 'OUTSIDE_CARGO_ZONE_CONTROL':
            print('Separate regression controls: obstacle >0.40 m; cargo-near 0.15 m/s cap does not apply.', flush=True)
        for mode, distance, expected, zero_command in [
                (mode, d, v, z) for mode in ['cl_drl', 'cl_drl_cbf'] for d, v, z in group_cases]:
            node, calls = host.ControllerTests().fixture()
            node.algorithm = mode
            node.cargo_mode = True
            nominal = 0.0 if zero_command else .6
            node.cmd_linear_x, node.cmd_linear_y, node.cmd_angular_z = nominal, 0., 0.
            node.fpga = SimpleNamespace(infer=lambda obs: np.array([1., 0., 0.]))
            if hardware:
                hardware.attach(node, stress=True)
            # Deliberately excessive filter output verifies the final safety clamp.
            node.cpu_controller = SimpleNamespace(filter_cbf=lambda **kwargs: (10., 0., 0., False))
            node.mcu.get_latest_imu = lambda: ((0, 0, 1), (0, 0, 0), time.monotonic())
            node.latest_ranges = np.full(360, 3.5, dtype=np.float32)
            node.latest_ranges[:9] = distance
            node.latest_ranges[-8:] = distance
            node.last_scan_time = node.last_cmd_time = time.monotonic()
            host.context['_control_loop'](node)
            twist = node.pub_safe_twist.messages[-1]
            actual = [float(twist.linear.x), float(twist.linear.y), float(twist.angular.z)]
            wheels = list(map(float, calls[-1]))
            wheel = expected / (math.pi * .0965)
            passed = (len(calls) == 1 and np.allclose(actual, [expected, 0, 0], atol=1e-6, rtol=0)
                      and np.allclose(wheels, [wheel, wheel, -wheel, -wheel], atol=1e-5, rtol=0))
            cap_applies = True
            if cap_applies:
                passed = passed and 0 <= actual[0] <= .15 + 1e-6
            row = dict(timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(), mode=mode,
                       group=group, cargo_cap_applies=cap_applies,
                       case='zero_nominal' if zero_command else ('cargo_ai_surge' if cap_applies else 'outside_zone_control'),
                       cargo_mode=True, obstacle_m=distance, nominal_vx=nominal, ai_action=[1, 0, 0],
                       expected_vx=expected, actual_twist=actual, actual_wheel_rps=wheels,
                       passed=bool(passed))
            rows.append(row)
            print(f"{mode:10} {row['case']:20} d={distance:.4f}m expected={expected:.8f} "
                  f"actual={actual[0]:.8f}m/s {'PASS' if passed else 'FAIL'}", flush=True)
    (out / 'cases.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    with (out / 'cases.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    hardware_result = hardware.finish() if hardware else None
    files = [Path(__file__), source, FPGA / 'software_integration/src/igor_controller/igor_controller/controller_node.py']
    summary = dict(passed=all(r['passed'] for r in rows), passed_cases=sum(r['passed'] for r in rows),
                   total_cases=len(rows), hardware_accessed=bool(hardware), hardware=hardware_result,
                   groups={g: dict(passed=sum(r['passed'] for r in rows if r['group'] == g),
                                   total=sum(r['group'] == g for r in rows)) for g, _ in groups},
                   scope=('Physical FPGA inference verified against integer oracle; post-inference maximum-action injection tests host cargo cap; motors mocked.' if hardware else
                          'Software mock of actual controller; no physical cargo detection, FPGA inference or motor motion verified.'),
                   source_sha256={str(p.relative_to(FPGA)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    for group, counts in summary['groups'].items():
        print(f"{group}: {counts['passed']}/{counts['total']} PASS", flush=True)
    print(f"\nRESULT: {summary['passed_cases']}/{len(rows)} {'PASS' if summary['passed'] else 'FAIL'}\nEvidence: {out}", flush=True)
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
