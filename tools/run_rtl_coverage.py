"""Run actual Verilator coverage in WSL; production RTL remains untouched.

Usage: python tools/run_rtl_coverage.py --suite core
Requires WSL Verilator, C++ compiler and make. Each suite stores raw counters,
logs, source hashes and an explicit unwaived denominator.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import shlex
from datetime import datetime, timezone
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FPGA = ROOT / 'fpga'
SRC = FPGA / 'experiments/parallel8'
OUT = FPGA / 'evidence/rtl_coverage'

def linux(path):
    path = Path(path).resolve()
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite', choices=['core', 'uart', 'board', 'gate'], required=True)
    p.add_argument('--summarize-only',action='store_true',help='Parse an existing successful run without rebuilding')
    a = p.parse_args()
    dest = OUT / a.suite
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'artifacts').mkdir(exist_ok=True)
    top = {'core':'tb_src_policy_core','uart':'tb_src_policy_uart',
           'board':'tb_board_wrapper','gate':'tb_safety_gate'}[a.suite]
    bench = FPGA/'verification/tb_safety_gate.v' if a.suite=='gate' else SRC/(top+'.sv')
    sources = [FPGA/'rtl/igor_safety_security_gate.v'] if a.suite=='gate' else [SRC/'igor_src_policy_core.v']
    if a.suite in ['uart','board']:
        sources += [FPGA/'rtl/igor_src_policy/igor_src_policy_uart.v',FPGA/'rtl/igor_uart_rx.v',FPGA/'rtl/igor_uart_tx.v']
    if a.suite=='board': sources += [SRC/'igor_src_policy_de10_nano.v']
    tb = bench.read_text().replace('../../verification/src_policy/artifacts/',linux(FPGA/'verification/src_policy/artifacts')+'/')
    # Remove only waveform I/O; assertions and all stimulus remain intact.
    tb = re.sub(r'\$(?:dumpfile|dumpvars|dumpoff)\s*(?:\([^;]*?\))?\s*;', ' begin end ', tb)
    supplement=FPGA/'verification/src_policy/coverage_illegal_state.svh'
    if a.suite=='core' and not a.summarize_only:
        tb=tb.replace('$fclose(checkpoints);',supplement.read_text()+'\n$fclose(checkpoints);')
    if a.suite=='gate':
        # Explicit assignment from scan temporaries makes combinational input
        # changes visible to compiled simulators; vectors/oracle are unchanged.
        tb=tb.replace('integer fd,rows,', 'reg [9:0] scanned_ctrl; reg [4:0] scv,spv,smv,smdv; reg signed [6:0] scw,spw; reg [6:0] smw,smdw;\ninteger fd,rows,')
        tb=tb.replace(',ctrl,cv,pv,mv,mdv,cw,pw,mw,mdw,expected);', ',scanned_ctrl,scv,spv,smv,smdv,scw,spw,smw,smdw,expected);')
        tb=tb.replace('  #1;', '  ctrl=scanned_ctrl; cv=scv; pv=spv; mv=smv; mdv=smdv; cw=scw; pw=spw; mw=smw; mdw=smdw;\n  #1;')
    copied = dest/(top+'.sv')
    if not a.summarize_only: copied.write_text(tb)
    for bank in SRC.glob('bank*.mem'): shutil.copy2(bank,dest/bank.name)
    if a.suite=='gate': shutil.copy2(FPGA/'evidence/current_safety/gate_vectors.hex',dest/'gate_vectors.hex')
    harness = dest/'main.cpp'
    harness_text='''#include "VTOP.h"
#include "verilated.h"
#include "verilated_cov.h"
int main(int argc,char** argv) {
 VerilatedContext context; context.commandArgs(argc,argv);
 VTOP model{&context};
 while(!context.gotFinish()) { model.eval();
  if(!model.eventsPending()) break;
  context.time(model.nextTimeSlot());
 }
 model.final(); VerilatedCov::write("coverage.dat");
 return context.gotFinish()?0:2;
}
'''.replace('VTOP', 'V'+top)
    if not a.summarize_only: harness.write_text(harness_text)
    baseline=json.loads((FPGA/'verification/src_policy/artifacts/results.json').read_text())
    # Candidate vector constants come from the canonical runner's metadata.
    cmd=['verilator','--cc','--exe','--build','-j','2','--compiler','gcc','-MAKEFLAGS','CXX=g++ LINK=g++ CFG_CXXFLAGS_NO_UNUSED= CFG_CXXFLAGS_STD=-std=c++20 CFG_CXXFLAGS_PCH_I=-include CFG_GCH_IF_CLANG=','--timing','--coverage',
         '--assert','-Wno-fatal','--top-module',top,'--Mdir','obj_dir',
         '-DVECTOR_COUNT='+str(baseline['core_vectors']),
         '-DACTIVATION_COUNT='+str(baseline['activation_cases'])]
    cmd += [linux(s) for s in sources]+[linux(copied),linux(harness)]
    commands=[cmd,['./obj_dir/V'+top]]
    receipt={'suite':a.suite,'status':'RUNNING','commands':commands,
             'recorded_utc':datetime.now(timezone.utc).isoformat(),
             'scope':'RTL instrumented simulation; no hardware, no structural waivers',
             'sha256':{str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources+[bench,copied,harness]+list(SRC.glob('bank*.mem'))},
             'unavailable':['expression','condition/MC-DC','native FSM state/arc','gate-level coverage']}
    if a.suite=='core':
        receipt['supplemental_test']='verification/src_policy/coverage_illegal_state.svh'
        receipt['sha256'][str(supplement.relative_to(ROOT))]=hashlib.sha256(supplement.read_bytes()).hexdigest()
    if a.summarize_only:
        receipt=json.loads((dest/'receipt.json').read_text())
    else:
        version=subprocess.run(['wsl','--cd',linux(dest),'--exec','sh','-lc','verilator --version'],capture_output=True,text=True,check=True)
        receipt['simulator']=version.stdout.strip()
        (dest/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    for i,command in enumerate([] if a.summarize_only else commands):
        with (dest/('build.log' if i==0 else 'simulation.log')).open('w') as log:
            result=subprocess.run(['wsl','--cd',linux(dest),'--exec','sh','-lc',shlex.join(command)],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            receipt['status']='FAILED';receipt['exit_code']=result.returncode
            (dest/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            raise SystemExit(f'{a.suite}: failed; inspect {dest}')
    log=(dest/'simulation.log').read_text()
    if 'PASS ' not in log: raise RuntimeError('Simulation did not report PASS')
    # .dat metadata uses ASCII 1 delimiters between key/value fields.
    bins={}; uncovered=[]
    for line in (dest/'coverage.dat').read_text().splitlines():
        match=re.match(r"C '([^']*)' (\d+)",line)
        if not match: continue
        meta=dict(field.split('\x02',1) for field in match[1].split('\x01') if '\x02' in field)
        filename=meta.get('f','')
        if not any(filename==linux(s) or filename.endswith('/'+s.name) for s in sources): continue
        typ=meta.get('page','unknown').split('/')[0]
        key=(filename,typ)
        counts=bins.setdefault(key,{'hit':0,'total':0})
        counts['total']+=1; counts['hit']+=int(int(match[2])>0)
        if int(match[2])==0:
            uncovered.append({'file':filename,'metric':typ,'line':meta.get('l'),
                              'column':meta.get('n'),'object':meta.get('o'),
                              'comment':meta.get('comment'),'hierarchy':meta.get('h')})
    rows=[{'file':f,'metric':t,**v,'percent':100*v['hit']/v['total']} for (f,t),v in sorted(bins.items())]
    if not rows: raise RuntimeError('No DUT coverage counters parsed; inspect raw .dat encoding')
    receipt.update(status='PASS',coverage=rows,denominator='All emitted DUT counters; no testbench counters; hit count > 0')
    (dest/'uncovered.json').write_text(json.dumps(uncovered,indent=2)+'\n')
    (dest/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__': main()
