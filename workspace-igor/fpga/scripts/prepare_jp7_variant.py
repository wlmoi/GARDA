"""Prepare a separate Parallel8 physical UART project for JP7 pins 1/2."""
import hashlib
import json
import shutil
from pathlib import Path

root=Path(__file__).resolve().parents[1]
base=root/'experiments/parallel8'
out=root/'experiments/parallel8_jp7'
out.mkdir(exist_ok=True)
names=['igor_src_policy_core.v','igor_src_policy_de10_nano.v','igor_src_policy.sdc']+[f'bank{i}.mem' for i in range(8)]
for name in names:
    shutil.copyfile(base/name,out/name)
pins=(base/'pin_assignment.tcl').read_text().replace('PIN_V12 -to UART_RX','PIN_Y15 -to UART_RX').replace('PIN_E8 -to UART_TX','PIN_AC24 -to UART_TX')
(out/'pin_assignment.tcl').write_text('# UART: JP7 pin 1 RX/Y15, pin 2 TX/AC24; GND pin 12.\n'+pins)
qsf=(base/'igor_src_policy.qsf').read_text().split('set_global_assignment -name LAST_QUARTUS_VERSION')[0]
(out/'igor_parallel8_jp7.qsf').write_text(qsf)
(out/'igor_parallel8_jp7.qpf').write_text('QUARTUS_VERSION = "25.1"\nPROJECT_REVISION = "igor_parallel8_jp7"\n')
(out/'source_manifest.json').write_text(json.dumps({
 'source_project':'fpga/experiments/parallel8',
 'unchanged_files':{n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in names},
 'uart_rx':{'header':'JP7','pin':1,'fpga_pin':'Y15'},
 'uart_tx':{'header':'JP7','pin':2,'fpga_pin':'AC24'},
 'ground':{'header':'JP7','pin':12},'baud':921600,'format':'8N1','logic_voltage':3.3,
 'pinout_source':'https://www.mouser.com/datasheet/2/598/DE10_Nano_User_manual_a_b-1108056.pdf#page=28'
},indent=2)+'\n')
print(out)
