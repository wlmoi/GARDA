"""Derive publication metrics from accepted Parallel8 records; no hardware actions."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
FPGA=ROOT/'fpga'
sys.path.insert(0,str(FPGA/'scripts'))
import freeze_release

def main():
    a=freeze_release.check_parallel8()
    p=FPGA/'experiments/parallel8'
    source=json.loads((FPGA/'evidence/current_metrics/metrics.json').read_text())
    b=source['projects']['source_policy']
    fit=(p/'output_files/igor_src_policy.fit.summary').read_text()
    def metric(label):
        m=re.search(r'^'+re.escape(label)+r'\s*:\s*([\d,]+)',fit,re.M)
        assert m,label
        return int(m.group(1).replace(',',''))
    used=metric('Logic utilization (in ALMs)')
    regs=metric('Total registers'); ram=metric('Total RAM Blocks'); dsp=metric('Total DSP Blocks')
    assert (used,regs,ram,dsp)==(3303,6277,64,8)
    weights=74*128+128*64+64*3; bias=128+64+3
    assert weights+bias==a['bank_words_verified']==18051
    cycles=a['cycles']; clk=a['clock_hz']; baseline_cycles=54348
    assert cycles==16*(3*74+4)+8*(3*128+4)+(3*64+4)==6916
    assert cycles/clk*1000==a['latency_ms']
    assert b['resources']['alm']['used']==3249
    banks=[]
    for i in range(8):
        words=[int(w,16) for w in (p/f'bank{i}.mem').read_text().split()]
        assert len(words)==4096
        banks.extend(v-65536 if v>=32768 else v for v in words)
    assert (min(banks),max(banks))==(-123,129)
    def power(profile):
        txt=(p/f'artifacts/power/{profile}/igor_src_policy.pow.summary').read_text()
        result={}
        for key,label in [('total','Total Thermal Power Dissipation'),('dynamic','Core Dynamic Thermal Power Dissipation'),('static','Core Static Thermal Power Dissipation'),('io','I/O Thermal Power Dissipation')]:
            result[key+'_mw']=float(re.search(re.escape(label)+r'\s*:\s*([\d.]+)',txt).group(1))
        return result
    typical=power('typical')
    report={'scope':'Derived metrics for accepted Parallel8; local reports, theoretical ratios and physical test references remain distinct.',
        'hardware_measured_by_this_script':False,'model':[74,128,64,3],
        'parameters':{'weights':weights,'bias':bias,'total':weights+bias,'active_bytes':(weights+bias)*2,
                      'bank_allocated_words':32768,'scheduled_bank_words':2297*8,'inactive_output_lane_words':5*65,
                      'active_to_allocated_percent':(weights+bias)/32768*100,
                      'integer_range':[min(banks),max(banks)],'candidate_9bit_reduction_percent':(16-9)/16*100},
        'performance':{'clock_hz':clk,'cycles':cycles,'layer_cycles':[3616,3104,196],
                       'core_latency_us':cycles/clk*1e6,'target_margin_us':160-cycles/clk*1e6,
                       'target_margin_percent':(160-cycles/clk*1e6)/160*100,
                       'baseline_cycles':baseline_cycles,'core_speedup':baseline_cycles/cycles,
                       'latency_reduction_percent':(1-cycles/baseline_cycles)*100,
                       'relative_speedup_to_8x_percent':baseline_cycles/cycles/8*100,
                       'neuron_slot_utilization_percent':bias/(25*8)*100,
                       'minimum_clock_mhz_for_exact_160us':cycles/160,
                       'theoretical_core_inferences_per_s':clk/cycles,
                       'useful_weighted_mac_per_s':weights*clk/cycles,
                       'two_ops_per_mac_GOPS':2*weights*clk/cycles/1e9},
        'resources':{'alm':used,'registers':regs,'m10k':ram,'dsp':dsp,
                     'alm_increase':used-3249,'register_increase':regs-5996,
                     'alm_increase_percent':(used-3249)/3249*100,
                     'alm_headroom':41910-used,'m10k_headroom':553-ram,'dsp_headroom':112-dsp,
                     'configured_memory_bits':524288,'implementation_memory_bits':64*10240,
                     'configured_vs_implementation_percent':524288/(64*10240)*100,
                     'top_pin_breakdown':{'clock':1,'keys':2,'uart':2,'led':8}},
        'transport':{'request_bytes':153,'response_bytes':11,'observation_payload_bytes':148,'action_payload_bytes':6,
                     'request_payload_percent':148/153*100,'response_payload_percent':6/11*100,
                     'uart_bit_cycles':54,'actual_baud':clk/54,'baud_error_percent':(clk/54/921600-1)*100,
                     'ideal_serial_ms':164*10*54/clk*1000,'ideal_serial_plus_core_ms':(164*10*54+cycles)/clk*1000},
        'power':{'kind':'vectorless estimate, Low confidence; not energy or board measurement',
                 'typical':typical,'maximum_tj100':power('maximum_tj100'),
                 'typical_dynamic_share_percent':typical['dynamic_mw']/typical['total_mw']*100,
                 'typical_static_share_percent':typical['static_mw']/typical['total_mw']*100,
                 'typical_total_delta_vs_serial_mw':typical['total_mw']-464.21,
                 'typical_total_delta_vs_serial_percent':(typical['total_mw']/464.21-1)*100}}
    sources=[p/'artifacts/acceptance.json',p/'core_checkpoints.csv',p/'output_files/igor_src_policy.fit.summary',
             p/'igor_src_policy_core.v',p/'igor_src_policy_de10_nano.v',FPGA/'rtl/igor_src_policy/igor_src_policy_uart.v',
             FPGA/'evidence/current_metrics/metrics.json',
             FPGA/'fpga_de10_nano/src_policy/output_files/igor_src_policy.fit.summary',
             p/'artifacts/power/typical/igor_src_policy.pow.summary',
             p/'artifacts/power/maximum_tj100/igor_src_policy.pow.summary']+[p/f'bank{i}.mem' for i in range(8)]
    report['source_sha256']={str(s.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}
    out=FPGA/'evidence/design_funfacts';out.mkdir(parents=True,exist_ok=True)
    (out/'design_funfacts.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: accepted source binding, model/parameter counts, bank range, fitted resources and derived design metrics')

if __name__=='__main__':main()
