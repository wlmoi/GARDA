"""Compare candidate power with baseline at the same stated model conditions."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
sof=HERE/'output_files/igor_src_policy.sof'
assert sof.is_file(),'Complete fitting first'
identity=sha(sof)
flow=HERE/'output_files/igor_src_policy.flow.rpt'
original=flow.read_bytes()
for profile,settings in [('typical',[]),('maximum_tj100',['--set=POWER_USE_DEVICE_CHARACTERISTICS=MAXIMUM','--set=POWER_AUTO_COMPUTE_TJ=OFF','--set=POWER_TJ_VALUE=100'])]:
    out=HERE/'artifacts/power'/profile; out.mkdir(parents=True,exist_ok=True)
    command=['D:/Quartus-Program/quartus/bin64/quartus_pow.exe','igor_src_policy',
             '--read_settings_files=on','--write_settings_files=off','--estimate_power=on',
             '--use_vectorless_estimation=on','--no_input_file']+settings
    run=subprocess.run(command,cwd=HERE,capture_output=True,text=True)
    log=run.stdout+run.stderr
    (out/'run.log').write_text(log)
    assert run.returncode==0 and 'Ignored setting' not in log,log[-3000:]
    for suffix in ['pow.rpt','pow.summary']:
        source=HERE/f'output_files/igor_src_policy.{suffix}'
        (out/source.name).write_bytes(source.read_bytes())
    (out/'post_power.flow.rpt').write_bytes(flow.read_bytes());flow.write_bytes(original)
    assert sha(sof)==identity
    record={'status':'PASS','command':command,'sof_sha256':identity,
            'kind':'Estimated FPGA thermal power; Low confidence; HPS excluded; not board measurement',
            'sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='receipt.json'}}
    (out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    print(profile, (out/'igor_src_policy.pow.summary').read_text(),flush=True)
