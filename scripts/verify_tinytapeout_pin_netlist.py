"""Run the submission's pin-only cocotb tests on a real mapped netlist.

This checks functional behaviour at zero delay. It is not an SDF timing test.
Use the unmodified IHP cell models and Icarus 13 or later for mapped designs.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
runtime = ROOT / ('.runtime/python' if os.name == 'nt' else '.runtime/linux-python')
if runtime.exists():
    sys.path.insert(0, str(runtime))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', type=Path, required=True)
    parser.add_argument('--stdcell-model', type=Path, required=True)
    parser.add_argument('--udp-model', type=Path, required=True)
    parser.add_argument('--build', type=Path, default=ROOT / 'verification/build/tt_mapped')
    parser.add_argument('--results', type=Path, default=ROOT / 'evidence/cocotb_tt_mapped.xml')
    parser.add_argument('--report', type=Path, default=ROOT / 'evidence/tinytapeout/current/mapped.json')
    args = parser.parse_args()
    from cocotb.runner import get_runner
    build = args.build.resolve()
    build.mkdir(parents=True, exist_ok=True)
    # No waveform dump of the entire cell library. The driven/observed pins
    # and the test module are otherwise identical to the official submission.
    testbench = build / 'tb.v'
    testbench.write_text(re.sub(r'  initial begin.*?  end', '',
                               (ROOT / 'test/tb.v').read_text(), flags=re.S))
    inputs = {
        'netlist': args.netlist.resolve(),
        'stdcell_model': args.stdcell_model.resolve(),
        'udp_model': args.udp_model.resolve(),
        'testbench': testbench,
        'pin_tests': ROOT / 'test/test.py',
        'reference_model': ROOT / 'reference_model/neural_reference.py',
    }
    inputs.update({f'model_{path.stem}': path for path in
                   sorted((ROOT / 'assets/neural_24_64_64_4').glob('*.mem'))})
    hashes = {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
              for name, path in inputs.items()}
    report = {
        'status': 'RUNNING',
        'qualification': 'Actual mapped netlist, functional zero delay. No SDF timing claim.',
        'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'inputs': hashes,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    args.results.unlink(missing_ok=True)
    os.environ['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'test'), str(ROOT / 'reference_model'),
                                              os.environ.get('PYTHONPATH', '')])
    sources = [args.udp_model.resolve(), args.stdcell_model.resolve(),
               args.netlist.resolve(), testbench]
    runner = get_runner('icarus')
    try:
        runner.build(verilog_sources=sources, hdl_toplevel='tb', build_dir=build,
                     build_args=['-g2012', '-DSIM', '-DFUNCTIONAL'], always=True)
        results = runner.test(hdl_toplevel='tb', test_module='test', test_dir=ROOT / 'test',
                              results_xml=str(args.results.resolve()))
        tree = ET.parse(results)
        cases = tree.findall('.//testcase')
        failures = tree.findall('.//failure') + tree.findall('.//error')
        if len(cases) != 2 or failures:
            raise ValueError(f'Mapped pin test failed: {len(cases)} tests, {len(failures)} failures')
        changed = [name for name, path in inputs.items()
                   if hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]['sha256']]
        if changed:
            raise ValueError(f'Inputs changed during mapped simulation: {changed}')
    except BaseException as error:
        report.update({
            'status': 'FAIL',
            'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'error': str(error),
        })
        args.report.write_text(json.dumps(report, indent=2) + '\n')
        raise
    report.update({
        'status': 'PASS',
        'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'tests': len(cases),
        'failures': len(failures),
        'test_cases': [case.attrib for case in cases],
        'xml': str(args.results.resolve()),
        'xml_sha256': hashlib.sha256(args.results.read_bytes()).hexdigest(),
    })
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: mapped netlist, 2 pin-only cocotb tests, zero delay, no SDF timing claim')


if __name__ == '__main__':
    main()
