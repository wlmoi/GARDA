"""Compare the browser companion model against the ACTUAL Verilog gate."""
from pathlib import Path
import json,subprocess,random,shutil,hashlib,os,shlex
R=Path(__file__).resolve().parents[1]
repo=R.parent;rtl=repo/'rtl/garda_safety_security_gate.v'
out=R/'tests/artifacts';out.mkdir(parents=True,exist_ok=True)
defaults=dict(rst_n=1,ready=1,estop=0,protective_stop=0,map_ok=1,cfg_ok=1,result_valid=1,all_done=1,arithmetic_fault=0,timeout=0,candidate_v=12,previous_v=12,max_v=20,max_dv=8,candidate_w=4,previous_w=4,max_w=20,max_dw=12)
vectors=[defaults.copy()]
for flag,value in [('rst_n',0),('estop',1),('protective_stop',1),('ready',0),('map_ok',0),('cfg_ok',0),('arithmetic_fault',1),('timeout',1),('all_done',0),('candidate_v',31),('candidate_v',0)]:
    vectors.append({**defaults,flag:value})
rng=random.Random(15102026)
flags=list(defaults)[:10]
for mask in range(1024):
    v=defaults.copy()
    for j,key in enumerate(flags):v[key]=(mask>>j)&1
    vectors.append(v)
for i in range(2048):
    v={**defaults,'candidate_v':rng.randrange(32),'previous_v':rng.randrange(32),'max_v':rng.randrange(32),'max_dv':rng.randrange(32),'candidate_w':rng.randrange(-64,64),'previous_w':rng.randrange(-64,64),'max_w':rng.randrange(128),'max_dw':rng.randrange(128)}
    if i%4==0:
        key=rng.choice(flags);v[key]=1-v[key]
    vectors.append(v)
(out/'vectors.json').write_text(json.dumps(vectors),encoding='utf-8')
runner="import fs from 'node:fs';\nimport {evaluateGate} from "+json.dumps((R/'dist/gate-model.js').as_uri())+";\nconst vectors=JSON.parse(fs.readFileSync(new URL('./vectors.json',import.meta.url)));fs.writeFileSync(new URL('./browser-results.json',import.meta.url),JSON.stringify(vectors.map(evaluateGate)));"
(out/'run-model.mjs').write_text(runner,encoding='utf-8')
subprocess.run(['node',str(out/'run-model.mjs')],check=True)
names=list(defaults)
decl='reg rst_n,ready,estop,protective_stop,map_ok,cfg_ok,result_valid,all_done,arithmetic_fault,timeout;\nreg [4:0] candidate_v,previous_v,max_v,max_dv;\nreg signed [6:0] candidate_w,previous_w;\nreg [6:0] max_w,max_dw;\nwire motor_enable; wire [4:0] v_command;wire signed [6:0] omega_command;wire [7:0] fault_code;'
ports=names+['motor_enable','v_command','omega_command','fault_code']
tb='`timescale 1ns/1ps\nmodule tb;\n'+decl+'\ngarda_safety_security_gate dut('+','.join('.'+n+'('+n+')' for n in ports)+');\ninitial begin\n'
for i,v in enumerate(vectors):
    tb+=' '.join(k+'='+str(v[k])+';' for k in names)+' #1; $display("CHECK '+str(i)+' %0d %0d %0d %0d",motor_enable,v_command,omega_command,fault_code);\n'
tb+='$finish;end\nendmodule\n'
(out/'tb.v').write_text(tb,encoding='utf-8')
if os.name=='nt' and shutil.which('wsl'):
    def linux(p):return '/mnt/'+str(p.drive)[0].lower()+str(p).replace('\\','/')[2:]
    command='iverilog -g2012 -s tb -o '+shlex.quote(linux(out/'sim.vvp'))+' '+shlex.quote(linux(rtl))+' '+shlex.quote(linux(out/'tb.v'))+' && vvp '+shlex.quote(linux(out/'sim.vvp'))
    p=subprocess.run(['wsl','bash','-lc',command],check=True,capture_output=True,text=True)
else:
    subprocess.run([shutil.which('iverilog') or 'iverilog','-g2012','-s','tb','-o',str(out/'sim.vvp'),str(rtl),str(out/'tb.v')],check=True,capture_output=True)
    p=subprocess.run([shutil.which('vvp') or 'vvp',str(out/'sim.vvp')],check=True,capture_output=True,text=True)
actual=[list(map(int,l.split()[2:])) for l in p.stdout.splitlines() if l.startswith('CHECK ')]
browser=json.loads((out/'browser-results.json').read_text());expected=[[v[k] for k in ['motor_enable','v_command','omega_command','fault_code']] for v in browser]
assert len(actual)==len(vectors)
for i,(a,b) in enumerate(zip(actual,expected)):
    if a!=b:raise AssertionError({'index':i,'input':vectors[i],'rtl':a,'browser':b})
codes=sorted(set(x[-1] for x in actual));assert codes==list(range(12)),codes
report={'status':'PASS','test':'Browser behavior model vs actual Icarus Verilog RTL','vectors':len(vectors),'fault_codes_covered':codes,'rtl_source':'rtl/garda_safety_security_gate.v','rtl_sha256':hashlib.sha256(rtl.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'browser_model_sha256':hashlib.sha256((R/'dist/gate-model.js').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'text_hash_normalization':'CRLF to LF','simulation_in_browser':False,'seed':15102026}
(R/'dist/data/gate-model-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
