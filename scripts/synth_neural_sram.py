"""Synthesize neural SRAM target; reject LUT/register parameter memories."""
from pathlib import Path
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / '.runtime/python'))
os.environ['YOWASP_CACHE_DIR'] = str(root / '.runtime/yowasp-cache')
tmp = root / '.runtime/tmp'
tmp.mkdir(parents=True, exist_ok=True)
os.environ['TMP'] = str(tmp)
os.environ['TEMP'] = str(tmp)
import tempfile
tempfile.tempdir = str(tmp)
os.chdir(root)
os.environ['YOWASP_MOUNT'] = '/=.'
from yowasp_yosys import run_yosys

target = 'tt_um_wlmoi_igor_neural_sram'
sources = ' '.join(['src/igor_neural_datapath.v', 'src/igor_neural_sram_top.v',
                    'src/igor_parameter_sram.v', 'src/igor_activation_sram.v',
                    'src/sram_2048x64_bb.v', 'src/sram_256x16_bb.v'])
command = (f'read_verilog {sources}; synth -top {target} -flatten -noabc; check -assert; stat; '
           'write_json evidence/neural_sram_netlist.json; '
           'write_verilog -noattr evidence/neural_sram_netlist.v')
code = run_yosys(['-Q', '-T', '-q', '-l', 'evidence/neural_sram_synthesis.log', '-p', command])
if code:
    raise SystemExit(code)
netlist = json.loads((root / 'evidence/neural_sram_netlist.json').read_text())
cells = netlist['modules'][target]['cells']
sys.path.insert(0,str(root))
from asic.neural_sram.contracts import EXPECTED_INSTANCES, EXPECTED_COUNTS
actual={name:cell['type'] for name,cell in cells.items() if cell['type'].startswith('RM_IHPSG13')}
assert actual == EXPECTED_INSTANCES, actual
assert not any('neural_rom' in c['type'] or c['type'].startswith('$mem') for c in cells.values())
assert all(cells[name]['connections']['A_BM'] == ['1'] * 16
           for name in actual if cells[name]['type'].endswith('256x16_c2_bm_bist'))
# A parameter write is masked to exactly one quarter of the 64-bit row.
assert len(cells['parameter_store.i_sram']['connections']['A_BM'])==64
din=cells['parameter_store.i_sram']['connections']['A_DIN']
assert all(din[offset:offset+16]==din[:16] for offset in (16,32,48))
assert all(cells[name]['connections']['A_CLK'] == netlist['modules'][target]['ports']['clk']['bits']
           for name in actual)
register_bits=sum(cell['type'].startswith(('$_DFF','$_SDFF')) for cell in cells.values())
assert register_bits <= 600, register_bits
report={'status':'PASS','top':target,'instances':actual,'macro_counts':EXPECTED_COUNTS,
        'count':len(actual),'register_bits':register_bits,'parallel_read_lanes':2,
        'parameter_and_activation_storage':'Physical SRAM black boxes',
        'synthesis':'Generic Yosys; not PDK mapping, area, timing, or layout qualification'}
(root/'evidence/neural_sram_synthesis.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: one packed parameter + two activation SRAMs; {register_bits} register bits')
