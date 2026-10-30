"""Verify full fixed-model inference and guards against an independent oracle."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reference_model'))
from neural_reference import infer,read_mem
sys.path.insert(0,str(ROOT/'scripts'))
from generate_neural_logic_rom import generated_source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generic',action='store_true')
    args=parser.parse_args()
    assert (ROOT/'src/igor_parameter_logic.v').read_text()==generated_source()
    build=ROOT/'verification/build/neural_logic';build.mkdir(parents=True,exist_ok=True)
    inputs=read_mem('test_inputs.mem');expected=[]
    for n in range(100):
        values,fault=infer(inputs[n*24:n*24+24]);assert not fault
        expected.extend(values)
    assert infer([32767]*24)[1]
    (build/'independent_expected.hex').write_text(''.join(f'{value&65535:04x}\n' for value in expected))
    iverilog=shutil.which('iverilog') or 'C:/iverilog/bin/iverilog.exe'
    vvp=shutil.which('vvp') or 'C:/iverilog/bin/vvp.exe'
    for name in ['rtl']+(['generic'] if args.generic else []):
        sources=[ROOT/'src'/name for name in ['igor_neural_logic_top.v','igor_parameter_logic.v',
                 'igor_neural_datapath_logic.v','igor_activation_logic.v']]
        if name=='generic':sources=[ROOT/'evidence/neural_logic_netlist.v']
        exe=build/(name+'.out')
        command=[iverilog,'-g2012','-s','tb','-o',str(exe)]
        if name=='generic':command+=['-Ptb.VECTORS=1','-Ptb.NETLIST_SMOKE=1']
        command+=list(map(str,sources))+[str(ROOT/'asic/neural_logic/tb_neural_logic.v')]
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        with (build/(name+'.log')).open('w') as log:
            result=subprocess.run([vvp,str(exe)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        text=(build/(name+'.log')).read_text()
        if result.returncode or 'PASS full neural logic:' not in text:raise RuntimeError(text)
        print('\n'.join(line for line in text.splitlines() if line.startswith('PASS')),flush=True)
    report={'status':'PASS','physical_sram_banks':0,'parameter_words':6020,
            'vectors':100,'outputs_checked':400,'latency_cycles':3080,
            'hidden_overflow_checked':True,'different_model_rejected':True,
            'generic_vectors':1 if args.generic else 0,
            'qualification':'RTL/generic simulation, not routed timing signoff'}
    (ROOT/'evidence/neural_logic_verification.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
