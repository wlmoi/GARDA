"""Extract fitted hierarchy and imported ASIC area; keep scopes separate."""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[2]
FPGA = ROOT/'fpga'
FIT = FPGA/'experiments/parallel8/output_files/igor_src_policy.fit.rpt'
ASIC = FPGA/'evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/final/metrics.json'

def main():
    lines=FIT.read_text().splitlines()
    header=next(i for i,line in enumerate(lines) if '; Compilation Hierarchy Node' in line)
    wanted={'igor_src_policy_de10_nano':'board','igor_src_policy_uart':'core_plus_uart_policy',
            'igor_src_policy_core':'core_only','igor_uart_rx':'uart_rx','igor_uart_tx':'uart_tx'}
    rows={}
    for n,line in enumerate(lines[header+1:],header+2):
        parts=[x.strip() for x in line.split(';')]
        if len(parts)<19: continue
        entity=parts[16]
        if entity not in wanted: continue
        number=lambda i: float(parts[i].split()[0].replace(',',''))
        rows[wanted[entity]]={'report_line':n,'entity':entity,'alms_needed':number(2),
            'combinational_aluts':int(number(7)),'registers':int(number(8)),
            'block_memory_bits':int(number(10)),'m10k':int(number(11)),
            'dsp':int(number(12)),'alm_device_percent':number(2)/41910*100}
    assert set(rows)==set(wanted.values()),rows
    m=json.loads(ASIC.read_text())
    std=m['design__instance__area__stdcell']; macro=m['design__instance__area__macros']
    die=m['design__die__area']; core=m['design__core__area']
    r={'scope':'FPGA fitted hierarchical attribution, not standalone core compilation; ASIC import is a different protocol-engine top.',
       'fpga':rows,'capacities':{'alms':41910,'m10k':553,'dsp':112,'memory_bits':5662720},
       'uart_policy_overhead':{key:rows['core_plus_uart_policy'][key]-rows['core_only'][key]
           for key in ('alms_needed','combinational_aluts','registers','block_memory_bits','m10k','dsp')},
       'asic':{'top':'tt_um_igorchip','die_mm2':die/1e6,'core_mm2':core/1e6,
           'standard_cells_mm2':std/1e6,'sram_macro_mm2':macro/1e6,
           'standard_cells_plus_macro_mm2':(std+macro)/1e6,
           'standard_cells_die_percent':std/die*100,'sram_die_percent':macro/die*100,
           'combined_die_percent':(std+macro)/die*100,
           'logic_share_of_logic_plus_sram_percent':std/(std+macro)*100,
           'sram_share_of_logic_plus_sram_percent':macro/(std+macro)*100},
       'memory_only_projection':{'assumption':'Replicate imported 256x16 SRAM macro footprint; excludes logic, routing, power/clock, spacing and ROM optimization.',
           'macro_bytes':512,'macro_mm2':macro/1e6,
           'allocated_fpga_bytes':65536,'allocated_macro_count':128,'allocated_macro_mm2':128*macro/1e6,
           'active_parameter_bytes':18051*2,'active_macro_count':math.ceil(18051*2/512),
           'active_macro_mm2':math.ceil(18051*2/512)*macro/1e6},
       'sources':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (FIT,ASIC)]}
    dest=FPGA/'evidence/area_analysis'; dest.mkdir(parents=True,exist_ok=True)
    (dest/'parallel8_area.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))

if __name__=='__main__': main()
