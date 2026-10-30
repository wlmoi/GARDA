"""Run the existing protocol-engine suite and bind presentation claims to its inputs."""
from pathlib import Path
import datetime,hashlib,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent
OUT=ROOT/'evidence/chip_highlights'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=[WORKSPACE/'src'/n for n in ['defines.vh','igorchip_top.v','program_host.v','program_memory.v','sram_256x16_bb.v']]
    files+=list((WORKSPACE/'tools').rglob('*.py'))+list((WORKSPACE/'test').glob('test_*.py'))
    files += [WORKSPACE/'test/integration_tb.v']+list((WORKSPACE/'test/ihp_sram').glob('*.v'))
    before={p.relative_to(WORKSPACE).as_posix():sha(p) for p in sorted(set(files))}
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONIOENCODING']='utf-8'
    env['PATH']='C:/iverilog/bin'+os.pathsep+env.get('PATH','')
    for key in ['JP_TEST_FPGA','JP_TEST_REGISTER']:env.pop(key,None)
    tmp=ROOT/'.runtime/highlights_tmp';tmp.mkdir(parents=True,exist_ok=True)
    env['TMP']=str(tmp);env['TEMP']=str(tmp)
    command=[sys.executable,'-B','-m','unittest','discover','-s','test','-p','test_*.py','-v']
    with (OUT/'regression.log').open('w',encoding='utf-8') as stream:
        run=subprocess.run(command,cwd=WORKSPACE,env=env,stdout=stream,stderr=subprocess.STDOUT)
    log=(OUT/'regression.log').read_text(encoding='utf-8')
    count=re.search(r'Ran (\d+) tests? in ([\d.]+)s',log)
    unchanged=before=={p.relative_to(WORKSPACE).as_posix():sha(p) for p in sorted(set(files))}
    passed=run.returncode==0 and count is not None and re.search(r'^OK\s*$',log,re.M) is not None and unchanged
    result={'status':'PASS' if passed else 'FAIL','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'command':command,'memory_mode':'ASIC SRAM behavioral models; SIM and FUNCTIONAL',
            'tests':int(count[1]) if count else None,'elapsed_seconds':float(count[2]) if count else None,
            'exit_code':run.returncode,'source_unchanged':unchanged,'source_sha256':before,
            'log_sha256':sha(OUT/'regression.log'),'scope':'Existing local RTL/model/host/SRAM/tool regressions; no new physical sign-off run.'}
    (OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','tests','elapsed_seconds','source_unchanged']},indent=2))
    if not passed:raise SystemExit(1)
if __name__=='__main__':main()
