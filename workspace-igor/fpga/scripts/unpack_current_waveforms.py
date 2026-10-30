#!/usr/bin/env python3
"""Restore packaged .vcd.gz waveforms; writes only their FPGA evidence folders."""
import gzip
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
for name in ('evidence/current_safety','evidence/current_board_wrapper','verification/src_policy/artifacts'):
    for source in (root / name).glob('*.vcd.gz'):
        target = source.with_suffix('')
        with gzip.open(source, 'rb') as compressed, target.open('wb') as output:
            shutil.copyfileobj(compressed, output)
        print(target.relative_to(root))
