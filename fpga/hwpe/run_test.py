"""Run the MMIO/Parallel16 regression and write a hash-bound simulation receipt."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

here = Path(__file__).resolve().parent
root = here.parents[1]
parallel = root / 'fpga/experiments/parallel16'
fixtures = root / 'fpga/verification/src_policy/artifacts'
compiler = shutil.which('iverilog')
runtime = shutil.which('vvp')
if not compiler or not runtime:
    raise SystemExit('Install Icarus Verilog (iverilog and vvp) on PATH.')
inputs = [here / 'run_test.py', here / 'tb_garda_policy_mmio.sv',
          here / 'garda_policy_mmio.v', parallel / 'garda_src_policy_core.v',
          fixtures / 'observations.hex', fixtures / 'expected.hex']
inputs += [parallel / f'bank{i}.mem' for i in range(16)]
def hashes():
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for p in inputs}
before = hashes()
if len((fixtures / 'observations.hex').read_text().splitlines()) != 236*74 or \
   len((fixtures / 'expected.hex').read_text().splitlines()) != 236*3:
    raise SystemExit('Fixture length does not match 236 policy vectors.')
with tempfile.TemporaryDirectory(prefix='garda-mmio-') as output:
    exe = Path(output) / 'test.vvp'
    subprocess.run([compiler, '-g2012', '-Wall', '-s', 'tb_garda_policy_mmio',
                    '-o', str(exe), str(here / 'tb_garda_policy_mmio.sv'),
                    str(here / 'garda_policy_mmio.v'),
                    str(parallel / 'garda_src_policy_core.v')], cwd=parallel, check=True)
    run = subprocess.run([runtime, str(exe)], cwd=parallel, check=True, timeout=600,
                         capture_output=True, text=True)
    print(run.stdout, end='')
    if run.stderr:
        print(run.stderr, end='')
    marker = 'PASS: MMIO backpressure, faults, abort, 236 vectors/708 signed outputs, 3556 cycles'
    if marker not in run.stdout:
        raise SystemExit('Expected pass marker missing from simulation output.')
    if hashes() != before:
        raise SystemExit('Inputs changed during simulation; no receipt written.')
    version = subprocess.run([compiler, '-V'], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    receipt = {'status': 'PASS', 'kind': 'RTL simulation, not physical timing or FPGA signoff',
               'generated_utc': datetime.now(timezone.utc).isoformat(),
               'tool': version, 'vectors': 236, 'signed_outputs_checked': 708,
               'inference_cycles': 3556, 'hash_format': 'SHA-256 of text with CRLF normalized to LF', 'sha256': before}
    (here / 'mmio-regression.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
