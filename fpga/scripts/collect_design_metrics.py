#!/usr/bin/env python3
"""Collect source-bound FPGA resource, latency, quantization and power evidence.

No conversion from ALMs to ASIC mm2 and no invented measured power numbers.
Output CSV rows bind each reported quantity to a file, line and SHA256.
"""
from __future__ import annotations
import csv
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from freeze_release import verify_build

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/current_metrics'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text(encoding='utf-8'))

def summary_field(path,label):
    for n,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if line.startswith(label+' : '): return line.split(' : ',1)[1].strip(),n
    raise ValueError(f'Missing {label} in {path}')

def main():
    OUT.mkdir(parents=True,exist_ok=True); evidence=[]; sources={}
    def record(metric,value,unit,scope,source,line,kind,notes=''):
        source=source.resolve(); rel=source.relative_to(ROOT.parent).as_posix()
        digest=sha(source);sources[rel]=digest
        evidence.append(dict(metric=metric,value=value,unit=unit,scope=scope,source=rel,
            line=line,sha256=digest,kind=kind,notes=notes))
    result={'generated_utc':datetime.now(timezone.utc).isoformat(),
            'hardware_measured':False,'main_model':[74,128,64,3],
            'projects':{},'asic_area_mm2':None,
            'asic_area_reason':'No technology-mapped current PPO netlist, standard-cell library/PDK and physical implementation; ALM usage is not die area.'}
    for name in ['source_policy','planner']:
        build=verify_build(name)
        summary=(ROOT/build['sof']).parent/f'{build["revision"]}.fit.summary'
        resources={}
        for key,label in [('alm','Logic utilization (in ALMs)'),('registers','Total registers'),
                          ('m10k','Total RAM Blocks'),('dsp','Total DSP Blocks'),
                          ('memory_bits','Total block memory bits'),('pins','Total pins')]:
            raw,line=summary_field(summary,label)
            nums=[int(v.replace(',','')) for v in re.findall(r'[\d,]+',raw)]
            resources[key]={'used':nums[0]}
            if '/' in raw:
                resources[key].update(total=nums[1],utilization_percent=nums[0]/nums[1]*100)
            record(f'{name}.{key}',nums[0],'count' if key!='memory_bits' else 'bits',
                   name,summary,line,'post-fit FPGA utilization',raw)
        result['projects'][name]={'resources':resources,'sof_sha256':build['sof_sha256'],
            'setup_slack_ns':min(v for k,v in build['slacks_ns'].items() if 'Setup' in k),
            'hold_slack_ns':min(v for k,v in build['slacks_ns'].items() if 'Hold' in k),
            'power':{}}
        for profile in sorted((OUT/'power').glob(name+'_*')):
            receipt=profile/'receipt.json'
            if not receipt.exists(): continue
            pr=load(receipt)
            if pr.get('status')!='PASS': continue
            for path,digest in pr['reports'].items():
                if sha(ROOT/path)!=digest: raise RuntimeError('Power report changed: '+path)
            s=next(profile.glob('*.pow.summary')); power={}
            for key,label in [('total_mw','Total Thermal Power Dissipation'),
                              ('dynamic_mw','Core Dynamic Thermal Power Dissipation'),
                              ('static_mw','Core Static Thermal Power Dissipation'),
                              ('io_mw','I/O Thermal Power Dissipation')]:
                raw,line=summary_field(s,label)
                match=re.fullmatch(r'([\d.]+)\s+(mW|W)',raw)
                if not match: raise ValueError('Unexpected power unit: '+raw)
                power[key]=float(match[1])*(1000 if match[2]=='W' else 1)
                record(f'{profile.name}.{key}',power[key],'mW',name,s,line,
                       'Quartus post-fit estimate, not board measurement',
                       'Typical model unless explicitly specified otherwise; HPS excluded; check confidence and thermal assumptions.')
            confidence,line=summary_field(s,'Power Estimation Confidence')
            power.update(confidence=confidence,receipt=receipt.relative_to(ROOT).as_posix(),
                         measured=False,profile=pr['profile'])
            if abs(power['total_mw']-sum(power[k] for k in ['dynamic_mw','static_mw','io_mw']))>0.021:
                raise RuntimeError('Power components do not sum within report rounding')
            report=next(profile.glob('*.pow.rpt')).read_text(encoding='utf-8')
            log=(profile/'run.log').read_text(encoding='utf-8')
            power['critical_warnings']=[x.strip() for x in log.splitlines() if 'Critical Warning' in x]
            power['warnings']=[x.strip() for x in log.splitlines() if re.search(r'^Warning',x)]
            power['conditions_excerpt']=[x.strip() for x in report.splitlines() if any(w in x for w in
                ['Device power characteristics','Auto computed junction temperature','Ambient temperature',
                 'User entered junction temperature','Specified Junction Temperature',
                 'Board model used','Enable HPS','Default Power Toggle Rate','Default Power Input I/O Toggle Rate'])]
            power['activity_annotation_excerpt']=[x.strip() for x in report.splitlines()
                if 'Number of signals with Toggle Rate from Simulation' in x or 'Simulation time nodes in unknown state' in x]
            actual_model=re.search(r'; Device power characteristics\s*;\s*([^;]+);',report,re.I)
            power['actual_characteristics']=actual_model[1].strip() if actual_model else None
            tj=re.search(r'; (?:Auto computed|User entered) junction temperature\s*;\s*([\d.]+)',report,re.I)
            power['actual_junction_c']=float(tj[1]) if tj else None
            if pr.get('ignored_settings'): raise RuntimeError('Ignored power settings are not accepted')
            if pr.get('requested_characteristics') and power['actual_characteristics'].upper()!=pr['requested_characteristics']:
                raise RuntimeError('Power model differs from requested model')
            if 'requested_junction_c' in pr and power['actual_junction_c']!=pr['requested_junction_c']:
                raise RuntimeError('Power temperature differs from requested temperature')
            power['under_1000_mw_in_this_estimate']=power['total_mw']<1000
            result['projects'][name]['power'][pr['profile']]=power

    policy=load(ROOT/'verification/src_policy/artifacts/results.json')
    vectors_path=ROOT/'verification/src_policy/artifacts/vectors.json';vectors=load(vectors_path)
    valid=[x for x in vectors['tests'] if x['normalized_contract']]
    output_rows=[]
    for item in valid:
        for i,(q,reference) in enumerate(zip(item['q8_8_actions'],item['fp64_source_reference'])):
            error=q/256-reference
            output_rows.append(dict(vector=item['name'],axis=['vx','vy','omega'][i],
                q8_8_raw=q,q8_8_value=q/256,fp64_source_reference=reference,
                signed_error=error,absolute_error=abs(error),error_lsb=error*256))
    def csvfile(path,rows):
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    csvfile(OUT/'quantization_outputs.csv',output_rows)
    errors=[r['absolute_error'] for r in output_rows]
    quant={'format':'signed int16 Q8.8','fraction_bits':8,'lsb':1/256,
        'round_to_nearest_max_error_without_clipping':0.5/256,
        'floor_requantization_error_interval_lsb':'(-1, 0], before activation/clipping',
        'all_core_vectors':policy['core_vectors'],'normalized_vectors':len(valid),
        'normalized_output_values':len(output_rows),'max_abs_error':max(errors),
        'mae':sum(errors)/len(errors),'rmse':math.sqrt(sum(e*e for e in errors)/len(errors)),
        'max_abs_error_lsb':max(errors)*256,'max_error_percent_of_two_unit_full_scale':max(errors)/2*100,
        'axis_max_abs_error':{axis:max(r['absolute_error'] for r in output_rows if r['axis']==axis)
                              for axis in ['vx','vy','omega']},
        'reference':'Python FP64 arithmetic using source FP32 coefficients on the SAME already-Q8.8 input; not ONNX execution or end-to-end sensor quantization.',
        'claim':'Sample characterization only; not a formal all-input bound or robot trajectory accuracy.'}
    if not math.isclose(quant['max_abs_error'],policy['normalized_max_abs_error'],abs_tol=1e-15):
        raise RuntimeError('Quantization characterization differs from verified policy suite')
    model_path=ROOT.parent/'src/igor_navigation/igor_navigation/weights/model_weights.json'
    model=load(model_path); parameter_rows=[]; stats={}
    for key in ['w1','b1','w2','b2','w3','b3']:
        values=model[key]
        if isinstance(values[0],list): values=[v for row in values for v in row]
        rows=[]
        for i,value in enumerate(values):
            rounded=round(value*256);q=min(32767,max(-32768,rounded));e=q/256-value
            rows.append(dict(parameter=key,index=i,source=value,q8_8_raw=q,dequantized=q/256,
                             error=e,absolute_error=abs(e),clipped=rounded!=q))
        parameter_rows.extend(rows)
        stats[key]={'count':len(rows),'max_abs_error':max(r['absolute_error'] for r in rows),
                    'mae':sum(r['absolute_error'] for r in rows)/len(rows),
                    'rmse':math.sqrt(sum(r['error']**2 for r in rows)/len(rows)),
                    'clipped_parameters':sum(r['clipped'] for r in rows)}
    quant['parameter_stats']=stats
    csvfile(OUT/'quantization_parameters.csv',parameter_rows)
    quant['active_parameter_words']=len(parameter_rows)
    quant['padding_words']=policy['storage_words']-policy['model_words']
    # Bind parameter rounding to deployed MEM rather than analysing a different model.
    deployed=[int(x,16) for x in (ROOT/'rtl/igor_src_policy/policy_weights.mem').read_text().split()]
    if deployed[:len(parameter_rows)]!=[r['q8_8_raw']&65535 for r in parameter_rows]:
        raise RuntimeError('Reported parameter quantization differs from deployed ROM')
    result['quantization']=quant
    for name,value,unit,source in [
        ('policy.max_abs_error',max(errors),'normalized action',vectors_path),
        ('policy.max_abs_error_lsb',max(errors)*256,'LSB',vectors_path),
        ('policy.output_mae',quant['mae'],'normalized action',OUT/'quantization_outputs.csv'),
        ('policy.output_rmse',quant['rmse'],'normalized action',OUT/'quantization_outputs.csv')]:
        is_vectors=source==vectors_path
        record(name,value,unit,f'{len(valid)} normalized vectors / {len(output_rows)} outputs',source,
               next(i for i,s in enumerate(source.read_text().splitlines(),1) if 'normalized_max_abs_error' in s) if is_vectors else 2,
               'derived integer-vs-floating sample characterization',
               quant['reference']+'; MAE=mean(abs(error)), RMSE=sqrt(mean(error^2)), LSB error=max_abs*256; aggregate all normalized output rows.')
    record('policy.parameter_quantization',len(parameter_rows),'parameters','current PPO',model_path,1,
           'computed against deployed Q8.8 ROM','Per-parameter detail: quantization_parameters.csv; no rounding-clipping bound for saturated coefficients.')
    results_path=ROOT/'verification/src_policy/artifacts/results.json'
    line=next(i for i,s in enumerate(results_path.read_text().splitlines(),1) if 'latency_cycles' in s)
    result['latency']={'clock_hz':50000000,'core_cycles':policy['latency_cycles'],
        'core_ms':policy['latency_cycles']/50000,'nominal_baud':921600,
        'divider':54,'actual_baud':50000000/54,'request_bytes':153,'response_bytes':11,
        'ideal_uart_ms_actual_divider':164*10*54/50000000*1000,
        'ideal_core_plus_uart_ms_actual_divider':policy['latency_cycles']/50000+164*10*54/50000000*1000,
        'physical_rtt_ms':None,'notes':'Component budget excludes parser/load/TX handshakes, interbyte gaps, USB, OS and ROS; not a measured RTT.'}
    schedule=[128*(3*74+4),64*(3*128+4),3*(3*64+4)]
    if sum(schedule)!=policy['latency_cycles']: raise RuntimeError('MAC schedule differs from measured core latency')
    result['latency']['layer_schedule_cycles']=schedule
    result['latency']['schedule_formula']='sum(output_neurons * (3 * input_neurons + 4))'
    sdc=ROOT/'fpga_de10_nano/src_policy/igor_src_policy.sdc'
    period=float(re.search(r'create_clock[^\n]*-period\s+([\d.]+)',sdc.read_text())[1])
    if period!=20: raise RuntimeError('Metrics expect the source-bound 50 MHz clock')
    record('policy.clock_hz',1e9/period,'Hz','source policy clock',sdc,1,'SDC target clock, not measured oscillator')
    record('policy.core_cycles',policy['latency_cycles'],'cycles','integer PPO core',results_path,line,'RTL simulation counter')
    record('policy.core_latency',policy['latency_cycles']/50000,'ms @ 50MHz','integer PPO core',results_path,line,'cycles / clock, not RTT')
    result['rtl_equivalence']={'core_passed':policy['core']['passed'],'uart_passed':policy['uart']['passed'],
        'core_assertions':policy['core']['assertions'],'uart_transactions':policy['uart']['directed_transactions'],
        'uart_assertions':policy['uart']['assertions'],'mismatches_observed_in_passing_suite':0,
        'hidden_values_compared':policy['core_vectors']*192,'outputs_compared':policy['core_vectors']*3,
        'claim':'Exact against specified integer model on tested vectors, not bitwise equivalence with FP32 representation.'}
    for file in [results_path,ROOT/'rtl/igor_src_policy/policy_weights.mem',
                 ROOT/'rtl/igor_src_policy/igor_src_policy_core.v',
                 ROOT/'evidence/current_builds/source_policy.json',ROOT/'evidence/current_builds/planner.json',
                 ROOT/'verification/src_policy/artifacts/model_provenance.json',
                 ROOT/'verification/src_policy/artifacts/core_checkpoints.csv']:
        sources[file.relative_to(ROOT.parent).as_posix()]=sha(file)
    csvfile(OUT/'metric_evidence.csv',evidence)
    result['source_sha256']=sources
    (OUT/'metrics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    sys.path.insert(0,str(ROOT/'.runtime/evidence_tools'))
    import fitz
    for name,data in result['projects'].items():
        power=data['power']['vectorless'];res=data['resources']
        doc=fitz.open();page=doc.new_page(width=1120,height=780)
        page.draw_rect(page.rect,color=None,fill=(0.96,0.97,0.99))
        page.insert_text((34,45),'IGOR | RESOURCE, LATENCY, QUANTIZATION & POWER',fontsize=21,color=(0.05,0.17,0.28))
        body=[f'PROJECT: {name} | Cyclone V 5CSEBA6U23I7 | 50 MHz',
          'SOURCE: original post-fit Quartus reports; this is not a GUI screenshot.', '',
          f'ALMs: {res["alm"]["used"]} / {res["alm"]["total"]} ({res["alm"]["utilization_percent"]:.4f}%)',
          f'Registers: {res["registers"]["used"]} | M10K: {res["m10k"]["used"]} | DSP: {res["dsp"]["used"]}',
          f'Allocated memory: {res["memory_bits"]["used"]} bits', '',
          f'POWER ESTIMATE: {power["total_mw"]:.2f} mW = dynamic {power["dynamic_mw"]:.2f} + static {power["static_mw"]:.2f} + I/O {power["io_mw"]:.2f}',
          'CONFIDENCE: '+power['confidence'],
          'Typical process, 25C ambient; vectorless; HPS OFF; no board thermal model.',
          'Not measured board power. Not a worst-case operating-temperature guarantee.', '',
          'ASIC AREA (mm2): NOT AVAILABLE - no PDK-mapped current design.',
          'ALM utilization cannot be converted to chip die area by a percentage rule.', '',
          'Evidence paths and exact line numbers: metric_evidence.csv',
          'Full raw reports and command/source/SOF hashes: power/*/receipt.json']
        if name=='source_policy':
            body.extend(['',f'PPO 74-128-64-3 latency: {result["latency"]["core_cycles"]} cycles = {result["latency"]["core_ms"]:.5f} ms',
               f'Output error max {quant["max_abs_error"]:.10f} = {quant["max_abs_error_lsb"]:.6f} LSB; 153 normalized vectors.',
               'Reference uses same Q8.8 inputs; input sensor quantization is not included.',
               'Integer RTL oracle: 236 vectors, 0 observed mismatch; not FP32 bitwise equality.'])
        if page.insert_textbox(fitz.Rect(34,80,1090,758),'\n'.join(body),fontname='cour',fontsize=12,lineheight=1.3)<0:
            raise RuntimeError('Metric image text overflow')
        page.get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(OUT/f'{name}_metrics.png')
    # A labelled report chart, never presented as a power-tool GUI screenshot.
    doc=fitz.open();page=doc.new_page(width=1120,height=760)
    page.draw_rect(page.rect,color=None,fill=(0.97,0.98,0.99))
    page.insert_text((35,45),'IGOR | POST-FIT POWER ESTIMATES (mW)',fontsize=24,color=(0.05,0.17,0.28))
    page.insert_text((35,74),'Confidence LOW | HPS excluded | Not measured board power',fontsize=14,color=(0.6,0.22,0.05))
    chart=[('Typical / Ta25C','vectorless'),('Fixture VCD','board_fixture_vcd'),
           ('Maximum / Tj85C','maximum_tj85'),('Maximum / Tj100C','maximum_tj100')]
    colors={'static_mw':(0.45,0.53,0.62),'dynamic_mw':(0.05,0.45,0.73),'io_mw':(0.88,0.49,0.12)}
    for i,(label,profile) in enumerate(chart):
        power=result['projects']['source_policy']['power'].get(profile)
        if power is None: continue
        y=155+i*92;page.insert_text((35,y+14),label,fontsize=12)
        page.insert_text((35,y+36),f'{power["total_mw"]:.2f} mW',fontsize=13,color=(0.05,0.17,0.28))
        x=195
        for key in ['static_mw','dynamic_mw','io_mw']:
            width=power[key]*0.7
            page.draw_rect(fitz.Rect(x,y,x+width,y+36),color=None,fill=colors[key]);x+=width
    page.draw_line((895,125),(895,485),color=(0.65,0.1,0.1),width=1.5)
    page.insert_text((858,115),'1000 mW',fontsize=12,color=(0.65,0.1,0.1))
    # x=195, scale=0.7 => 1000 mW reference at x=895.
    for i,(label,key) in enumerate([('Core static','static_mw'),('Fabric dynamic','dynamic_mw'),('I/O','io_mw')]):
        x=195+i*210;page.draw_rect(fitz.Rect(x,515,x+18,533),fill=colors[key],color=None)
        page.insert_text((x+25,529),label,fontsize=12)
    notes=['All profiles: current policy 74-128-64-3; 50 MHz; nominal VCC 1.10 V.',
           'Typical: ambient 25C / computed Tj about 27.9C. Maximum profiles: fixed junction temperature.',
           'VCD has only 2.2% internal signal activity annotation; remaining activity is estimated.',
           'Sources: power/*/*.pow.summary, *.pow.rpt and receipt.json; exact lines: metric_evidence.csv.',
           'Report chart derived from original tool outputs. No guarantee of whole-board power below 1 W.']
    if page.insert_textbox(fitz.Rect(35,568,1090,735),'\n'.join(notes),fontsize=12,fontname='cour',lineheight=1.3)<0:
        raise RuntimeError('Power chart notes overflow')
    page.get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(OUT/'power_estimates.png')
    print('PASS metrics: resource, latency, deployed-ROM quantization and power report provenance')
    print(json.dumps({'normalized_vectors':len(valid),'max_error_lsb':quant['max_abs_error_lsb'],
                      'policy_power_mw':result['projects']['source_policy']['power']['vectorless']['total_mw'],
                      'planner_power_mw':result['projects']['planner']['power']['vectorless']['total_mw']}))

if __name__=='__main__': main()
