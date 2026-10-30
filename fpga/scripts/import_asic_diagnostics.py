"""Import user-provided ASIC diagnostics as immutable, source-attributed evidence."""
from pathlib import Path, PurePosixPath
import argparse,csv,hashlib,json,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/asic_import/gds_diagnostics_1'
def sha(data): return hashlib.sha256(data).hexdigest()
def write_csv(name,header,rows):
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)
def leaves(obj,pointer=''):
    if isinstance(obj,dict):
        for key,value in obj.items(): yield from leaves(value,pointer+'/'+str(key).replace('~','~0').replace('/','~1'))
    elif isinstance(obj,list):
        for i,value in enumerate(obj): yield from leaves(value,pointer+'/'+str(i))
    else: yield pointer,obj
def unit(key):
    if key.startswith('power__'): return 'W'
    if 'area' in key: return 'um^2'
    if 'utilization' in key: return 'ratio'
    if 'drop' in key or 'voltage' in key: return 'V'
    if any(x in key for x in ['__ws','__wns','__tns','clock__skew']): return 'ns'
    if 'wirelength' in key or 'displacement' in key: return 'um'
    if any(x in key for x in ['count','route__net','route__vias','design__io','design__rows','design__sites','antenna_diodes']): return 'count'
    return 'raw; see source definition'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    archive=OUT/'source.zip'
    if args.archive.resolve()!=archive.resolve(): shutil.copyfile(args.archive,archive)
    inventory=[]; scalars=[]; power=[]; docs={}
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None,'ZIP CRC failure'
        for entry in z.infolist():
            name=entry.filename; path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name: raise ValueError('Unsafe ZIP path: '+name)
            if entry.is_dir(): continue
            data=z.read(name); digest=sha(data)
            inventory.append([name,entry.file_size,entry.compress_size,digest,entry.CRC,'archive-only binary' if path.suffix=='.odb' else 'raw/'+name])
            if path.suffix=='.odb': continue  # Binary database retained losslessly inside source.zip.
            target=OUT/'raw'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            if path.suffix=='.json':
                obj=json.loads(data);docs[name]=obj
                for pointer,value in leaves(obj): scalars.append([name,pointer,json.dumps(value,ensure_ascii=True),type(value).__name__,digest])
            if name.endswith('/power.rpt'):
                text=data.decode(); corner=re.search(r'=+\s+(\S+) Corner',text)
                for i,line in enumerate(text.splitlines(),1):
                    match=re.match(r'^(Sequential|Combinational|Clock|Macro|Pad|Total)\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)',line)
                    if match:
                        values=list(map(float,match.groups()[1:])); internal,switching,leakage,total=values
                        assert abs(internal+switching+leakage-total)<max(1e-10,abs(total)*2e-6),(name,line)
                        power.append([name,i,corner[1] if corner else 'single-corner step',match[1],*values,(internal+switching)*1000,total*1000,digest])
    write_csv('archive_inventory.csv',['archive_member','bytes','compressed_bytes','sha256','crc32','preservation'],inventory)
    write_csv('all_json_values.csv',['source_member','json_pointer','raw_value','python_type','source_sha256'],scalars)
    write_csv('all_power_reports.csv',['source_member','line','corner','group','internal_W','switching_W','leakage_W','total_W','dynamic_mW','total_mW','source_sha256'],power)
    name='runs/wokwi/final/metrics.json';metrics=docs[name];text=(OUT/'raw'/name).read_text()
    rows=[]
    for key,value in metrics.items():
        line=next(i for i,s in enumerate(text.splitlines(),1) if json.dumps(key)+':' in s)
        rows.append([key,value,unit(key),name,line,sha((OUT/'raw'/name).read_bytes())])
    write_csv('final_metrics.csv',['metric','raw_value','unit','source_member','line','source_sha256'],rows)
    config=docs['runs/wokwi/56-openroad-stapostpnr/config.json']
    final_power=[r for r in power if '/56-openroad-stapostpnr/' in r[0] and r[3]=='Total']
    typ=next(r for r in final_power if r[2]=='nom_typ_1p20V_25C')
    assert abs(metrics['power__total']-typ[7])<1e-9
    summary={'status':'IMPORTED_NOT_TAPEOUT_SIGNOFF','source_archive_sha256':sha(archive.read_bytes()),
             'archive_members':len(inventory),'json_leaf_values':len(scalars),'final_metrics':len(metrics),'power_rows':len(power),
             'design_name':config['DESIGN_NAME'],'pdk':config['PDK'],'clock_period_ns':config['CLOCK_PERIOD'],
             'macros':list(config['MACROS']),'power_postroute_total_rows':final_power,
             'source_configuration':{'ERROR_ON_ILLEGAL_OVERLAPS':docs['src/config.json'].get('ERROR_ON_ILLEGAL_OVERLAPS'), 'RUN_MAGIC_DRC':docs['src/config.json'].get('RUN_MAGIC_DRC')},
             'rtl_binding':'Results attributed to archive top tt_um_igorchip; source commit/equivalence to local Parallel8 not established by this archive.',
             'silicon_measurement':False,'precheck_or_gl_job_success_proven':False,
             'nonzero_signoff_metrics':{k:metrics[k] for k in ['timing__setup__ws','timing__setup__tns','timing__setup_vio__count','design__max_slew_violation__count','design__max_cap_violation__count','design__max_fanout_violation__count','magic__illegal_overlap__count']},
             'final_metrics_raw':metrics}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# ASIC diagnostics imported from user archive','',
           f'Top: **{config["DESIGN_NAME"]}**; PDK: **{config["PDK"]}**; clock constraint **{config["CLOCK_PERIOD"]} ns**.',
           'These are results of the RTL/design used in the supplied run, not a new local build or measured silicon.',
           'No equivalence to the local FPGA Parallel8 model or source commit is inferred.','',
           '## Post-route power','', '| Corner | Internal mW | Switching mW | Dynamic mW | Leakage mW | Total mW |','|---|---:|---:|---:|---:|---:|']
    for r in final_power: lines.append(f'| {r[2]} | {r[4]*1000:.9g} | {r[5]*1000:.9g} | {r[8]:.9g} | {r[6]*1000:.9g} | {r[9]:.9g} |')
    lines+=['','Internal + switching = dynamic. Do not call switching alone total dynamic.',
            'Pad group is reported as zero: this is not proof of zero package/shuttle/board I/O power.',
            'No VCD/SAIF or activity-coverage evidence was established in this archive; no Quartus confidence label is assigned.','',
            '## Sign-off observations','',
            f'- Worst setup: **{metrics["timing__setup__ws"]} ns**; TNS **{metrics["timing__setup__tns"]} ns**; **{metrics["timing__setup_vio__count"]} setup violations**.',
            f'- Max slew/cap/fanout violation counts: **{metrics["design__max_slew_violation__count"]} / {metrics["design__max_cap_violation__count"]} / {metrics["design__max_fanout_violation__count"]}**.',
            f'- Illegal overlap metric: **{metrics["magic__illegal_overlap__count"]}**. Requires rule/waiver review; do not silently treat as zero.',
            '- Source config has `ERROR_ON_ILLEGAL_OVERLAPS=false` and `RUN_MAGIC_DRC=false`. A completed flow is not proof that these checks passed.',
            f'- KLayout DRC: {metrics["klayout__drc_error__count"]}; routing DRC: {metrics["route__drc_errors"]}; LVS errors: {metrics["design__lvs_error__count"]}; antenna count: {metrics["route__antenna_violation__count"]}.',
            '- Workflow YAML describes requested jobs; it does not establish their exit status. Precheck and gate-level success need their actual artifacts.',
            '- 50 MHz is the configured target; the negative slow-corner setup slack prevents claiming qualified all-corner 50 MHz.',
            '- Inference-cycle count, algorithm accuracy and physical silicon power are not established by this diagnostics package.','',
            '- GDS/OAS, SPEF and SDF are referenced by paths in state JSON but are not included as those file types in this archive. Their paths alone do not provide layout hashes or a reproducible gate-level/timing run.','',
            '## Complete numeric records','',
            f'- [Final metrics CSV](final_metrics.csv): **{len(metrics)}** original metrics, source lines, units and SHA.',
            f'- [All JSON values](all_json_values.csv): **{len(scalars)}** leaf values from every JSON, including each stage/config; JSON pointers preserve identity.',
            f'- [All power reports](all_power_reports.csv): **{len(power)}** group rows across stages/corners. Do not mix pre-route with post-route.',
            '- [Raw final metrics](raw/runs/wokwi/final/metrics.json) and [post-route timing](raw/runs/wokwi/56-openroad-stapostpnr/summary.rpt).',
            '- [Archive inventory](archive_inventory.csv): member SHA/CRC and preservation location for every file.',
            '- [Original source.zip](source.zip) preserves all bytes, including ODB databases. All non-ODB files are also extracted under `raw/`.',
            '- [Summary JSON](summary.json) retains every final metric without rounding.','',
            '## Every final metric','', '| Metric | Raw value | Unit |','|---|---:|---|']
    for key,value,units,*_ in rows: lines.append(f'| `{key}` | {value} | {units} |')
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    manifest={p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['status','design_name','pdk','archive_members','json_leaf_values','final_metrics','power_rows','nonzero_signoff_metrics']},indent=2))
if __name__=='__main__':main()
