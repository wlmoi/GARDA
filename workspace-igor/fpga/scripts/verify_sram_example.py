"""Synthesize and simulate one explicit IHP SRAM through external project pins."""
from pathlib import Path
import hashlib,json,os,sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.runtime/python'))
os.environ['YOWASP_CACHE_DIR']=str(ROOT/'.runtime/yowasp-cache')
os.environ['YOWASP_MOUNT']='/=.'
os.chdir(ROOT)
from yowasp_yosys import run_yosys
TOP='tt_um_wlmoi_igor_sram_example'
MACRO='RM_IHPSG13_1P_256x16_c2_bm_bist'
provenance={item['file']:item for item in json.loads((ROOT/'asic/neural_sram/ihp/provenance.json').read_text())}
for name in ['RM_IHPSG13_1P_core_behavioral_bm_bist.v',MACRO+'.v']:
 assert hashlib.sha256((ROOT/'asic/neural_sram/ihp'/name).read_bytes()).hexdigest()==provenance[name]['sha256']
build=ROOT/'verification/build/sram_example'
build.mkdir(parents=True,exist_ok=True)
stem='verification/build/sram_example/netlist'
code=run_yosys(['-Q','-T','-q','-l','verification/build/sram_example/synthesis.log','-p',
 f'read_verilog asic/sram_example/project.v src/sram_256x16_bb.v; synth -top {TOP} -flatten -noabc; check -assert; stat; write_json {stem}.json; write_verilog -noattr {stem}.v'])
if code:raise SystemExit(code)
netlist=json.loads((build/'netlist.json').read_text())['modules'][TOP]
cells=netlist['cells']
actual={n:c['type'] for n,c in cells.items() if c['type'].startswith('RM_IHPSG13')}
assert actual=={'parameter_store.i_sram':MACRO},actual
assert not any(c['type'].startswith('$mem') for c in cells.values())
assert cells['parameter_store.i_sram']['connections']['A_CLK']==netlist['ports']['clk']['bits']
assert cells['parameter_store.i_sram']['connections']['A_BM']==['1']*16
register_bits=sum(c['type'].startswith(('$_DFF','$_SDFF')) for c in cells.values())
assert register_bits==24,register_bits
os.environ['PYTHONPATH']=os.pathsep.join([str(ROOT/'.runtime/python'),str(ROOT/'asic/sram_example'),os.environ.get('PYTHONPATH','')])
if os.name=='nt':os.environ['PATH']=os.pathsep.join(['C:/iverilog/bin',str(ROOT/'.runtime/python/cocotb/libs'),os.environ['PATH']])
from cocotb.runner import get_runner
models=[ROOT/'asic/neural_sram/ihp'/name for name in
 ['RM_IHPSG13_1P_core_behavioral_bm_bist.v',MACRO+'.v']]
for name,sources in [('rtl',[ROOT/'asic/sram_example/project.v',ROOT/'src/sram_256x16_bb.v']),
                     ('generic',[build/'netlist.v'])]:
 runner=get_runner('icarus')
 runner.build(verilog_sources=sources+models+[ROOT/'asic/sram_example/tb.v'],hdl_toplevel='tb',
              build_dir=build/name,build_args=['-g2012','-DSIM','-DFUNCTIONAL'],always=True)
 result=runner.test(hdl_toplevel='tb',test_module='test',test_dir=ROOT/'asic/sram_example',
                    results_xml=str(ROOT/'evidence'/f'cocotb_sram_example_{name}.xml'))
 tree=ET.parse(result)
 if tree.findall('.//failure') or tree.findall('.//error'):raise SystemExit(f'{name}: FAILED')
report={'status':'PASS','top':TOP,'instances':actual,'physical_sram_instances':1,
 'register_bits':register_bits,'tested_addresses':256,'weight_image':'W3 addresses 5760..6015',
 'tests':['RTL pin-only','generic-netlist pin-only','all-address readback','all-bit patterns','read-output hold','enable','reset retention'],
 'qualification':'Generic synthesis and simulation; physical routing, DRC, LVS and timing are separate checks'}
(ROOT/'evidence/sram_example_verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
