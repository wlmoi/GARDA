#!/usr/bin/env python3
"""Capture real GTKWave windows with its native Grab_To_File Tcl API.

Quartus images are explicitly labelled extracts from verified reports, NOT GUI
screenshots. No synthetic waveform or fabricated app chrome is produced.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/visual_review'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def row(path, **match):
    with (ROOT / path).open(newline='', encoding='utf-8') as stream:
        found = [r for r in csv.DictReader(stream) if all(r[k] == str(v) for k,v in match.items())]
    if len(found) != 1: raise RuntimeError(f'Expected one checkpoint: {path}, {match}, got {len(found)}')
    return found[0]

def captures():
    top = 'evidence/current_safety/top.vcd'
    topcsv = 'evidence/current_safety/top_checkpoints.csv'
    def top_case(name, case, instance='core', extra=(), radius_ns=160, markers=()):
        r = row(topcsv, case=case)
        p = f'tb_safety_top.{instance}.'
        sig = [p+x for x in ('rst_n','estop','motor_enable','v_command','omega_command',
                              'fault_code','event_count','last_fault','busy','done')]
        sig += [p+x for x in extra]
        return dict(name=name, waveform=top, checkpoint_file=topcsv, checkpoint=r,
                    time_ps=int(r['time_ns'])*1000, radius_ps=radius_ns*1000,
                    signals=sig, markers=markers)
    items = [
        top_case('01_planner_estop_and_logger','estop_registered_error_log',
                 markers=((814535000,'E_STOP_ZERO'),(814551000,'LOGGED'))),
        top_case('02_planner_invalid_map','write_without_map_begin_zero_and_logged',extra=('map_fault','map_ok')),
        top_case('03_planner_deadline','compute_deadline_variant_zero_and_logged','deadline_core',('elapsed','timed_out')),
        top_case('04_planner_map_freshness','map_freshness_zero_and_logged','freshness_core',('age','map_fresh')),
        top_case('05_planner_result_lease','result_command_lease_zero_and_logged',extra=('elapsed','lease_expired')),
        top_case('06_planner_map_version','map_swap_requires_fresh_result_logged',extra=('seq','run_map_sequence','result_map_matches')),
    ]
    r = row('evidence/current_safety/gate_checkpoints.csv',case='gate_fault_11')
    items.append(dict(name='07_gate_all_outcomes',waveform='evidence/current_safety/gate.vcd',
        checkpoint_file='evidence/current_safety/gate_checkpoints.csv',checkpoint=r,time_ps=11999,end_ps=11999,
        marker_note='Stable sample 1 ps before CSV assertion timestamp; next stimulus/dumpoff occurs in the same timestamp.',
        radius_ps=12000,signals=['tb_safety_gate.'+s for s in ['ctrl','motor_enable','v_command','omega_command','fault_code']],
        markers=((999,'PASS'),(10999,'ABS_LIMIT'),(11999,'DELTA_LIMIT'))))
    uartcsv = 'verification/src_policy/artifacts/uart_checkpoints.csv'
    usig = ['tb_src_policy_uart.'+s for s in ('rst_n','estop','safety_permit','response_valid',
        'test_id','error_code','error_flags','action0','action1','action2','accepted_frames','rejected_frames','last_latency_cycles')]
    for name,test,event in [
        ('09_policy_crc_reject',2,'rejected_zero_guard'),
        ('10_policy_estop_inference',10,'rejected_zero_guard'),
        ('11_policy_estop_tx',12,'rejected_zero_guard'),
        ('12_policy_stale',15,'rejected_zero_guard'),
        ('13_counter_accepted_max',1401,'accepted_counter_saturates'),
        ('14_counter_rejected_max',1404,'rejected_counter_estop_saturates'),
        ('15_counter_reset_recovery',1406,'post_saturation_reset_recovery'),
    ]:
        r = row(uartcsv,test_id=test,event=event)
        items.append(dict(name=name,waveform='verification/src_policy/artifacts/uart.vcd',
            checkpoint_file=uartcsv,checkpoint=r,time_ps=int(r['time_ps'])-1,radius_ps=3000000,
            marker_note='Stable VCD sample 1 ps before CSV checkpoint; next test_id may change in the same timestamp.',
            signals=usig,markers=()))
    corecsv = 'verification/src_policy/artifacts/core_checkpoints.csv'
    r=row(corecsv,test_id=1,event='bit_exact_complete')
    start=row(corecsv,test_id=1,event='inference_started')
    items.append(dict(name='08_policy_bit_exact_done',waveform='verification/src_policy/artifacts/core.vcd',
        checkpoint_file=corecsv,checkpoint=r,time_ps=int(r['time_ps'])-1000,
        end_ps=int(r['time_ps'])-1,radius_ps=2000000,
        marker_note='Marker is 1 ns before CSV checkpoint; dump switches off at the checkpoint timestamp.',
        signals=['tb_src_policy_core.'+s for s in ('start','busy','done','fault','test_id','output_index','output_value','latency_cycles','dut.layer','dut.state')],
        markers=((int(r['time_ps']),'DONE_54348'),),inference_start_ps=int(start['time_ps'])))
    return sorted(items,key=lambda x:x['name'])

def validate_wave_samples(items):
    """One streaming pass per VCD: marker values must be known and match CSV.

    This guards against a screenshot taken at a dump-off boundary (all X),
    which is a viewing artefact rather than a failed RTL assertion.
    """
    for waveform in sorted({item['waveform'] for item in items}):
        group=sorted((i for i in items if i['waveform']==waveform),key=lambda i:i['time_ps'])
        stack=[]; symbols={}; values={}; pending=iter(group); current=next(pending,None)
        with (ROOT/waveform).open(encoding='ascii') as stream:
            for line in stream:
                p=line.split()
                if p[:1]==['$scope']: stack.append(p[2])
                elif p[:1]==['$upscope']: stack.pop()
                elif p[:1]==['$var']: symbols['.'.join(stack+[p[4]])]=(p[3],int(p[2]))
                elif p[:1]==['$enddefinitions']: break
            needed={symbols[s][0] for i in group for s in i['signals']}
            def sample(item):
                actual={}
                for s in item['signals']:
                    code,width=symbols[s]; bits=values.get(code,'x').lower()
                    if 'x' in bits or 'z' in bits: raise RuntimeError(f'Unknown VCD value at marker: {s}, {item["name"]}')
                    actual[s]=int(bits,2)
                row=item['checkpoint']; aliases={'safety_permit':'residual_valid','error_code':'last_error',
                    'action0':'action0_q8_8','action1':'action1_q8_8','action2':'action2_q8_8',
                    'accepted_frames':'accepted','rejected_frames':'rejected'}
                for s,v in actual.items():
                    name=s.rsplit('.',1)[-1]; key=name if name in row else aliases.get(name)
                    if key and key in row and v != (int(row[key]) & ((1<<symbols[s][1])-1)):
                        raise RuntimeError(f'VCD/CSV marker mismatch: {item["name"]}, {s}: {v} != {row[key]}')
                item['sampled_vcd_values']=actual
                item['marker_values_match_checkpoint']=True
            for line in stream:
                if line.startswith('#'):
                    time=int(line[1:])
                    while current is not None and current['time_ps']<time:
                        sample(current); current=next(pending,None)
                    if current is None: break
                elif line[:1] in '01xXzZ' and line.strip():
                    code=line[1:].strip()
                    if code in needed: values[code]=line[0]
                elif line[:1] in ('b','B'):
                    p=line.split()
                    if len(p)==2 and p[1] in needed: values[p[1]]=p[0][1:]
            while current is not None:
                sample(current); current=next(pending,None)

def capture(item, exe):
    stem=OUT/item['name']; wave=ROOT/item['waveform']; t=item['time_ps']
    # Each facility must exist: never silently capture an empty/misnamed trace.
    stack=[]; facilities={}
    with wave.open(encoding='ascii') as stream:
        for line in stream:
            p=line.split()
            if p[:1]==['$scope']: stack.append(p[2])
            elif p[:1]==['$upscope']: stack.pop()
            elif p[:1]==['$var']:
                facilities['.'.join(stack+[p[4]])] = p[5] if p[1]!='integer' and p[5].startswith('[') else ''
            elif p[:1]==['$enddefinitions']: break
    missing=set(item['signals'])-facilities.keys()
    if missing: raise RuntimeError(f'Missing VCD signals: {missing}')
    save=stem.with_suffix('.gtkw')
    names=[s+facilities[s] for s in item['signals']]
    save.write_text('[size] 1400 720\n[pos] 0 0\n[sst_width] 200\n[signals_width] 400\n[timestart] 0\n@22\n'+'\n'.join(names)+'\n',encoding='utf-8')
    script=stem.with_suffix('.tcl'); image=stem.with_suffix('.png')
    commands=['puts "DISPLAYED [gtkwave::getDisplayedSignals]"',
              f'if {{[llength [gtkwave::getDisplayedSignals]] != {len(names)}}} {{error "Not all requested signals are displayed"}}',
              f'gtkwave::setZoomRangeTimes {max(0,t-item["radius_ps"])} {item.get("end_ps",t+item["radius_ps"])}',
              f'gtkwave::setMarker {t}']
    for letter,(mt,label) in zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',item['markers']):
        commands.append(f'gtkwave::setNamedMarker {letter} {mt} "{label}"')
    commands += [f'gtkwave::/File/Grab_To_File {{{image.as_posix()}}}', 'gtkwave::/File/Quit']
    # On a Tcl error, terminate this launched viewer instead of leaving a modal
    # window hung until the timeout; report no successful capture in that case.
    script.write_text('if {[catch {\n'+'\n'.join(commands)+'\n} capture_error]} {\nputs stderr $capture_error\nexit 1\n}\n',encoding='utf-8')
    command=[str(exe),'-S',str(script),str(wave),str(save)]
    completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=60)
    log=stem.with_suffix('.log'); log.write_text(completed.stdout+completed.stderr,encoding='utf-8')
    if completed.returncode or not image.exists() or image.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n':
        raise RuntimeError(f'GTKWave capture failed: {log}')
    return {**item,'kind':'native GTKWave Grab_To_File screenshot, unmodified',
            'image':image.relative_to(ROOT).as_posix(),'image_sha256':sha(image),
            'waveform_sha256':sha(wave),'checkpoint_sha256':sha(ROOT/item['checkpoint_file']),
            'command':command,'exit_code':completed.returncode,'capture_log':log.relative_to(ROOT).as_posix()}

def compile_image(name, fitz):
    receipt=ROOT/f'evidence/current_builds/{name}.json'
    r=json.loads(receipt.read_text()); log=ROOT/r['log']; sof=ROOT/r['sof']
    if r['status']!='PASS' or not r['source_unchanged']: raise RuntimeError('Build is not accepted')
    if sha(log)!=r['log_sha256'] or sha(sof)!=r['sof_sha256']: raise RuntimeError('Build identity drift')
    for path,digest in {**r['source_sha256'],**r['report_sha256']}.items():
        if sha(ROOT/path)!=digest: raise RuntimeError(f'Build evidence drift: {path}')
    lines=log.read_text(encoding='utf-8',errors='replace').splitlines()
    success=[s.strip() for s in lines if 'was successful' in s or 'Quartus Prime Version' in s]
    setup=min(v for k,v in r['slacks_ns'].items() if 'Setup' in k)
    hold=min(v for k,v in r['slacks_ns'].items() if 'Hold' in k)
    body=[f'PROJECT: {name}',f'Finished UTC: {r["finished_utc"]}',
          'Device: Cyclone V 5CSEBA6U23I7 | Clock: 50 MHz',
          f'Input hashes unchanged: {r["source_unchanged"]} | Exit code: {r["exit_code"]}',
          f'Worst setup: {setup:+.3f} ns | Worst hold: {hold:+.3f} ns | Fitted pins: {len(r["pin_assignments"])}',
          f'Minimum slack (all reported checks): {min(r["slacks_ns"].values()):+.3f} ns','',
          'EXACT LINES FROM QUARTUS LOG:',*success,'',
          'SOF SHA256:',r['sof_sha256'],'','Evidence sources:',r['log'],
          receipt.relative_to(ROOT).as_posix(),'',
          'Report image generated from original files; NOT a Quartus GUI screenshot.',
          'PASS applies to compilation/timing. Hardware programming and robot tests are not claimed.']
    doc=fitz.open(); page=doc.new_page(width=1120,height=800)
    page.draw_rect(page.rect,color=None,fill=(0.96,0.97,0.99))
    page.insert_text((34,42),'IGOR | QUARTUS BUILD EVIDENCE',fontsize=23,color=(0.05,0.17,0.28))
    page.insert_text((34,69),'VERIFIED REPORT EXTRACT - NOT A GUI SCREENSHOT',fontsize=12,color=(0.45,0.18,0.06))
    box=fitz.Rect(34,92,1090,775)
    if page.insert_textbox(box,'\n'.join(body),fontsize=12,fontname='cour',lineheight=1.35)<0:
        raise RuntimeError('Report text overflows image')
    image=OUT/f'quartus_{name}.png'; page.get_pixmap(matrix=fitz.Matrix(1.4,1.4)).save(image)
    return dict(name=f'quartus_{name}',kind='image of verified original Quartus report extract; not GUI screenshot',
                image=image.relative_to(ROOT).as_posix(),image_sha256=sha(image),
                build_receipt=receipt.relative_to(ROOT).as_posix(),receipt_sha256=sha(receipt),
                sof_sha256=r['sof_sha256'],setup_ns=setup,hold_ns=hold)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gtkwave',type=Path,default=Path('C:/iverilog/gtkwave/bin/gtkwave.exe'))
    args=p.parse_args(); OUT.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(ROOT/'.runtime/evidence_tools'))
    import fitz
    # Gate captures on the existing source/evidence acceptance, not just exit(0).
    subprocess.run([sys.executable,str(ROOT/'verification/audit_acceptance.py')],cwd=ROOT,check=True)
    result={'generated_utc':datetime.now(timezone.utc).isoformat(),
            'gui_helper_error':'Windows native computer-use pipe unavailable after one recovery.',
            'hardware_tests_executed':False,'images':[]}
    items=captures(); validate_wave_samples(items)
    for item in items:
        result['images'].append(capture(item,args.gtkwave)); print('CAPTURED',item['name'],flush=True)
    for name in ('source_policy','planner'): result['images'].append(compile_image(name,fitz))
    (OUT/'index.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    cards=[]
    for item in result['images']:
        cards.append(f'<section><h2>{html.escape(item["name"])}</h2><p>{html.escape(item["kind"])}</p>'
                     f'<a href="{Path(item["image"]).name}"><img src="{Path(item["image"]).name}" width="100%"></a></section>')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>IGOR evidence</title>'
        '<style>body{font:16px system-ui;max-width:1400px;margin:30px auto;background:#edf1f5}section{background:white;padding:20px;margin:20px 0}img{height:auto}</style>'
        '<h1>IGOR: actual GTKWave captures and verified build report images</h1>'
        '<p>Waveforms use simulation data; Quartus images are report extracts, not GUI screenshots. No physical hardware test is claimed.</p>'+''.join(cards),encoding='utf-8')
    print(f'PASS: {len(result["images"])} evidence images; {OUT}')

if __name__=='__main__': main()
