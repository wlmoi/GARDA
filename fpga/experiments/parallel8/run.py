"""Reproduce isolated candidate regressions and optional Quartus implementation."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',action='store_true')
    args=parser.parse_args()
    baseline=json.loads((ROOT/'verification/src_policy/artifacts/results.json').read_text())
    bound=list(HERE.glob('*.v'))+list(HERE.glob('*.sv'))+list(HERE.glob('*.mem'))
    bound+=list((ROOT/'verification/src_policy/artifacts').glob('*.hex'))
    bound+=[ROOT/'rtl/igor_src_policy/igor_src_policy_uart.v',ROOT/'rtl/igor_uart_rx.v',ROOT/'rtl/igor_uart_tx.v']
    before={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(bound)}
    results={'scope':'Eight-lane candidate; no physical hardware measurement',
             'latency_cycles':6916,'latency_ms_at_50mhz':0.13832,
             'target_ms':0.16,'baseline_cycles':54348,'suites':{}}
    for suite in ['core','uart','board']:
        sources=[HERE/'igor_src_policy_core.v']
        if suite in ['uart','board']: sources += [ROOT/'rtl/igor_src_policy/igor_src_policy_uart.v',ROOT/'rtl/igor_uart_rx.v',ROOT/'rtl/igor_uart_tx.v']
        if suite=='board': sources += [HERE/'igor_src_policy_de10_nano.v']
        top='tb_board_wrapper' if suite=='board' else f'tb_src_policy_{suite}'
        sources += [HERE/f'{top}.sv']
        exe=HERE/f'artifacts/{suite}.vvp'
        command=['C:/iverilog/bin/iverilog.exe','-g2012','-Wall','-s',top,
                 f'-DVECTOR_COUNT={baseline["core_vectors"]}',f'-DACTIVATION_COUNT={baseline["activation_cases"]}',
                 '-o',str(exe)]+list(map(str,sources))
        compiled=subprocess.run(command,cwd=HERE,capture_output=True,text=True)
        (HERE/f'artifacts/{suite}_compile.log').write_text(compiled.stdout+compiled.stderr)
        compiled.check_returncode()
        run=subprocess.run(['C:/iverilog/bin/vvp.exe',str(exe)],cwd=HERE,capture_output=True,text=True,timeout=1800)
        log=run.stdout+run.stderr
        (HERE/f'artifacts/{suite}.log').write_text(log)
        run.check_returncode()
        assert f'PASS {suite}' in log,log
        match=re.search(r'(\d+) (assertions|checkpoints)',log)
        results['suites'][suite]={'passed':True,match[2]:int(match[1])}
        print(log.strip(),flush=True)
    if args.build:
        with (HERE/'artifacts/compile.log').open('w') as stream:
            subprocess.run(['D:/Quartus-Program/quartus/bin64/quartus_sh.exe','--flow','compile','igor_src_policy'],
                           cwd=HERE,stdout=stream,stderr=subprocess.STDOUT,check=True)
    assert before=={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(bound)},'Inputs changed during simulation'
    results['sha256']=before
    (HERE/'artifacts/results.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__': main()
