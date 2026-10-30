"""Execute the real pinned PicoRV32 CPU/ROM/RAM/HWPE self-test and fault cases."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PARALLEL=ROOT/'fpga/experiments/parallel16'
VENDOR=HERE/'vendor/picorv32'


def digest(path):
    data=path.read_bytes()
    if path.suffix in {'.py','.v','.sv','.hex','.mem','.S','.json','.md','.qsf','.sdc','.tcl','.qpf'}:
        data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()


def main():
    upstream=json.loads((VENDOR/'UPSTREAM.json').read_text())
    for name,expected in upstream['files_sha256'].items():
        # Vendored upstream bytes are immutable, including their exact EOLs.
        if hashlib.sha256((VENDOR/name).read_bytes()).hexdigest()!=expected:
            raise SystemExit(f'Upstream CPU/license modified: {name}')
    subprocess.run([sys.executable,str(HERE/'firmware/build_firmware.py'),'--check'],check=True)
    sources=[VENDOR/'picorv32.v',HERE/'garda_riscv_soc.v',ROOT/'fpga/hwpe/garda_policy_mmio.v',PARALLEL/'garda_src_policy_core.v']
    bound=sources+[HERE/'run_test.py',HERE/'tb_garda_riscv_soc.sv',HERE/'tb_garda_riscv_bus_faults.sv']
    bound+=list((HERE/'firmware').glob('*'))+[PARALLEL/f'bank{i}.mem' for i in range(16)]
    bound+=[HERE/'garda_riscv_de10_nano.v',HERE/'prepare_quartus.py']+list((HERE/'quartus').glob('*.qsf'))+list((HERE/'quartus').glob('*.sdc'))+list((HERE/'quartus').glob('*.tcl'))
    bound+=[ROOT/'fpga/verification/src_policy/artifacts/observations.hex',ROOT/'fpga/verification/src_policy/artifacts/expected.hex']
    before={p.relative_to(ROOT).as_posix():digest(p) for p in bound if p.is_file()}
    compiler=shutil.which('iverilog') or 'C:/iverilog/bin/iverilog.exe'
    runtime=shutil.which('vvp') or 'C:/iverilog/bin/vvp.exe'
    logs={}
    with tempfile.TemporaryDirectory(prefix='garda-real-riscv-') as directory:
        output=Path(directory)
        bad=output/'corrupt.hex'
        words=(HERE/'firmware/boot.hex').read_text().splitlines()
        words[0x1128//4]=f'{int(words[0x1128//4],16)^1:08x}'
        bad.write_text('\n'.join(words)+'\n')
        for name,top,testbench in [('cpu','tb_garda_riscv_soc','tb_garda_riscv_soc.sv'),
                                   ('corrupt_oracle','tb_garda_riscv_soc','tb_garda_riscv_soc.sv'),
                                   ('bus_faults','tb_garda_riscv_bus_faults','tb_garda_riscv_bus_faults.sv')]:
            exe=output/(name+'.vvp')
            command=[compiler,'-g2012','-s',top,'-o',str(exe)]
            if name=='corrupt_oracle':
                command += [f'-P{top}.BOOT_FILE="{bad.as_posix()}"',f'-P{top}.EXPECT_PASS=0']
            subprocess.run(command+list(map(str,sources))+[str(HERE/testbench)],cwd=PARALLEL,check=True,capture_output=True,text=True)
            result=subprocess.run([runtime,str(exe)],cwd=PARALLEL,check=True,capture_output=True,text=True,timeout=120)
            log=result.stdout+result.stderr
            if 'PASS' not in log or 'ERROR:' in log or 'FATAL:' in log:
                raise RuntimeError(log)
            logs[name]=log
            print(log,end='')
    after={p.relative_to(ROOT).as_posix():digest(p) for p in bound if p.is_file()}
    if before!=after:raise SystemExit('Inputs changed during simulation; rerun before publishing evidence')
    observed=re.search(r'cycles=(\d+) fetches=(\d+) inputs=(\d+) starts=(\d+) outputs=(\d+) IRQs=(\d+) waitirq_quiet=(\d+) signature=([0-9a-f]+)',logs['cpu'])
    if observed is None:raise SystemExit('Missing measured CPU counters')
    counters=[int(value) for value in observed.groups()[:7]]
    report={'status':'PASS','kind':'Actual upstream CPU RTL + Parallel16 RTL simulation; no physical board measurement',
            'generated_utc':datetime.now(timezone.utc).isoformat(),'upstream_cpu':upstream['repository'],
            'upstream_commit':upstream['commit'],'cpu_isa':'RV32IC + upstream custom IRQ extension; M/DIV disabled',
            'vectors':[0,1,17],'input_writes':counters[2],'outputs_checked':counters[4],'irqs_serviced':counters[5],
            'accelerator_cycles_per_inference':3556,'cpu_total_cycles':counters[0],'cpu_instruction_fetches':counters[1],
            'cpu_waitirq_quiet_cycles':counters[6],'signature':observed.group(8),'tests':logs,'sha256_lf':before}
    (HERE/'cpu-regression.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':main()
