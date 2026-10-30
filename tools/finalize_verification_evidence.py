"""Validate source-bound coverage evidence and package the reviewable results."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'fpga/evidence/rtl_coverage'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'scope':'Measured RTL simulation coverage; no physical sign-off or ISO certification',
          'suites':{},'files':{}}
for suite in ['core','uart','board','gate']:
    folder=OUT/suite
    receipt=json.loads((folder/'receipt.json').read_text())
    assert receipt['status']=='PASS',(suite,receipt['status'])
    assert 'PASS ' in (folder/'simulation.log').read_text()
    for relative,digest in receipt['sha256'].items():
        assert sha(ROOT/relative)==digest,('Source drift',relative)
    for row in receipt['coverage']:
        assert 0<=row['hit']<=row['total'] and row['total']>0
        assert abs(row['percent']-100*row['hit']/row['total'])<1e-8
    manifest['suites'][suite]={'status':'PASS','raw_coverage_sha256':sha(folder/'coverage.dat')}
for p in sorted(OUT.rglob('*')):
    if p.is_file() and 'obj_dir' not in p.parts and not p.name.startswith('bank') and p.name!='manifest.json':
        manifest['files'][p.relative_to(ROOT).as_posix()]=sha(p)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
selected=[ROOT/'fpga/VERIFICATION_GUIDE.md',ROOT/'fpga/PROFESSOR_FEEDBACK_AUDIT.md',
          ROOT/'fpga/Bennaya.md',ROOT/'tools/append_professor_feedback.py',
          ROOT/'fpga/evidence/bennaya_answers/professor_feedback_append_receipt.json']
selected+=list(OUT.rglob('*'))
selected+=list((ROOT/'tools').glob('*coverage*.*'))
selected+=[ROOT/'tools/build_verification_inventory.py',ROOT/'tools/measure_core_fsm.py',ROOT/'tools/measure_gate_decisions.py',Path(__file__).resolve(),ROOT/'fpga/verification/src_policy/coverage_illegal_state.svh']
for receipt in OUT.glob('*/receipt.json'):
    selected += [ROOT/p for p in json.loads(receipt.read_text())['sha256']]
selected += list((ROOT/'fpga/verification/src_policy/artifacts').glob('*.hex'))
selected += [ROOT/'fpga/verification/src_policy/artifacts/results.json',
             ROOT/'fpga/evidence/current_safety/gate_vectors.hex',
             ROOT/'fpga/evidence/current_safety/summary.json',
             ROOT/'fpga/evidence/parallel8_wave_proof/core/core.vcd',
             ROOT/'fpga/evidence/parallel8_wave_proof/simulation_receipt.json']
target=ROOT/'fpga/evidence/rtl_coverage_evidence.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(selected)):
        if p.is_file() and 'obj_dir' not in p.parts and '__pycache__' not in p.parts:
            z.write(p,p.relative_to(ROOT).as_posix())
print('Validated all 4 PASS receipts and source hashes; archive:',target,'bytes:',target.stat().st_size)
