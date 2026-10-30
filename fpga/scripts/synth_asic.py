"""Synthesize the current TT safety gate; generic cells are not PDK area or GDS."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOP = 'tt_um_wlmoi_garda_gate'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'evidence')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Quote Yosys paths independently of the shell, including Windows spaces.
    def quoted(path):
        if path.is_relative_to(ROOT):
            path = path.relative_to(ROOT)
        return '"' + path.as_posix().replace('"', '\\"') + '"'
    commands = (
        'read_verilog src/project.v src/garda_safety_security_gate.v; '
        f'synth -top {TOP} -flatten -noabc; check -assert; stat; '
        f'write_json {quoted(output / "asic_generic_netlist.json")}; '
        f'write_verilog -noattr {quoted(output / "asic_generic_netlist.v")}'
    )
    arguments = ['-l', str(output / 'asic_generic_synthesis_noabc.log'), '-p', commands]
    native = shutil.which('yosys')
    if native:
        return subprocess.run([native, *arguments], cwd=ROOT, check=False).returncode
    sys.path.insert(0, str(ROOT / '.runtime/python'))
    os.environ['YOWASP_CACHE_DIR'] = str(ROOT / '.runtime/yowasp-cache')
    os.environ['YOWASP_MOUNT'] = '/=.'
    os.chdir(ROOT)
    from yowasp_yosys import run_yosys
    return run_yosys(arguments)


if __name__ == '__main__':
    raise SystemExit(main())

