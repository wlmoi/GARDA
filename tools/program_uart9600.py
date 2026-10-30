"""Verify and optionally load the isolated Parallel8 9600-baud build."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'fpga/experiments/parallel8_9600'
BIN=Path('D:/Quartus-Program/quartus/bin64')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',action='store_true')
    args=parser.parse_args()
    sof=PROJECT/'output_files/igor_src_policy_9600.sof'
    build=(PROJECT/'compile_9600.log').read_text(encoding='utf-16')
    assert 'Full Compilation was successful' in build, 'Build not successful/complete'
    assert 'Critical Warning' not in build, 'Review critical warnings first'
    timing=(PROJECT/'output_files/igor_src_policy_9600.sta.summary').read_text()
    slacks=[float(x) for x in re.findall(r'Slack\s*:\s*(-?[\d.]+)',timing)]
    assert slacks and min(slacks)>=0, 'Timing not met'
    sim=(PROJECT/'verification/simulation.log').read_text()
    assert 'PASS 9600 baud:' in sim and 'FATAL' not in sim
    baseline=ROOT/'fpga/experiments/parallel8'
    acceptance=json.loads((baseline/'artifacts/acceptance.json').read_text())
    for name,digest in acceptance['sha256'].items():
        assert sha(ROOT/'fpga'/name)==digest, f'Accepted baseline drift: {name}'
    assert sha(PROJECT/'igor_src_policy_core.v')==sha(baseline/'igor_src_policy_core.v')
    expected=(baseline/'igor_src_policy_de10_nano.v').read_text().replace('.BAUD(921600)','.BAUD(9600)')
    assert (PROJECT/'igor_src_policy_de10_nano.v').read_text()==expected
    assert '.BAUD(9600)' in expected
    assert sha(PROJECT/'pin_assignment.tcl')==sha(baseline/'pin_assignment.tcl')
    qsf=(PROJECT/'igor_src_policy_9600.qsf').read_text()
    assert 'DEVICE 5CSEBA6U23I7' in qsf
    sources=[PROJECT/'igor_src_policy_core.v',PROJECT/'igor_src_policy_de10_nano.v',PROJECT/'pin_assignment.tcl',PROJECT/'igor_src_policy_9600.qsf',PROJECT/'igor_src_policy.sdc']
    sources+=list(PROJECT.glob('bank*.mem'))
    sources+=[ROOT/p for p in ['fpga/rtl/igor_src_policy/igor_src_policy_uart.v','fpga/rtl/igor_uart_rx.v','fpga/rtl/igor_uart_tx.v']]
    assert all(sof.stat().st_mtime>=p.stat().st_mtime for p in sources),'SOF older than source'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    evidence=ROOT/'fpga/evidence/current_programming'/('uart9600_'+stamp)
    evidence.mkdir(parents=True)
    report={'baud':9600,'clock_hz':50000000,'sof':str(sof.relative_to(ROOT)),
            'sof_sha256':sha(sof),'minimum_timing_slack_ns':min(slacks),
            'hardware_programmed':False,'uart_function_verified':False,
            'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sources}}
    def run(arguments,name):
        result=subprocess.run([str(BIN/'quartus_pgm.exe')]+arguments,capture_output=True,text=True,cwd=PROJECT)
        output=result.stdout+result.stderr
        (evidence/name).write_text(output,encoding='utf-8')
        print(output,flush=True)
        result.check_returncode()
        assert not re.search(r'Error \(\d+\)|was unsuccessful',output)
        return output
    try:
        chain=run(['-c','1','-a'],'chain.log')
        assert re.search(r'1\) DE-SoC',chain)
        assert re.search(r'4BA00477\s+SOCVHPS\s+02D020DD\s+5CSEBA6',chain), 'Unexpected JTAG chain'
        cdf=evidence/'uart9600.cdf'
        cdf.write_text('JedecChain;\nFileRevision(JESD32A);\nDefaultMfr(6E);\n'
          'P ActionCode(Ign) Device PartName(SOCVHPS) MfrSpec(OpMask(0));\n'
          f'P ActionCode(Cfg) Device PartName(5CSEBA6) Path("{sof.parent.as_posix()}/") File("{sof.name}") MfrSpec(OpMask(1));\n'
          'ChainEnd;\nAlteraBegin;\nChainType(JTAG);\nAlteraEnd;\n')
        if args.program:
            result=run(['-c','1','-m','JTAG',str(cdf)],'programming.log')
            assert 'Configuration succeeded -- 1 device(s) configured' in result
            assert all(sha(p)==report['source_sha256'][str(p.relative_to(ROOT))] for p in sources)
            assert sha(sof)==report['sof_sha256']
            report['hardware_programmed']=True
    finally:
        (evidence/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Evidence:',evidence,flush=True)

if __name__=='__main__':main()
