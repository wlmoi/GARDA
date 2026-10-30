"""Explicit decision outcome coverage of the oracle-checked gate vector stream.

This is a source-reviewed functional decision model, not native expression
coverage, MC/DC, or a substitute for the simulator's structural database.
"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'fpga/evidence/current_safety'
vectors=BASE/'gate_vectors.hex'
summary=json.loads((BASE/'summary.json').read_text())
assert summary['status']=='PASS'
names=['reset','estop','protective_stop','not_ready','invalid_map','invalid_config',
       'arithmetic_fault','timeout','incomplete_result','speed_bound','slew_bound']
bins={n:{'false':0,'true':0} for n in names}
count=0
def signed7(x): return x-128 if x&64 else x
for line in vectors.read_text().splitlines():
    ctrl,cv,pv,mv,mdv,cw,pw,mw,mdw,expected=[int(x,16) for x in line.split()]
    c=[bool(ctrl&(1<<i)) for i in range(10)]
    cw,pw=signed7(cw),signed7(pw)
    decisions=[not c[0],c[2],c[3],not c[1],not c[4],not c[5],c[8],c[9],
               not c[7] or not c[6],cv>mv or abs(cw)>mw,
               abs(cv-pv)>mdv or abs(cw-pw)>mdw]
    actual=0
    for i,(name,value) in enumerate(zip(names,decisions),1):
        bins[name]['true' if value else 'false']+=1
        if value: actual=i;break
    assert actual==expected,(actual,expected)
    count+=1
hit=sum(int(v>0) for b in bins.values() for v in b.values())
out={'scope':'Source-reviewed functional gate decision outcomes on applied, oracle-checked vector stream',
     'cases':count,'covered':hit,'total':22,'percent':100*hit/22,'bins':bins,
     'vector_sha256':hashlib.sha256(vectors.read_bytes()).hexdigest(),
     'rtl_sha256':hashlib.sha256((ROOT/'fpga/rtl/igor_safety_security_gate.v').read_bytes()).hexdigest(),
     'limitations':'Not native branch/expression/MC-DC coverage; checks modeled decisions reached after higher-priority decisions are false.'}
(ROOT/'fpga/evidence/rtl_coverage/gate_decision_model.json').write_text(json.dumps(out,indent=2)+'\n')
print(count,'cases;',hit,'/22 modeled decision outcomes =',out['percent'],'percent')
