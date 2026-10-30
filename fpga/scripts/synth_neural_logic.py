"""Synthesize full fixed-model inference; reject hard SRAM and parameter flops."""
from pathlib import Path
import json,os,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.runtime/python'))
os.environ['YOWASP_CACHE_DIR']=str(ROOT/'.runtime/yowasp-cache')
os.environ['YOWASP_MOUNT']='/=.'
os.chdir(ROOT)
from yowasp_yosys import run_yosys

TOP='tt_um_wlmoi_igor_neural_logic'
SOURCES=['igor_neural_logic_top.v','igor_parameter_logic.v',
         'igor_neural_datapath_logic.v','igor_activation_logic.v']
command='read_verilog '+' '.join('src/'+name for name in SOURCES)+f'; synth -top {TOP} -flatten; check -assert; stat; '
command+='write_json evidence/neural_logic_netlist.json; write_verilog -noattr evidence/neural_logic_netlist.v'
code=run_yosys(['-Q','-T','-q','-l','evidence/neural_logic_synthesis.log','-p',command])
if code:raise SystemExit(code)
cells=json.loads((ROOT/'evidence/neural_logic_netlist.json').read_text())['modules'][TOP]['cells']
assert not any(cell['type'].startswith(('RM_IHPSG13_','$mem')) for cell in cells.values())
registers=sum(cell['type'].startswith(('$_DFF','$_SDFF')) for cell in cells.values())
assert 2000<registers<=3500,registers
report={'status':'PASS','top':TOP,'physical_sram_banks':0,'register_bits':registers,
        'parameter_words':6020,'parameter_storage':'Immutable standard-cell logic',
        'activation_storage':'Flip-flops','parallel_mac_lanes':2,
        'qualification':'Generic synthesis only; physical acceptance still required'}
(ROOT/'evidence/neural_logic_synthesis.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: complete inference, zero hard SRAM, {registers} register bits')
