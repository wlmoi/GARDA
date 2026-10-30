"""Index every Python test and SV checkpoint without inventing execution results."""
import ast
import csv
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'fpga/evidence/rtl_coverage'
OUT.mkdir(parents=True,exist_ok=True)
rows=[]
for directory in ['fpga/verification','fpga/test','test','fpga/experiments/parallel8']:
    base=ROOT/directory
    if not base.exists(): continue
    for p in sorted(base.rglob('*')):
        if any(part in ['build','artifacts','__pycache__'] for part in p.parts): continue
        if p.suffix=='.py':
            try: tree=ast.parse(p.read_text(encoding='utf-8-sig'))
            except (SyntaxError,UnicodeError): continue
            for node in ast.walk(tree):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                    rows.append({'source':p.relative_to(ROOT).as_posix(),'line':node.lineno,'kind':'Python test definition','name':node.name,'description':ast.get_docstring(node) or node.name[5:].replace('_',' '),'execution':'See suite receipt; definition alone is not PASS'})
        if p.suffix in ['.sv','.v'] and p.name.startswith('tb'):
            for n,line in enumerate(p.read_text().splitlines(),1):
                for match in re.finditer(r'checkpoint\s*\(\s*"([^"]+)"',line):
                    rows.append({'source':p.relative_to(ROOT).as_posix(),'line':n,'kind':'RTL named checkpoint','name':match[1],'description':match[1].replace('_',' '),'execution':'See suite log/receipt'})
with (OUT/'test_inventory.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=['source','line','kind','name','description','execution'])
    writer.writeheader();writer.writerows(rows)
summary=[]
for p in sorted(OUT.glob('*/receipt.json')):
    record=json.loads(p.read_text())
    if record.get('status')=='PASS':
        for r in record.get('coverage',[]): summary.append({'suite':record['suite'],**r})
(OUT/'coverage_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['# Measured RTL coverage','', 'Raw, unwaived DUT counters; percent = hit / total x 100. Testbench excluded.', '', '| Suite | RTL | Metric | Hit / Total | Percent |','| --- | --- | --- | ---: | ---: |']
for r in summary: lines.append(f"| {r['suite']} | {Path(r['file']).name} | {r['metric']} | {r['hit']} / {r['total']} | {r['percent']:.2f}% |")
lines += ['', 'An absent metric is NOT MEASURED, never inferred as 0% or 100%.', '', 'Inventory definitions/checkpoints: '+str(len(rows))+'. Inventory is not an executed-test count.', '', 'Pass-rate evidence (separate from code coverage):','', '| Suite | Passed / Executed | Pass rate |','| --- | ---: | ---: |']
for label,relative in [('Host','current_host/results.json'),('LiDAR','current_lidar/results.json')]:
    p=ROOT/'fpga/evidence'/relative
    if p.exists():
        r=json.loads(p.read_text()); total=r['tests']; hit=total-r['failures']-r['errors']
        lines.append(f'| {label} | {hit} / {total} | {100*hit/total:.2f}% |')
lines+=['', 'Acceptance thresholds are project review criteria in ../../VERIFICATION_GUIDE.md; not ISO thresholds.', 'All emitted counter bins are included. Constant/unused bits remain visible in the raw toggle denominator.']
lines+=['', '## Explicit functional coverage models (separate from native code coverage)','', '| Model | Hit / Total | Percent |','| --- | ---: | ---: |']
p=OUT/'fsm_observation.json'
if p.exists():
    r=json.loads(p.read_text())
    for key in ['state_coverage','normal_arc_coverage']:
        v=r[key];lines.append(f"| Core FSM {key} | {v['hit']} / {v['total']} | {v['percent']:.2f}% |")
p=OUT/'gate_decision_model.json'
if p.exists():
    r=json.loads(p.read_text());lines.append(f"| Gate reachable modeled decision outcomes | {r['covered']} / {r['total']} | {r['percent']:.2f}% |")
lines+=['', 'Functional models have explicit reviewed denominators; these are not native FSM/condition/MC-DC measurements. See individual JSON limitations.']
(OUT/'COVERAGE_RESULTS.md').write_text('\n'.join(lines)+'\n')
details=['# Test and checkpoint inventory','', 'Nama dan uraian berikut menunjuk definisi tes, bukan klaim bahwa semua tes telah dijalankan. Cocokkan dengan log/receipt suite. Proses setup, stimulus, oracle dan cara menjalankan tersedia pada VERIFICATION_GUIDE.md.','']
for r in rows:
    details.append(f"- `{r['source']}:{r['line']}` — **{r['name']}**: {r['description']}")
(OUT/'TEST_INVENTORY.md').write_text('\n'.join(details)+'\n',encoding='utf-8')
with (OUT/'coverage_summary.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['suite','file','metric','hit','total','percent']);w.writeheader();w.writerows(summary)
print('Indexed',len(rows),'test/checkpoint definitions; coverage rows',len(summary))
