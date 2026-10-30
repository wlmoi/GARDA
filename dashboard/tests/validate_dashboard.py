from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import json,hashlib,zipfile
R=Path(__file__).resolve().parents[1];D=R/'dist'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        for k in ['src','href']:
            if k in a:self.links.append(a[k])
p=Links();p.feed((D/'index.html').read_text(encoding='utf-8'))
assert len(p.ids)==len(set(p.ids)),'Duplicate DOM id'
checked=0
for link in p.links:
    if urlsplit(link).scheme:continue
    if link.startswith('#'):
        assert link=='#' or link[1:] in p.ids,link
        continue
    target=(D/unquote(link.split('#')[0])).resolve()
    assert target.is_relative_to(D.resolve()) and target.is_file(),link
    checked+=1
catalog=json.loads((D/'data/rtl-catalog.json').read_text(encoding='utf-8'))
assert len(catalog['modules'])==20 and len(catalog['asic_modules'])==4
assert len({m['file'] for m in catalog['modules']})==19
for m in catalog['modules']+catalog['asic_modules']:
    src=D/'source'/m['file'];assert src.is_file(),m['file']
    assert hashlib.sha256(src.read_bytes().replace(b'\r\n', b'\n')).hexdigest()==m['sha256'],m['file']
    canonical=R.parent/m['file']
    assert canonical.is_file() and src.read_bytes().replace(b'\r\n',b'\n')==canonical.read_bytes().replace(b'\r\n',b'\n'),'Snapshot differs from canonical source: '+m['file']
    assert all(p['direction'] in ['input','output','inout'] and p['bits'] for p in m['ports']),m['id']
for path in (D/'downloads').glob('*.zip'):
    with zipfile.ZipFile(path) as z:assert z.testzip() is None,path
with zipfile.ZipFile(D/'downloads/TINYTAPEOUT_SOURCE.zip') as z:
    for path in ['info.yaml','src/igor_neural_logic_top.v','test/test.py','test/Makefile','reference_model/neural_reference.py','assets/neural_24_64_64_4/bram_unified_weights.mem','requirements.txt']:
        assert path in z.namelist(),'Incomplete TinyTapeout source bundle: '+path
report=json.loads((D/'data/tinytapeout-report.json').read_text(encoding='utf-8'))
assert report['functional_pass'] is True
raw=json.loads((D/'data/tinytapeout-raw.json').read_text(encoding='utf-8'))
canonical_raw=json.loads((R.parent/'evidence/tinytapeout/current/verification.json').read_text(encoding='utf-8'))
assert raw==canonical_raw,'TinyTapeout evidence snapshot is stale'
for index,key in enumerate(['rtl','generic','cocotb','mapped','global_routing','detailed_routing','physical_signoff']):
    assert report['checks'][index]['status']==raw.get(key,{}).get('status','NOT_RUN').lower(),'Displayed status differs: '+key
gate=json.loads((D/'data/gate-model-verification.json').read_text(encoding='utf-8'))
assert gate['status']=='PASS' and gate['vectors']==3084 and gate['fault_codes_covered']==list(range(12))
assert gate['rtl_sha256']==hashlib.sha256((R.parent/gate['rtl_source']).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'Gate evidence refers to different RTL'
assert gate['browser_model_sha256']==hashlib.sha256((D/'gate-model.js').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'Gate evidence refers to different browser model'
config=json.loads((R.parent/'vercel.json').read_text())
assert config['framework'] is None and config['outputDirectory']=='dashboard/dist'
assert config['installCommand']=='' and config['buildCommand']==''
assert (D/'downloads/igor.sof').read_bytes()==(R.parent/'ImplementationReadyQuartus/IGOR_DE10_NANO/quartus/output_files/igor.sof').read_bytes(),'Published SOF differs'
for data in (D/'data').glob('*.json'):
    assert 'C:\\\\Users\\\\' not in data.read_text(encoding='utf-8'),'Local path published in '+data.name
print(json.dumps({'status':'PASS','local_links':checked,'fpga_modules':20,'asic_modules':4,'source_sha256_verified':24,'zip_crc':'PASS','browser_gate_vs_rtl':gate['vectors'],'tinytapeout_functional':report['functional_pass']}))
