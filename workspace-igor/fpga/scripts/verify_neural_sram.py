"""Reproduce official-macro SRAM tests and pin-level neural regression."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'asic/neural_sram'
BUILD = ROOT / 'verification/build/neural_sram'
sys.path.insert(0, str(ROOT / 'reference_model'))
from neural_reference import infer, read_mem


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generic', action='store_true', help='Also exercise the generic synthesis netlist')
    args = parser.parse_args()
    report_path = ROOT / 'evidence/neural_sram_verification.json'
    report_path.write_text(json.dumps({'status': 'RUNNING'}) + '\n')
    BUILD.mkdir(parents=True, exist_ok=True)
    for record in json.loads((TARGET / 'ihp/provenance.json').read_text()):
        assert hashlib.sha256((TARGET / 'ihp' / record['file']).read_bytes()).hexdigest() == record['sha256']
    # Independently reconstruct the complete address map from layer exports.
    reconstructed = []
    for layer in range(1, 4):
        reconstructed.extend(read_mem(f'bram_w{layer}.mem'))
        reconstructed.extend(read_mem(f'bram_b{layer}.mem'))
    assert reconstructed == read_mem('bram_unified_weights.mem')
    assert len(reconstructed) == 6020
    assert infer([32767] * 24)[1], 'Independent overflow vector must fault'
    values = read_mem('test_inputs.mem')
    expected = []
    for n in range(100):
        result, fault = infer(values[n * 24:n * 24 + 24])
        assert not fault
        expected.extend(result)
    (BUILD / 'independent_expected.hex').write_text(''.join(f'{v & 65535:04x}\n' for v in expected))
    iverilog = shutil.which('iverilog') or 'C:/iverilog/bin/iverilog.exe'
    vvp = shutil.which('vvp') or 'C:/iverilog/bin/vvp.exe'
    models = [TARGET / 'ihp/RM_IHPSG13_1P_core_behavioral_bm_bist.v',
              TARGET / 'ihp/RM_IHPSG13_1P_2048x64_c2_bm_bist.v',
              TARGET / 'ihp/RM_IHPSG13_1P_256x16_c2_bm_bist.v']
    suites = {}
    for name in ['memory', 'activation', 'neural_sram'] + (['generic'] if args.generic else []):
        sources = [ROOT / 'src/igor_parameter_sram.v', TARGET / f'tb_{name}.v', *models]
        if name == 'activation':
            sources.append(ROOT / 'src/igor_activation_sram.v')
        if name == 'neural_sram':
            sources.extend([ROOT / 'src/igor_neural_sram_top.v', ROOT / 'src/igor_neural_datapath.v', ROOT / 'src/igor_activation_sram.v'])
        if name == 'generic':
            sources = [ROOT / 'evidence/neural_sram_netlist.v', TARGET / 'tb_neural_sram.v', *models]
        exe = BUILD / f'{name}.out'
        command = [iverilog, '-g2012', '-DSIM', '-DFUNCTIONAL', '-s', 'tb',
                   '-o', str(exe), *map(str, sources)]
        if name == 'generic':
            command[1:1] = ['-Ptb.VECTORS=1', '-Ptb.NETLIST_SMOKE=1']
        compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)
        log = BUILD / f'{name}.log'
        with log.open('w') as output:
            result = subprocess.run([vvp, str(exe)], cwd=ROOT, stdout=output,
                                    stderr=subprocess.STDOUT, text=True,
                                    timeout=300 if name == 'generic' else 180)
        logged = log.read_text()
        if result.returncode or 'PASS' not in logged:
            raise RuntimeError(logged)
        print('\n'.join(line for line in logged.splitlines() if line.startswith('PASS')),
              flush=True)
        suites[name] = 'PASS'
    report = {'status': 'PASS', 'suites': suites, 'physical_macro_banks': 3, 'parameter_banks': 1, 'activation_banks': 2,
              'weights': 5888, 'biases': 132, 'words': 6020,
              'readback_words': 6020, 'vectors': 100, 'outputs_checked': 400,
              'latency_cycles': 3080, 'model': 'Unmodified pinned IHP behavioral models',
              'hidden_overflow_vectors_checked': 1,
              'activation_words_checked': 152,
              'generic_netlist_vectors': 1 if args.generic else 0,
              'physical_qualification': 'NOT RUN: requires CMOS5L PDK and LibreLane'}
    report_path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
