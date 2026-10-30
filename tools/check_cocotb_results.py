"""Fail CI for missing, empty, or failed cocotb xUnit results (cocotb 1 and 2)."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def check(path):
    tree = ET.parse(path)
    cases = tree.findall('.//testcase')
    if not cases:
        raise ValueError(f'{path}: no test cases executed')
    failures = tree.findall('.//failure') + tree.findall('.//error')
    if failures:
        raise ValueError(f'{path}: {len(failures)} failed test cases')
    skipped = tree.findall('.//skipped')
    if len(skipped) == len(cases):
        raise ValueError(f'{path}: every test was skipped')
    print(f'PASS {path}: {len(cases) - len(skipped)} tests, no failures')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python tools/check_cocotb_results.py RESULTS.xml')
    check(Path(sys.argv[1]))
