"""Create a relative-path update ZIP for matching Jetson and DE10 workspaces."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=[
 'eth_direction.md','docs/connect_de10.md','tools/connect_de10.py','tools/de10_connect.py','tools/package_de10_connect.py','test/test_connect_de10.py',
 'src/igor_controller/igor_controller/ethernet_protocol.py',
 'src/igor_controller/igor_controller/fpga_bridge.py',
 'src/igor_controller/igor_controller/controller_node.py',
 'fpga/software_integration/src/igor_controller/igor_controller/ethernet_protocol.py',
 'fpga/software_integration/src/igor_controller/igor_controller/fpga_bridge.py',
 'fpga/software_integration/src/igor_controller/igor_controller/controller_node.py',
 'src/igor_pipeline/protocol/protocol_v2.h',
 'src/igor_pipeline/hps_de10/de10_udp_gateway.py',
 'src/igor_pipeline/hps_de10/de10_server_daemon.c',
 'src/igor_pipeline/hps_de10/de10_shared_mem_ext.c',
 'src/igor_pipeline/hps_de10/de10_shared_mem_ext.h',
 'src/igor_pipeline/hps_de10/Makefile',
 'src/igor_pipeline/hps_de10/igor-ethernet.service.example',
 'src/igor_pipeline/scripts/ethernet_test.py',
 'src/igor_pipeline/scripts/benchmark_latency.py',
 'src/igor_pipeline/scripts/uart_test.py',
 'tools/uart_diagnose.py',
 'src/igor_pipeline/scripts/uart_q88_vectors.json',
 'test/test_ethernet.py','tools/package_ethernet.py','tools/verify_ethernet.py']

def main():
    names=list(FILES)
    evidence=ROOT/'docs/ethernet_validation'
    if evidence.exists():names += [str(p.relative_to(ROOT)).replace('\\','/') for p in evidence.glob('*') if p.is_file()]
    manifest={'scope':'Software update only; no FPGA bitstream, Linux boot image or physical acceptance',
              'files':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}}
    path=ROOT/'tools/igor_ethernet_update.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in names:archive.write(ROOT/name,name)
        archive.writestr('ethernet_update_manifest.json',json.dumps(manifest,indent=2)+'\n')
    print(f'Packaged {len(names)} files: {path}')
    print('SHA256:',hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':main()
