"""Run available testing_scenario checks; explicitly retain unresolved physical scenarios."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from usb_serial_roles import fpga_port

FPGA = Path(__file__).resolve().parents[1]
REPO = FPGA.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-board', action='store_true', help='Report board stages as NOT_RUN')
    parser.add_argument('--lidar-only', action='store_true', help='Real LiDAR plus software/RTL; no STM, FPGA serial or JTAG access')
    parser.add_argument('--lidar-port', default='auto', help='RPLIDAR A1 CH340 adapter port or auto')
    parser.add_argument('--stm-port', default='auto', help='STM CH9102 port or auto')
    parser.add_argument('--fpga-port', default='auto', help='FPGA Prolific USB-UART port or auto')
    parser.add_argument('--board-preprogrammed', action='store_true', help='Use the already programmed validated observer; skip the second programming step')
    parser.add_argument('--sensor-seconds', type=float, default=5)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.sensor_seconds <= 30:
        parser.error('--sensor-seconds must be within 1..30')
    out = args.output or FPGA / 'evidence/testing_scenarios' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True, exist_ok=False)
    records = []

    def save():
        status = 'FAIL' if any(r['status'] == 'FAIL' for r in records) else 'INCOMPLETE' if any(r['status'] != 'PASS' for r in records) else 'PASS'
        summary = dict(status=status, all_scenarios_passed=status == 'PASS',
                       passed=sum(r['status'] == 'PASS' for r in records),
                       failed=sum(r['status'] == 'FAIL' for r in records),
                       unresolved=sum(r['status'] not in ('PASS', 'FAIL') for r in records),
                       software_tests_run=sum(r.get('tests_run', 0) for r in records), cases=records)
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        return summary

    def unavailable(name, reason, status='BLOCKED'):
        records.append(dict(name=name, status=status, reason=reason))
        print(f'{status}: {name}: {reason}', flush=True)
        save()

    def run(name, command, timeout=240, unit=False):
        print(f'RUN: {name}', flush=True)
        began = time.monotonic()
        r = dict(name=name, command=command, status='FAIL')
        try:
            process = subprocess.run(command, cwd=REPO, capture_output=True, text=True, errors='replace', timeout=timeout)
            output = process.stdout + process.stderr
            r['exit_code'] = process.returncode
            matches = re.findall(r'Ran (\d+) tests?', output)
            if unit:
                r['tests_run'] = int(matches[-1]) if matches else 0
            r['status'] = 'PASS' if process.returncode == 0 and (not unit or r['tests_run'] > 0) else 'FAIL'
            if unit and not r['tests_run']:
                r['reason'] = 'No tests executed; zero-test OK is not accepted'
        except subprocess.TimeoutExpired as exc:
            output = f'TIMEOUT after {timeout}s\n{exc.stdout!r}\n{exc.stderr!r}'
            r['reason'] = 'Timeout; inspect log and active subprocesses before retrying'
        except OSError as exc:
            output = str(exc)
            r['reason'] = str(exc)
        logfile = out / (name + '.log')
        logfile.write_text(output, encoding='utf-8')
        r.update(log=str(logfile), duration_s=round(time.monotonic() - began, 3))
        records.append(r)
        print(f"{r['status']}: {name}" + (f" ({r['tests_run']} tests)" if unit else ''), flush=True)
        if r['status'] != 'PASS':
            print('Failure details (full output in log):\n' + '\n'.join(output.splitlines()[-8:])[-2000:], flush=True)
        save()

    specification = FPGA / 'testing_scenario.md'
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True)
    (out / 'session.json').write_text(json.dumps(dict(
        specification=str(specification), specification_sha256=hashlib.sha256(specification.read_bytes()).hexdigest(),
        commit=git.stdout.strip(), python=sys.executable, platform=sys.platform,
        motion_requested=False, note='Software fixtures, RTL simulation and board checks are separate from robot acceptance.'), indent=2) + '\n', encoding='utf-8')
    print('Evidence:', out, flush=True)
    try:
        if args.lidar_only:
            run('lidar_communication_and_feature_format', [sys.executable, str(FPGA / 'scripts/lidar_ai_reader.py'), '--port', args.lidar_port, '--seconds', '15', '--output', str(out / 'lidar_ai')])
            sensor_summary = out / 'lidar_ai/summary.json'
            if sensor_summary.is_file():
                sensor = json.loads(sensor_summary.read_text(encoding='utf-8'))
                if not sensor.get('scan_ok'):
                    unavailable('lidar_measurement_quality', sensor.get('quality_gate_reason', 'Sensor quality not established'))
            unavailable('STM_telemetry', 'LiDAR-only profile; STM not accessed', 'NOT_RUN')
        elif args.skip_board:
            unavailable('laptop_sensor_preflight', 'Explicit --skip-board selection', 'NOT_RUN')
        else:
            run('laptop_sensor_preflight', [sys.executable, str(FPGA / 'scripts/laptop_sensor_preflight.py'),
                                          '--lidar-port', args.lidar_port, '--stm-port', args.stm_port,
                                          '--scan-mode', 'express',
                                          '--seconds', str(args.sensor_seconds),
                                          '--output', str(out / 'sensors')])
        for filename in ('test_rectangle_route.py', 'test_uart_fabric.py', 'test_uart_q88.py', 'test_ethernet.py', 'test_security_auth.py'):
            name = filename.removesuffix('.py')
            if not (REPO / 'test' / filename).is_file():
                unavailable(name, f'Required test/{filename} does not exist in this checkout')
            else:
                run(name, [sys.executable, '-m', 'unittest', 'discover', '-s', 'test', '-p', filename, '-q'], unit=True)
        run('laptop_fault_contracts', [sys.executable, '-m', 'unittest', 'discover', '-s', 'fpga/verification', '-p', 'test_laptop_scenario_contracts.py', '-q'], unit=True)
        run('laptop_sensor_decoder', [sys.executable, '-m', 'unittest', 'discover', '-s', 'fpga/verification', '-p', 'test_laptop_sensor_decode.py', '-q'], unit=True)
        run('lidar_ai_features', [sys.executable, '-m', 'unittest', 'discover', '-s', 'fpga/verification', '-p', 'test_lidar_ai_features.py', '-q'], unit=True)
        run('lidar_express_decoder', [sys.executable, '-m', 'unittest', 'discover', '-s', 'fpga/verification', '-p', 'test_lidar_express.py', '-q'], unit=True)
        run('model_identity_oracle', [sys.executable, str(FPGA / 'scripts/verify_mock_inference.py'), '--self-test'])
        run('parallel8_rtl_256_vectors', [sys.executable, str(FPGA / 'scripts/verify_mock_inference.py'), '--rtl-sim'])
        if args.skip_board or args.lidar_only:
            for name in ('physical_parallel8_256_vectors', 'physical_uart_return', 'passive_datalogger'):
                unavailable(name, 'Explicit --skip-board or --lidar-only selection', 'NOT_RUN')
        else:
            # The board is an inference endpoint; this script never opens STM COM9 or commands motors.
            try:
                selected_port = fpga_port(args.fpga_port)
            except RuntimeError as exc:
                unavailable('physical_parallel8_256_vectors', str(exc))
                unavailable('physical_uart_return', str(exc))
            else:
                print('Detected FPGA UART:', selected_port, flush=True)
                board_command = [sys.executable, str(FPGA / 'scripts/verify_board_jtag.py'), '--port', selected_port]
                if not args.board_preprogrammed:
                    board_command.append('--program')
                run('physical_parallel8_256_vectors', board_command)
                run('physical_uart_return', [sys.executable, str(FPGA / 'scripts/verify_mock_inference.py'), '--port', selected_port])
            run('passive_datalogger', [sys.executable, str(FPGA / 'scripts/fpga_datalogger.py'), '--duration', '3', '--location', 'Scenario runner - physical location unspecified'])
        for name, reason in (
            ('laptop_motion_readiness', 'See actual sensor stage logs. Physical pose, verified IMU units and a validated laptop motor-control session are still required; no motion is started by this runner.'),
            ('A1_measured_rectangle', 'Requires fresh independently measured /pose, operator, clear 5x4m area, agreed geometry tolerances, bag and measured corners'),
            ('A2_command_estimated_rectangle', 'Route algorithm is tested on laptop; physical motion still needs real LiDAR, sensor preflight and supervision; not dimensional acceptance'),
            ('B_live_inputs_outputs_and_IMU_units', 'Requires real controller trace, calibrated IMU units, LiDAR, active robot run and measured deadline results'),
            ('C_link_disconnect_stop_reconnect', 'Requires supervised physical cable pull, active forward command, measured 5m, STOP trace, video/rest measurement and agreed stopping bound'),
        ):
            unavailable(name, reason)
    except KeyboardInterrupt:
        unavailable('suite_interrupted', 'Operator interrupted; remaining checks were not completed', 'NOT_RUN')
    summary = save()
    print(f"\nOverall: {summary['status']}; PASS={summary['passed']} FAIL={summary['failed']} unresolved={summary['unresolved']}")
    print('Robot motion is never started by this Windows launcher. See testing_scenario.md and TESTING_SCENARIO_RUNNER.md.')
    print('Evidence:', out, flush=True)
    return 1 if summary['failed'] else 2 if summary['unresolved'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
