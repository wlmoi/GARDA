"""Package the current portable Q8.8 tools for Jetson installation."""
import base64
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'src/igor_pipeline/scripts'
FILES=['uart_test.py','uart_validate_q88.py','uart_validate_hardware_q88.py',
       'uart_q88_vectors.json','README_Q88.md']
TEMPLATE='''#!/usr/bin/env python3
"""Install all UART Q8.8 tools. Usage: python3 install_igor_uart_q88.py [~/igor_ws]"""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FILES = __FILES__

def main():
    root=Path(sys.argv[1]).expanduser().resolve() if len(sys.argv)>1 else Path.home()/'igor_ws'
    target=root/'src/igor_pipeline/scripts'
    if not target.is_dir():raise SystemExit(f'Workspace not found: {root}')
    try:import serial
    except ImportError:raise SystemExit('Install pyserial: python3 -m pip install --user pyserial')
    with tempfile.TemporaryDirectory(dir=target,prefix='uart-q88-stage-') as tmp:
        stage=Path(tmp)
        for name,item in FILES.items():
            if Path(name).name!=name:raise SystemExit('Invalid package filename')
            content=base64.b64decode(item['data'])
            if hashlib.sha256(content).hexdigest()!=item['sha256']:raise SystemExit(f'Bad checksum: {name}')
            if name.endswith('.py'):compile(content,name,'exec')
            (stage/name).write_bytes(content)
        subprocess.run([sys.executable,str(stage/'uart_test.py'),'--self-check'],check=True)
        subprocess.run([sys.executable,str(stage/'uart_validate_q88.py')],check=True)
        for name,item in FILES.items():
            destination=target/name
            if destination.exists():
                digest=hashlib.sha256(destination.read_bytes()).hexdigest()
                if digest!=item['sha256']:
                    backup=destination.with_name(name+'.backup-'+digest[:12])
                    if not backup.exists():shutil.copy2(destination,backup)
                shutil.copymode(destination,stage/name)
            (stage/name).replace(destination)
            print(f'Installed {destination}')
    print('PASS installed all Q8.8 tools. FPGA image must match --baud 9600.')
    print('Read: '+str(target/'README_Q88.md'))

if __name__=='__main__':main()
'''

def main():
    payload={}
    for name in FILES:
        p=SCRIPTS/name
        content=p.read_text(encoding='utf-8-sig').replace('\r\n','\n').encode()
        p.write_bytes(content)
        payload[name]={'sha256':hashlib.sha256(content).hexdigest(),
                       'data':base64.b64encode(content).decode()}
    installer=TEMPLATE.replace('__FILES__',repr(payload))
    (ROOT/'tools/install_igor_uart_q88.py').write_text(installer,encoding='utf-8',newline='\n')
    with zipfile.ZipFile(ROOT/'tools/igor_uart_q88.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:archive.write(SCRIPTS/name,name)
    # Existing single-script download links continue to install the current test.
    for name in ['install_igor_uart.py','install_igor_uart_9600.py']:
        p=ROOT/'tools'/name
        text=p.read_text(encoding='utf-8-sig')
        text=re.sub(r'^PAYLOAD = .*$', 'PAYLOAD = '+repr(payload['uart_test.py']['data']),text,flags=re.M)
        text=re.sub(r'^SHA256 = .*$', 'SHA256 = '+repr(payload['uart_test.py']['sha256']),text,flags=re.M)
        text=text.replace('--baud 921600','--baud 9600')
        p.write_text(text,encoding='utf-8',newline='\n')
    print('Packaged 5 files: tools/install_igor_uart_q88.py and tools/igor_uart_q88.zip')

if __name__=='__main__':main()
