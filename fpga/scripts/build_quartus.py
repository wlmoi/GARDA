#!/usr/bin/env python3
"""Build one DE10-Nano project and bind its results to exact input hashes."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {
    'source_policy': ('fpga_de10_nano/src_policy', 'igor_src_policy'),
    'planner': ('fpga_de10_nano/quartus', 'igor'),
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inputs(project, revision):
    files = {project / (revision + '.qpf'), project / (revision + '.qsf'), project / 'pin_assignment.tcl'}
    qsf = (project / (revision + '.qsf')).read_text(encoding='utf-8')
    for kind, value in re.findall(r'set_global_assignment -name (VERILOG_FILE|SDC_FILE)\s+([^\r\n]+)', qsf):
        files.add((project / value.strip().strip('"')).resolve())
    files.update((ROOT / 'rtl/igor_src_policy').glob('*.mem') if revision == 'igor_src_policy' else (ROOT / 'fpga_de10_nano/assets').rglob('*.mem'))
    for p in files:
        if not p.resolve().is_relative_to(ROOT):
            raise RuntimeError(f'Build input escapes the FPGA package: {p}')
        if not p.is_file():
            raise RuntimeError(f'Missing build input: {p}')
    return {p.resolve().relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)}

def timing(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    rows = re.findall(r'Type\s*:\s*(.*?)\r?\nSlack\s*:\s*([-+\d.]+)', text)
    if not rows:
        raise RuntimeError('No timing corners found')
    return {name.strip(): float(value) for name, value in rows}

def pin_rows(path):
    rows = {}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        pieces = [part.strip() for part in line.split(':')]
        if len(pieces) > 4 and re.fullmatch(r'(FPGA_CLK1_50|UART_RX|UART_TX|KEY\[\d\]|SW\[\d\]|LED\[\d\])', pieces[0]):
            rows[pieces[0]] = {'location': pieces[1], 'direction': pieces[2], 'io_standard': pieces[3]}
    return rows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', choices=PROJECTS)
    parser.add_argument('--quartus-sh', type=Path)
    args = parser.parse_args()
    executable = args.quartus_sh or shutil.which('quartus_sh') or Path('D:/Quartus-Program/quartus/bin64/quartus_sh.exe')
    executable = Path(executable)
    if not executable.is_file():
        parser.error('Quartus shell not found; supply --quartus-sh')
    version = subprocess.run([str(executable), '--version'], capture_output=True, text=True)
    if version.returncode or '25.1' not in version.stdout:
        raise RuntimeError('This release expects Quartus Prime Standard 25.1')
    folder, revision = PROJECTS[args.project]
    project = ROOT / folder
    output = ROOT / 'evidence/current_builds'
    output.mkdir(parents=True, exist_ok=True)
    before = inputs(project, revision)
    record = {'schema': 1, 'project': args.project, 'revision': revision,
              'started_utc': datetime.now(timezone.utc).isoformat(),
              'tool_version': version.stdout.strip(), 'source_sha256': before,
              'status': 'RUNNING', 'hardware_programmed': False}
    receipt = output / (args.project + '.json')
    receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    command = [str(executable), '--flow', 'compile', revision]
    log = project / ('compile.log' if revision == 'igor_src_policy' else 'compile_current.log')
    with log.open('w', encoding='utf-8') as stream:
        completed = subprocess.run(command, cwd=project, stdout=stream, stderr=subprocess.STDOUT)
    try:
        if completed.returncode:
            raise RuntimeError(f'Quartus compile failed ({completed.returncode}); see {log}')
        if inputs(project, revision) != before:
            raise RuntimeError('Build inputs changed during compilation')
        reports = project / 'output_files'
        slacks = timing(reports / (revision + '.sta.summary'))
        if min(slacks.values()) < 0:
            raise RuntimeError('A setup/hold/recovery/removal/pulse-width constraint failed')
        pinfile = reports / (revision + '.pin')
        pins = pin_rows(pinfile)
        expected_count = 13 if args.project == 'source_policy' else 17
        if len(pins) != expected_count:
            raise RuntimeError(f'Expected {expected_count} assigned top-level pins; found {len(pins)}')
        sof = reports / (revision + '.sof')
        if not sof.is_file():
            raise RuntimeError('No programming image was generated')
        record.update(status='PASS', command=command, exit_code=0,
                      finished_utc=datetime.now(timezone.utc).isoformat(),
                      source_unchanged=True, slacks_ns=slacks, pin_assignments=pins,
                      sof=sof.relative_to(ROOT).as_posix(), sof_sha256=sha(sof),
                      log=log.relative_to(ROOT).as_posix(), log_sha256=sha(log),
                      report_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in reports.glob(revision + '.*') if p.suffix in {'.sof','.rpt','.summary','.pin'}})
    except Exception as error:
        record.update(status='FAIL', error=str(error), finished_utc=datetime.now(timezone.utc).isoformat())
        receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        raise
    receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(f"PASS {args.project}: {len(pins)} pins, minimum slack {min(slacks.values()):.3f} ns; {sof}")

if __name__ == '__main__':
    main()
