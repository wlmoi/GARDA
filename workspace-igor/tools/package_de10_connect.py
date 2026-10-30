"""Build one self-contained Jetson connection script, including gateway/client assets."""
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NAMES=['tools/connect_de10.py','src/igor_controller/igor_controller/ethernet_protocol.py',
       'src/igor_pipeline/hps_de10/de10_udp_gateway.py','src/igor_pipeline/scripts/ethernet_test.py',
       'src/igor_pipeline/scripts/uart_q88_vectors.json']
TEMPLATE='''#!/usr/bin/env python3
"""Satu file mandiri. Jalankan di Jetson: python3 de10_connect.py [opsi].
Menyiapkan asset terverifikasi di .igor_de10_connect/ di sebelah file ini.
"""
import base64
import hashlib
import io
from pathlib import Path
import runpy
import tempfile
import zipfile

PAYLOAD = __PAYLOAD__
PAYLOAD_SHA256 = __SHA__
MANIFEST = __MANIFEST__
VERSION = __VERSION__

def main():
    data=base64.b64decode(PAYLOAD)
    if hashlib.sha256(data).hexdigest()!=PAYLOAD_SHA256:raise SystemExit('Checksum bundle gagal')
    root=Path(__file__).resolve().parent/'.igor_de10_connect'/VERSION
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if set(archive.namelist())!=set(MANIFEST):raise SystemExit('Isi bundle tidak sesuai manifest')
        contents={name:archive.read(name) for name in MANIFEST}
        for name,content in contents.items():
            if hashlib.sha256(content).hexdigest()!=MANIFEST[name]:raise SystemExit('Checksum asset gagal: '+name)
        for name,content in contents.items():
            target=(root/name).resolve()
            if root.resolve() not in target.parents:raise SystemExit('Path bundle tidak valid')
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest()!=MANIFEST[name]:
                    raise SystemExit('Asset cache berubah; gunakan salinan baru script pada folder lain: '+str(target))
                continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as stage:
                stage.write(content);temporary=Path(stage.name)
            temporary.replace(target)
    runpy.run_path(str(root/'tools/connect_de10.py'),run_name='__main__')

if __name__=='__main__':main()
'''

def main():
    manifest={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in NAMES}
    version=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:16]
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in NAMES:archive.write(ROOT/name,name)
    data=stream.getvalue()
    text=TEMPLATE.replace('__PAYLOAD__',repr(base64.b64encode(data).decode()))
    text=text.replace('__SHA__',repr(hashlib.sha256(data).hexdigest())).replace('__MANIFEST__',repr(manifest)).replace('__VERSION__',repr(version))
    path=ROOT/'tools/de10_connect.py';path.write_text(text,encoding='utf-8',newline='\n')
    print('Generated standalone:',path,'version',version)

if __name__=='__main__':main()
