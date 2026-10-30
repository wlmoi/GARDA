"""One entry point: automatically select LiDAR-only or existing full hardware runner."""
from pathlib import Path
import subprocess
import sys
from serial.tools import list_ports

if __name__ == '__main__':
    ports = list(list_ports.comports())
    has_fpga_uart = any((p.vid, p.pid) == (0x067b, 0x2303) for p in ports)
    has_stm = any((p.vid, p.pid) == (0x1a86, 0x55d4) for p in ports)
    full = has_fpga_uart and has_stm
    print('IGOR A/B/C: ' + ('FULL HARDWARE CHECKS' if full else 'LIDAR + SOFTWARE/RTL; other hardware NOT_RUN'), flush=True)
    print('A=rectangle fixtures; B=sensor/inference checks; C=fault fixtures. Physical robot acceptance requires operator evidence.', flush=True)
    command = [sys.executable, str(Path(__file__).with_name('run_testing_scenarios.py'))]
    if not full:
        command.append('--lidar-only')
    raise SystemExit(subprocess.call(command + sys.argv[1:]))
