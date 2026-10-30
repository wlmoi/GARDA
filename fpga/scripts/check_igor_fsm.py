"""Check native FSM document references, state encodings and source provenance."""
from pathlib import Path
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from igor_fsm_data import PAGES

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/assets/igor_fsm'
receipt=json.loads((OUT/'fsm_sources.json').read_text(encoding='utf-8'))
book=ROOT/'docs/assets/igor_fsm_all.drawio'
assert hashlib.sha256(book.read_bytes()).hexdigest()==receipt['drawio_sha256']
for name,digest in {**receipt['source_sha256'],**receipt['artifact_sha256']}.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
diagrams=ET.parse(book).findall('diagram')
assert len(diagrams)==len(PAGES)==19
assert {d.get('id') for d in diagrams}=={p['key'] for p in PAGES}
for diagram in diagrams:
    p=next(p for p in PAGES if p['key']==diagram.get('id'))
    cells=diagram.findall('.//mxCell')
    ids={c.get('id') for c in cells}
    assert len(ids)==len(cells),p['key']
    for c in cells:
        for key in ('parent','source','target'):
            assert c.get(key) is None or c.get(key) in ids,(p['key'],key,c.get(key))
    states={s['id'] for s in p['states']}
    assert states<=ids
    edges=[c for c in cells if c.get('edge')=='1']
    assert len(edges)==len(p['transitions'])+bool(p['reset']),p['key']
    for edge in p['transitions']:
        expected=' '.join(edge['label'].split())
        assert any(c.get('source')==edge['source'] and c.get('target')==edge['target']
                   and ' '.join(c.get('value','').split())==expected for c in edges),(p['key'],edge)
    for c in edges:
        assert c.get('value') and '\\n' not in c.get('value'),(p['key'],c.get('id'))
    svg=ET.parse(OUT/(p['key']+'.svg'))
    png=(OUT/(p['key']+'.png')).read_bytes()
    assert png[:8]==b'\x89PNG\r\n\x1a\n'
    dims=struct.unpack('>II',png[16:24])
    recorded=next(item for item in receipt['pages'] if item['key']==p['key'])
    assert dims==(recorded['width'],recorded['height']),p['key']

def encodings(name,expected):
    src=(ROOT/name).read_text(encoding='utf-8')
    values=dict((n,int(v)) for n,v in re.findall(r'\b(\w+)\s*=\s*\d+\s*\x27d(\d+)',src))
    for state,code in expected.items(): assert values.get(state)==code,(name,state,code)

core_names=['IDLE','BIAS_ADDRESS','BIAS_WAIT','BIAS_TAKE','WEIGHT_ADDRESS','WEIGHT_WAIT','MAC','ACTIVATE']
for path in ('experiments/parallel8/igor_src_policy_core.v','rtl/igor_src_policy/igor_src_policy_core.v'):
    encodings(path,dict(zip(core_names,range(8))))
mode_names=['RX','LOAD','START','RUN','CAP0','CAP1','CAP2','TX','TX_START_LAST','TX_END_LAST']
encodings('rtl/igor_src_policy/igor_src_policy_uart.v',dict(zip(mode_names,range(10))))
encodings('rtl/igor_top.v',dict(zip(['IDLE','RUN','RESULT','FAULT'],range(4))))
encodings('rtl/igor_rollout_tile.v',dict(zip(['IDLE','INIT','STEP','WAIT_RAM','SCORE','FINISH'],range(6))))

for name,expected in [('rtl/igor_uart_rx.v',set(range(4))),
                      ('rtl/igor_neural_core.v',set(range(8))),
                      ('rtl/igor_de10_nano_wrapper.v',set(range(7))|{8,9}),
                      ('rtl/igor_uart_protocol.v',set(range(8)))]:
    src=(ROOT/name).read_text(encoding='utf-8')
    groups=re.findall(r'(?m)^\s*(\d+(?:\s*,\s*\d+)*)\s*:',src)
    actual={int(n) for group in groups for n in re.findall(r'\d+',group)}
    assert actual==expected,(name,actual,expected)

core=(ROOT/'experiments/parallel8/igor_src_policy_core.v').read_text()
compact=re.sub(r'\s+','',core)
for snippet in ['elseif(abort)','elseif(fault)','if(neuron+8>=output_count)',
                "fault<=1;error_code<=6;",'done&&!fault&&!abort&&output_index<3']:
    assert snippet in compact,snippet
assert compact.index('elseif(abort)')<compact.index('elseif(fault)')<compact.index('case(state)')
policy=(ROOT/'rtl/igor_src_policy/igor_src_policy_uart.v').read_text()
assert 'task reject;' in policy and 'default: reject(8\'d10);' in policy
assert 'TX_START_LAST: if (tx_busy)' in policy and 'TX_END_LAST: if (!tx_busy)' in policy
assert 'result_valid && !estop_active && !core_fault' in policy
audited={p.relative_to(ROOT).as_posix() for p in (ROOT/'rtl').rglob('*.v')}
assert len(audited)==22 and audited<=receipt['source_sha256'].keys()
for doc in ['FSM_CORE_AND_CONTROLLERS.md','IGOR_CORE_DIAGRAM.md']:
    for target in re.findall(r'\]\(([^)]+)\)',(ROOT/'docs'/doc).read_text(encoding='utf-8')):
        if not target.startswith('https://'): assert (ROOT/'docs'/target).is_file(),target
result={'status':'PASS','kind':'documentation/source consistency; not a new RTL simulation or hardware test',
        'pages':len(diagrams),'common_rtl_files_audited':len(audited),'all_edges_named':True,
        'checks':['native XML IDs/endpoints','all transitions retained','numeric/named encodings matched',
                  'core abort/fault priority and output gating','policy last-byte handshake',
                  'SVG XML and PNG dimensions','local links','source and artifact SHA256']}
(OUT/'document_checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
