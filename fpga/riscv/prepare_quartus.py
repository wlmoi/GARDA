"""Stage exact Parallel16 ROM banks for the isolated RISC-V Quartus project."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PROJECT=HERE/'quartus'
subprocess.run([sys.executable,str(HERE/'firmware/build_firmware.py'),'--check'],check=True)
for lane in range(16):
    source=ROOT/f'fpga/experiments/parallel16/bank{lane}.mem'
    target=PROJECT/source.name
    shutil.copyfile(source,target)
    assert hashlib.sha256(source.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest()
print('Prepared exact 16 model banks; compile quartus/garda_riscv.qpf as a board self-test.')
