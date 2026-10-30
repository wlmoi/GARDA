"""Offline worker-proximity controller mock + real RTL corrupted-UART simulation.

Never opens a COM port, programs an FPGA, or sends a chassis command.
"""
import csv
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np

FPGA = Path(__file__).resolve().parents[1]


def load_host_fixture():
    path = FPGA/'verification/run_host_regression.py'
    spec = importlib.util.spec_from_file_location('worker_mock_host', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def worker_test(out, physical=False):
    host = load_host_fixture()
    node, motor_calls = host.ControllerTests().fixture()
    # Use the actual packaged _control_loop with test doubles, never a real MCU.
    node.cmd_linear_x, node.cmd_linear_y, node.cmd_angular_z = .3, .2, .4
    node.fpga = SimpleNamespace(infer=lambda observation: np.ones(3))
    hardware = None
    if physical:
        from disturbance_hardware import HardwareInference
        hardware = HardwareInference(out, host)
        hardware.attach(node)
    node.mcu.get_latest_imu = lambda: ((0, 0, 1), (0, 0, 0), time.monotonic())
    records = []
    distances = [1.5, .4, .23, .2201, .22, .2199, .21, .15, .15]
    print('\n[1/2] WORKER STEPS IN CLOSE - synthetic frontal LiDAR obstacle', flush=True)
    for index, distance in enumerate(distances):
        node.latest_ranges = np.full(360, 3.5, dtype=np.float32)
        node.latest_ranges[:9] = distance
        node.latest_ranges[-8:] = distance
        node.last_scan_time = node.last_cmd_time = time.monotonic()
        before = len(motor_calls)
        host.context['_control_loop'](node)
        if len(motor_calls) != before + 1:
            raise AssertionError('Expected exactly one mock wheel command per control step')
        wheels = [float(x) for x in motor_calls[-1]]
        twist = node.pub_safe_twist.messages[-1]
        safe = [float(twist.linear.x), float(twist.linear.y), float(twist.angular.z)]
        expected_stop = distance <= .22
        actual_stop = all(x == 0 for x in wheels) and all(x == 0 for x in safe)
        passed = all(np.isfinite(wheels)) and all(np.isfinite(safe)) and actual_stop == expected_stop
        row = dict(timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(), step=index,
                   frontal_obstacle_m=distance, nominal_twist=[.3, .2, .4],
                   policy_action_source='physical_fpga' if hardware else 'mock_ones',
                   mock_policy_action=None if hardware else [1, 1, 1], safe_twist=safe, wheel_rps=wheels,
                   expected_stop=expected_stop, actual_stop=actual_stop, passed=bool(passed))
        records.append(row)
        print(f"distance={distance:.4f}m expected={'STOP' if expected_stop else 'MOTION'} "
              f"actual={'STOP' if actual_stop else 'MOTION'} wheels={np.round(wheels, 5).tolist()} "
              f"{'PASS' if passed else 'FAIL'}", flush=True)
    (out/'worker_steps.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    with (out/'worker_steps.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    hardware_result = hardware.finish() if hardware else None
    return dict(passed=all(r['passed'] for r in records), steps=len(records), hardware=hardware_result,
                critical_steps=sum(r['expected_stop'] for r in records),
                scope=('Actual controller with physical FPGA inference and mocked ROS/MCU; synthetic obstacle; no measured physical stopping.' if hardware else
                       'Actual controller methods, mocked ROS/FPGA/MCU, synthetic obstacle. Command stop, not measured physical stopping.'))


def executable(name):
    found = shutil.which(name)
    fallback = Path('C:/iverilog/bin')/(name+'.exe')
    if fallback.is_file():
        return str(fallback)
    if found:
        return found
    raise RuntimeError('Install Icarus Verilog: missing '+name)


def liquid_test(out):
    work = out/'liquid_rtl'
    work.mkdir()
    rom = Path('assets/neural_24_64_64_4/bram_unified_weights_padded.mem')
    (work/rom.parent).mkdir(parents=True)
    shutil.copyfile(FPGA/rom, work/rom)
    sources = sorted((FPGA/'rtl').glob('*.v'))
    testbench = FPGA/'verification/tb_safety_uart.v'
    print('\n[2/2] LIQUID ON WIRING - digital corruption proxy, Icarus RTL simulation', flush=True)
    commands = [
        [executable('iverilog'), '-g2012', '-s', 'tb_safety_uart', '-o', str(work/'uart.vvp')]
        + [str(p) for p in sources] + [str(testbench)],
        [executable('vvp'), str(work/'uart.vvp')],
    ]
    for label, command in zip(['compile', 'simulation'], commands):
        # An empty pipe avoids a Windows Icarus crash when a batch inherits NUL stdin.
        process = subprocess.run(command, cwd=work, input='', capture_output=True, text=True, timeout=120)
        (work/(label+'_command.json')).write_text(json.dumps(dict(command=command, exit_code=process.returncode), indent=2))
        (work/(label+'.log')).write_text(process.stdout+process.stderr, encoding='utf-8')
        if process.returncode or 'ERROR:' in process.stdout:
            raise RuntimeError('RTL '+label+' failed (exit '+str(process.returncode)+'); inspect '+str(work/(label+'.log')))
        if label == 'simulation' and 'PASS uart:' not in process.stdout:
            raise RuntimeError('Missing RTL PASS marker')
    with (work/'uart_checkpoints.csv').open(newline='') as stream:
        rows = {r['case']: r for r in csv.DictReader(stream)}
    selected = []
    scenarios = [
        ('crc_corruption_zero_and_logged', 'CRC byte XOR 1'),
        ('good_command_after_crc_fault_rejected', 'Valid frame after sticky CRC fault, without reset'),
        ('wrong_terminator_rejected', 'Trailer 0x5A replaced by 0x00'),
        ('truncated_frame_timeout', 'Only header 0xA5, then timeout'),
        ('uart_stop_bit_error', 'RX held low: invalid stop bit'),
    ]
    for case, stimulus in scenarios:
        r = rows[case]
        passed = (int(r['accepted_commands']) == 0 and int(r['protocol_fault']) == 1
                  and all(int(r[k]) == 0 for k in ['motor_enable', 'v_command', 'omega_command']))
        if case == 'crc_corruption_zero_and_logged':
            passed = passed and int(r['last_fault']) == 4
        record = dict(case=case, stimulus=stimulus, expected='reject; accepted=0; permit=0; commands=0',
                      actual=r, passed=passed)
        selected.append(record)
        print(f"{stimulus}: accepted={r['accepted_commands']} protocol_fault={r['protocol_fault']} "
              f"permit={r['motor_enable']} outputs=[{r['v_command']},{r['omega_command']}] "
              f"last_fault={r['last_fault']} {'PASS' if passed else 'FAIL'}", flush=True)
    # Positive controls prevent a permanently rejecting parser from passing this mock.
    control_ok = (int(rows['valid_config_accepted']['accepted_commands']) == 1
                  and int(rows['reset_recovers_uart_faults']['accepted_commands']) == 1
                  and int(rows['reset_recovers_uart_faults']['protocol_fault']) == 0)
    print('Valid frame before fault + recovery after reset:', 'PASS' if control_ok else 'FAIL', flush=True)
    (out/'corrupt_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected))
    return dict(passed=all(r['passed'] for r in selected) and control_ok,
                corruption_cases=len(selected), positive_controls_passed=control_ok,
                full_uart_checkpoints=len(rows), scope='Existing planner UART RTL testbench; corrupted serial bits/bytes, not physical liquid, short-circuit, or EMC qualification.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hardware', action='store_true', help='Require physical FPGA inference and corrupted-frame tests')
    args = parser.parse_args()
    out = FPGA/'evidence/mock_disturbances'/dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    result = dict(scope='OFFLINE MOCK / RTL SIMULATION ONLY', hardware_accessed=False,
                  physical_motion_measured=False, motor_commands_sent_to_hardware=0)
    print('PHYSICAL FPGA REQUIRED; synthetic obstacle, mock motor transport.' if args.hardware else
          'OFFLINE MOCK: no board, LiDAR, STM32, serial port or JTAG required.', flush=True)
    print('Logs:', out, flush=True)
    try:
        for label, action in [('worker', lambda p: worker_test(p, args.hardware)), ('liquid_corruption', liquid_test)]:
            try:
                result[label] = action(out)
            except Exception as exc:
                result[label] = dict(passed=False, error=str(exc))
                print(label, 'ERROR:', exc, flush=True)
        paths = [Path(__file__), FPGA/'verification/run_host_regression.py',
                 FPGA/'software_integration/src/garda_controller/garda_controller/controller_node.py',
                 FPGA/'verification/tb_safety_uart.v'] + sorted((FPGA/'rtl').glob('*.v'))
        result['source_sha256'] = {str(p.relative_to(FPGA)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        if args.hardware:
            command = [sys.executable, '-u', str(FPGA/'scripts/verify_mock_inference.py')]
            physical = subprocess.run(command, input='', capture_output=True, text=True, timeout=180)
            (out/'physical_corrupt_frames.log').write_text(physical.stdout+physical.stderr, encoding='utf-8')
            print(physical.stdout, flush=True)
            result['physical_uart'] = dict(passed=physical.returncode == 0, log='physical_corrupt_frames.log')
            result['hardware_accessed'] = True
            result['scope'] = 'Physical FPGA inference/UART plus host and RTL tests; no physical motors or liquid'
        result['passed'] = result['worker']['passed'] and result['liquid_corruption']['passed'] and (not args.hardware or result['physical_uart']['passed'])
        (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
        text = '# Mock worker + corrupted wiring frames\n\n'
        text += '**'+('PASS' if result['passed'] else 'FAIL')+' — '+result['scope']+'.**\n\n'
        text += '- Worker: actual packaged host controller, synthetic frontal distances and nonzero nominal/action commands. At <=0.22m require all four mock wheel RPS and all safe-twist axes zero.\n'
        text += '- Liquid proxy: actual planner UART RTL, CRC/trailer/truncation/framing corruption, sticky fault, valid baseline and reset recovery.\n'
        text += '- Evidence: worker_steps.csv/JSONL, corrupt_frames.jsonl, summary.json, liquid_rtl/uart_checkpoints.csv, uart.vcd and simulation.log.\n'
        text += '- No water or physical motor commands. Physical FPGA is required only with --hardware; physical UART rejection results are in physical_corrupt_frames.log. Planner fault-code checks remain RTL simulation, separate from the Parallel8 neural UART protocol. Command-zero does not measure physical stopping distance.\n'
        (out/'REPORT.md').write_text(text, encoding='utf-8')
        print('\nFINAL:', 'PASS' if result['passed'] else 'FAIL', '| Evidence:', out, flush=True)
        return 0 if result['passed'] else 1
    except Exception as exc:
        result.update(passed=False, error=str(exc))
        (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
        raise


if __name__ == '__main__':
    raise SystemExit(main())
