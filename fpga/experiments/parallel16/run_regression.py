"""Run isolated Parallel16 core, UART or DE10-Nano wrapper RTL simulations."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, shutil, subprocess, tempfile

here=Path(__file__).resolve().parent
root=here.parents[2]
fixtures=root/'fpga/verification/src_policy/artifacts'
rtl=root/'fpga/rtl'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('suite', choices=['core','uart','board'])
args=parser.parse_args()
compiler=shutil.which('iverilog'); runtime=shutil.which('vvp')
if not compiler or not runtime: raise SystemExit('Install iverilog and vvp on PATH.')
tb_name='tb_board_wrapper' if args.suite=='board' else f'tb_src_policy_{args.suite}'
sources=[here/'garda_src_policy_core.v']
if args.suite in ('uart','board'):
    sources += [rtl/'garda_src_policy/garda_src_policy_uart.v', rtl/'garda_uart_rx.v', rtl/'garda_uart_tx.v']
if args.suite=='board': sources += [here/'garda_src_policy_de10_nano.v']
inputs=[here/'run_regression.py', here/(tb_name+'.sv'),*sources]
inputs += [here/f'bank{i}.mem' for i in range(16)]
fixture_names=['observations.hex','expected.hex']
if args.suite=='core': fixture_names += ['hidden1.hex','hidden2.hex','saturated.hex','activation_inputs.hex','activation_expected.hex']
inputs += [fixtures/name for name in fixture_names]
def hashes(): return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in inputs}
before=hashes()
with tempfile.TemporaryDirectory(prefix='garda-p16-') as tmp:
    build=Path(tmp);(build/'artifacts').mkdir()
    for i in range(16): shutil.copyfile(here/f'bank{i}.mem',build/f'bank{i}.mem')
    tb=(here/(tb_name+'.sv')).read_text().replace('../../verification/src_policy/artifacts/', fixtures.as_posix()+'/')
    (build/(tb_name+'.sv')).write_text(tb)
    exe=build/'test.vvp'
    subprocess.run([compiler,'-g2012','-Wall','-s',tb_name,'-DVECTOR_COUNT=236',
                    '-DACTIVATION_COUNT=8364','-o',str(exe),str(build/(tb_name+'.sv')),
                    *map(str,sources)],cwd=build,check=True)
    completed=subprocess.run([runtime,str(exe)],cwd=build,text=True,capture_output=True,timeout=1200,check=True)
    print(completed.stdout,end='')
    marker='PASS board_wrapper:' if args.suite=='board' else f'PASS {args.suite}:'
    if marker not in completed.stdout: raise SystemExit('Expected simulation pass marker missing.')
    if hashes()!=before: raise SystemExit('Inputs changed during simulation; no receipt written.')
    result={'status':'PASS','scope':'RTL simulation, not physical FPGA or timing signoff',
            'hash_format':'SHA-256 of text with CRLF normalized to LF',
            'suite':args.suite,'generated_utc':datetime.now(timezone.utc).isoformat(),
            'pass_line':next(x for x in completed.stdout.splitlines() if x.startswith(marker)),
            'source_sha256':before}
    (here/(args.suite+'-regression.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
