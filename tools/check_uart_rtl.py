"""Rerun accepted Parallel8 RTL in isolated output directories; no rebuild/programming."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FPGA = ROOT / 'fpga'
SOURCE = FPGA / 'experiments/parallel8'
OUTPUT = FPGA / 'evidence/uart_rtl_audit' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def main():
    OUTPUT.mkdir(parents=True)
    baseline = json.loads((FPGA/'verification/src_policy/artifacts/results.json').read_text())
    acceptance = json.loads((SOURCE/'artifacts/acceptance.json').read_text())
    for name, digest in acceptance['sha256'].items():
        assert hashlib.sha256((FPGA/name).read_bytes()).hexdigest() == digest, name
    assert hashlib.sha256((FPGA/'bitstreams/igor_src_policy_parallel8.sof').read_bytes()).hexdigest() == 'cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49'
    print(f'PASS accepted source/image hashes. Evidence: {OUTPUT}', flush=True)
    receipt = {'scope': 'RTL simulation, not physical UART acceptance',
               'accepted_sources_verified': True,
               'packaged_sof_sha256': hashlib.sha256((FPGA/'bitstreams/igor_src_policy_parallel8.sof').read_bytes()).hexdigest(),
               'suites': {}}
    common = [SOURCE/'igor_src_policy_core.v', FPGA/'rtl/igor_src_policy/igor_src_policy_uart.v', FPGA/'rtl/igor_uart_rx.v', FPGA/'rtl/igor_uart_tx.v']
    for suite in ['core', 'uart', 'board', 'board_nominal', 'stress']:
        folder = OUTPUT/suite
        (folder/'artifacts').mkdir(parents=True)
        for mem in SOURCE.glob('bank*.mem'):
            shutil.copyfile(mem, folder/mem.name)
        for name in ['observations', 'expected']:
            shutil.copyfile(FPGA/f'verification/src_policy/artifacts/{name}.hex', folder/f'{name}.hex')
        if suite == 'stress':
            words = [int(x, 16) for x in (folder/'observations.hex').read_text().split()]
            words = [x-65536 if x & 32768 else x for x in words]
            legal = [n for n in range(len(words)//74) if all(
                (0 if i < 64 else -256) <= x <= 256
                for i, x in enumerate(words[n*74:(n+1)*74]))]
            assert len(legal) >= 50
            (folder/'valid_vectors.hex').write_text(''.join(f'{n:04x}\n' for n in legal[:50]))
        top = ('tb_uart_board_stress' if suite == 'stress' else
               'tb_board_wrapper' if suite.startswith('board') else f'tb_src_policy_{suite}')
        bench_source = ROOT/'tools/uart_board_stress.sv' if suite == 'stress' else SOURCE/f'{top}.sv'
        text = bench_source.read_text()
        text = text.replace('../../verification/', (FPGA/'verification').as_posix() + '/')
        text = re.sub(r'\$dump(?:file|vars)\([^;]*\);', '', text)
        if suite == 'board_nominal':
            text = text.replace('localparam BIT_CYCLES=54, BIT_NS=1080;', 'localparam real BIT_NS=1000000000.0/921600.0;')
            start = text.index(' task uart_byte;')
            end = text.index(' task frame_without_crc;', start)
            text = text[:start] + ''' task uart_byte;input [7:0] value;integer k;begin
  rx=0;#(BIT_NS);
  for(k=0;k<8;k=k+1)begin rx=value[k];#(BIT_NS);end
  rx=1;#(BIT_NS);
 end endtask
''' + text[end:]
        bench = folder/f'{top}.sv'
        bench.write_text(text)
        sources = common[:1] if suite == 'core' else common[:]
        if suite.startswith('board') or suite == 'stress':
            sources.append(SOURCE/'igor_src_policy_de10_nano.v')
        sources.append(bench)
        exe = folder/'simulation.vvp'
        command = ['iverilog', '-g2012', '-Wall', '-s', top,
                   f'-DVECTOR_COUNT={baseline["core_vectors"]}',
                   f'-DACTIVATION_COUNT={baseline["activation_cases"]}', '-o', str(exe)] + [str(p) for p in sources]
        build = subprocess.run(command, cwd=folder, capture_output=True, text=True)
        (folder/'compile.log').write_text(build.stdout+build.stderr)
        build.check_returncode()
        print(f'Running {suite}...', flush=True)
        run = subprocess.run(['vvp', str(exe)], cwd=folder, capture_output=True, text=True, timeout=1800)
        log = run.stdout + run.stderr
        (folder/'simulation.log').write_text(log)
        run.check_returncode()
        assert 'PASS ' in log and not re.search(r'ERROR|FATAL', log), log
        receipt['suites'][suite] = {'passed': True, 'log': log.strip()}
        (OUTPUT/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print(log.strip(), flush=True)
    for name, digest in acceptance['sha256'].items():
        assert hashlib.sha256((FPGA/name).read_bytes()).hexdigest() == digest, name
    print('PASS all RTL audit suites; accepted source hashes remain unchanged', flush=True)


if __name__ == '__main__':
    main()
