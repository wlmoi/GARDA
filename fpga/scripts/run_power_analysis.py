#!/usr/bin/env python3
"""Run post-fit Quartus power estimation without changing release assignments.

Each analysis archives its exact reports, assumptions, command and input/build
hashes. Estimated device thermal power is not measured DE10-Nano board power.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('project',choices=['source_policy','planner'])
    p.add_argument('--profile',default='vectorless')
    p.add_argument('--vcd',type=Path)
    p.add_argument('--junction-c',type=int)
    p.add_argument('--characteristics',choices=['TYPICAL','MAXIMUM'])
    p.add_argument('--quartus-pow',type=Path,default=Path('D:/Quartus-Program/quartus/bin64/quartus_pow.exe'))
    args=p.parse_args()
    if not args.profile.replace('_','').isalnum(): p.error('profile must be an alphanumeric label')
    receipt_path=ROOT/f'evidence/current_builds/{args.project}.json'
    build=json.loads(receipt_path.read_text())
    if build['status']!='PASS' or not build['source_unchanged']: raise RuntimeError('Build not accepted')
    bound={**build['source_sha256'],**build['report_sha256'],build['log']:build['log_sha256']}
    for name,digest in bound.items():
        if sha(ROOT/name)!=digest: raise RuntimeError(f'Build input/report changed: {name}')
    project=(ROOT/build['sof']).parent.parent; revision=build['revision']
    # quartus_pow regenerates the flow summary even with write_settings_files
    # off. Preserve the accepted compile summary; archive the power-stage flow
    # separately. Source, SOF, fitter, STA and compile log must stay identical.
    flow=project/'output_files'/f'{revision}.flow.rpt'
    flow_bytes=flow.read_bytes()
    out=ROOT/f'evidence/current_metrics/power/{args.project}_{args.profile}'
    out.mkdir(parents=True,exist_ok=True)
    command=[str(args.quartus_pow),revision,'--read_settings_files=on','--write_settings_files=off',
             '--estimate_power=on','--use_vectorless_estimation=on']
    record={'schema':1,'project':args.project,'profile':args.profile,'status':'RUNNING',
            'started_utc':datetime.now(timezone.utc).isoformat(),'command':command,'cwd':str(project),
            'kind':'post-fit Quartus estimated device thermal power, not measured board power',
            'build_receipt_sha256':sha(receipt_path),'sof_sha256':build['sof_sha256'],
            'source_sha256':build['source_sha256'],'hardware_measured':False}
    if args.characteristics:
        command.append('--set=POWER_USE_DEVICE_CHARACTERISTICS='+args.characteristics)
        record['requested_characteristics']=args.characteristics
    if args.junction_c is not None:
        if not -40<=args.junction_c<=100: p.error('analysis junction range must be -40..100 C')
        command += ['--set=POWER_AUTO_COMPUTE_TJ=OFF',
                    '--set=POWER_TJ_VALUE='+str(args.junction_c)]
        record['requested_junction_c']=args.junction_c
    if args.vcd:
        vcd=args.vcd.resolve()
        command.append('--input_vcd='+str(vcd));record['vcd']=str(vcd)
        record['vcd_sha256']=sha(vcd)
    else: command.append('--no_input_file')
    meta=out/'receipt.json';meta.write_text(json.dumps(record,indent=2)+'\n')
    with (out/'run.log').open('w',encoding='utf-8') as log:
        completed=subprocess.run(command,cwd=project,stdout=log,stderr=subprocess.STDOUT)
    record['exit_code']=completed.returncode
    if flow.read_bytes()!=flow_bytes:
        power_flow=out/'post_power.flow.rpt'
        power_flow.write_bytes(flow.read_bytes())
        record['post_power_flow_sha256']=sha(power_flow)
        flow.write_bytes(flow_bytes)
        record['original_compile_flow_restored']=True
    for name,digest in bound.items():
        if sha(ROOT/name)!=digest: raise RuntimeError(f'Power analysis changed release build: {name}')
    record['release_inputs_unchanged']=True
    record['reports']={}
    for suffix in ['pow.rpt','pow.summary']:
        source=project/'output_files'/f'{revision}.{suffix}'
        if source.is_file():
            target=out/source.name;shutil.copyfile(source,target)
            record['reports'][target.relative_to(ROOT).as_posix()]=sha(target)
    record['finished_utc']=datetime.now(timezone.utc).isoformat()
    text=(out/'run.log').read_text(encoding='utf-8')
    record['ignored_settings']='Ignored setting' in text
    record['status']='PASS' if completed.returncode==0 and len(record['reports'])==2 and not record['ignored_settings'] else 'FAIL'
    meta.write_text(json.dumps(record,indent=2)+'\n')
    print(record['status'],meta,flush=True)
    if record['status']!='PASS': raise SystemExit(1)

if __name__=='__main__': main()
