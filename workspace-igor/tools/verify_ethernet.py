"""Record software interoperability/regression evidence; no physical board claims."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/ethernet_validation'

def main():
    OUT.mkdir(exist_ok=True)
    results={'scope':'Localhost UDP + simulated UART; native C wire/HAL tests; no physical board acceptance',
             'utc':datetime.now(timezone.utc).isoformat(),'hardware_verified':False,'suites':{}}
    suites={
      'connection':['-m','unittest','discover','-s','test','-p','test_connect_de10.py'],
      'ethernet':['-m','unittest','discover','-s','test','-p','test_ethernet.py'],
      'uart':['-m','unittest','discover','-s','test','-p','test_uart*.py'],
      'host':['fpga/verification/run_host_regression.py']}
    for name,args in suites.items():
        result=subprocess.run([sys.executable]+args,cwd=ROOT,capture_output=True,text=True)
        log=result.stdout+result.stderr;(OUT/f'{name}.log').write_text(log,encoding='utf-8')
        count=re.search(r'Ran (\d+) tests',log)
        results['suites'][name]={'passed':result.returncode==0,'tests':int(count[1]) if count else None,'log':f'{name}.log'}
        print(name,results['suites'][name],flush=True)
        result.check_returncode()
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as reserve:
        reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
    with (OUT/'gateway_cli.log').open('w',encoding='utf-8') as stream:
        server=subprocess.Popen([sys.executable,'-u','src/igor_pipeline/hps_de10/de10_udp_gateway.py',
            '--bind','127.0.0.1','--port',str(port),'--backend','mock','--allow-client','127.0.0.1'],
            cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        try:
            end=time.perf_counter()+5
            while time.perf_counter()<end:
                if server.poll() is not None:raise RuntimeError('Gateway exited during startup')
                if 'NETWORK TEST ONLY' in (OUT/'gateway_cli.log').read_text():break
                time.sleep(.05)
            else:raise RuntimeError('Gateway startup deadline expired')
            command=[sys.executable,'src/igor_pipeline/scripts/ethernet_test.py','--host','127.0.0.1',
                     '--port',str(port),'--iter','3']
            positive=subprocess.run(command+['--network-only'],cwd=ROOT,capture_output=True,text=True)
            negative=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            (OUT/'cli_network_only.log').write_text(positive.stdout+positive.stderr)
            (OUT/'cli_production_rejects_mock.log').write_text(negative.stdout+negative.stderr)
            assert positive.returncode==0 and negative.returncode==1
            assert 'mode=NETWORK TEST ONLY' in positive.stdout and 'Backend status 6' in negative.stdout
            results['cli_smoke']={'network_only_passed':True,'production_rejected_mock':True}
        finally:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
    files=[ROOT/'eth_direction.md',ROOT/'docs/connect_de10.md',ROOT/'test/test_ethernet.py',ROOT/'test/test_connect_de10.py',ROOT/'tools/connect_de10.py',ROOT/'tools/de10_connect.py',ROOT/'tools/package_de10_connect.py',Path(__file__).resolve()]
    for folder in ['src/igor_controller/igor_controller','src/igor_pipeline/hps_de10',
                   'src/igor_pipeline/protocol','src/igor_pipeline/scripts',
                   'fpga/software_integration/src/igor_controller/igor_controller']:
        files += [p for p in (ROOT/folder).glob('*') if p.is_file() and p.suffix in ('.py','.h','.c','.json','.example')]
    results['source_sha256']={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print('PASS regression and real-process localhost CLI checks; evidence:',OUT,flush=True)

if __name__=='__main__':main()
