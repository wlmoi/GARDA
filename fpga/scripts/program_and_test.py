"""Program accepted Parallel8 JP1 1/2, then run full hardware checks. No chassis writes."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from serial.tools import list_ports
from usb_serial_roles import fpga_port

FPGA = Path(__file__).resolve().parents[1]


def execute(command, log):
    with log.open('w', encoding='utf-8') as stream:
        process = subprocess.Popen(command, cwd=FPGA.parent, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, errors='replace')
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
                stream.write(line)
                stream.flush()
            return process.wait()
        except BaseException:
            process.terminate()
            process.wait(timeout=15)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sensor-seconds', type=float, default=30)
    args = parser.parse_args()
    if not 1 <= args.sensor_seconds <= 30:
        parser.error('--sensor-seconds must be within 1..30')
    out = FPGA / 'evidence/program_and_test' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    result = dict(status='RUNNING', motion_commanded=False, session=str(out))
    (out / 'ports.json').write_text(json.dumps([dict(port=p.device, description=p.description,
        vid=p.vid, pid=p.pid) for p in list_ports.comports()], indent=2))
    print('SESSION:', out, flush=True)
    print('JP1: adapter TX -> pin 1, adapter RX <- pin 2, GND pin 12. No VCC. No robot motion.', flush=True)
    try:
        selected = fpga_port()
        pwsh = shutil.which('pwsh') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe')
        print('STEP 1: PROGRAM FPGA', flush=True)
        code = execute([pwsh, '-NoProfile', '-File', str(FPGA/'scripts/program_uart_monitor.ps1'),
                        '-Header', 'JP1_1_2'], out/'programming.log')
        result['programming_exit_code'] = code
        if code:
            raise RuntimeError('Programming failed; tests were not started')
        image = FPGA/'bitstreams/garda_parallel8_jp1_1_2_monitor.sof'
        result['sof_sha256'] = hashlib.sha256(image.read_bytes()).hexdigest()
        print('STEP 2: FULL SCENARIO TESTS', flush=True)
        code = execute([sys.executable, '-u', str(FPGA/'scripts/run_testing_scenarios.py'),
            '--board-preprogrammed', '--fpga-port', selected, '--sensor-seconds', str(args.sensor_seconds),
            '--output', str(out/'scenario')], out/'testing.log')
        result['testing_exit_code'] = code
        summary = out/'scenario/summary.json'
        if not summary.exists():
            raise RuntimeError('Scenario runner did not produce its summary')
        result['scenario'] = json.loads(summary.read_text())
        result['status'] = result['scenario']['status']
        return code
    except KeyboardInterrupt:
        result.update(status='INTERRUPTED', error='Stopped by operator')
        return 130
    except Exception as exc:
        result.update(status='ERROR', error=str(exc))
        print('ERROR:', exc, flush=True)
        return 1
    finally:
        (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print('FINAL:', result['status'], '| Logs:', out, flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
