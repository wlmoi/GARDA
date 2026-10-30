"""Synthesize the GARDA gate prototype into a separate, non-signoff output directory."""
from pathlib import Path
import argparse
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path, default=root / 'verification/build/tt_generic',
                    help='Directory for the generated netlist, JSON and log (default: verification/build/tt_generic)')
args = parser.parse_args()
output = args.output_dir.resolve()
if output == (root / 'evidence').resolve() or output.is_relative_to((root / 'evidence').resolve()):
    raise SystemExit('Refusing to overwrite archived evidence; choose a separate output directory.')
output.mkdir(parents=True, exist_ok=True)
yosys = shutil.which('yosys') or shutil.which('yowasp-yosys')
if not yosys:
    raise SystemExit('Yosys is required on PATH; no historical evidence was modified.')

def quoted(path):
    # Yosys scripts use double-quoted strings, including for paths with spaces.
    value = path.as_posix()
    if any(c in value for c in ('\\', '\"', '\n', '\r')):
        raise ValueError(f'Unsupported path: {path}')
    return f'"{value}"'

commands = '; '.join([
    f'read_verilog {quoted(root / "src/project.v")} {quoted(root / "src/garda_safety_security_gate.v")}',
    'synth -top tt_um_wlmoi_garda_gate -flatten -noabc',
    'check', 'stat',
    f'write_json {quoted(output / "asic_generic_netlist.json")}',
    f'write_verilog -noattr {quoted(output / "asic_generic_netlist.v")}',
])
subprocess.run([yosys, '-l', str(output / 'asic_generic_synthesis_noabc.log'), '-p', commands],
               cwd=root, check=True)
