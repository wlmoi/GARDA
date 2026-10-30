"""Prepare an isolated JTAG console project; never changes the accepted image."""
from pathlib import Path
import hashlib, json, shutil

root = Path(__file__).resolve().parents[1]
out = root / 'experiments/parallel8_jtag'
out.mkdir(exist_ok=True)
base = root / 'experiments/parallel8'
for name in ['igor_src_policy_core.v', 'pin_assignment.tcl', 'igor_src_policy.sdc'] + [f'bank{i}.mem' for i in range(8)]:
    shutil.copyfile(base / name, out / name)
pins=(out/'pin_assignment.tcl').read_text()
pins='\n'.join(line for line in pins.splitlines() if not ('UART_RX' in line and not line.startswith('foreach')))
pins=pins.replace(' UART_RX','')
(out/'pin_assignment.tcl').write_text(pins+'\n')
sdc=(out/'igor_src_policy.sdc').read_text()
(out/'igor_src_policy.sdc').write_text('\n'.join(line for line in sdc.splitlines() if 'UART_RX' not in line)+'\n')
qsf = (base / 'igor_src_policy.qsf').read_text().split('set_global_assignment -name LAST_QUARTUS_VERSION')[0]
qsf = qsf.replace('igor_src_policy_de10_nano', 'igor_jtag_top')
qsf += '\nset_global_assignment -name VERILOG_FILE igor_jtag_console.v\n'
ip = 'D:/Quartus-Program/ip/altera/sopc_builder_ip/altera_avalon_jtag_uart/'
for name in ['altera_avalon_jtag_uart', 'altera_avalon_jtag_uart_scfifo_r', 'altera_avalon_jtag_uart_scfifo_w']:
    qsf += f'set_global_assignment -name SYSTEMVERILOG_FILE "{ip}{name}.sv"\n'
(out / 'igor_jtag.qsf').write_text(qsf)
(out / 'igor_jtag.qpf').write_text('QUARTUS_VERSION = "25.1"\nPROJECT_REVISION = "igor_jtag"\n')
def crc(data):
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ (0x8c if c & 1 else 0)
    return c
payload = b''.join(x.to_bytes(2, 'little', signed=True) for x in [205]*64+[0]*10)
frame = bytes([0x5a, 0xa5, 1, 148])+payload
frame += bytes([crc(frame[2:])])
(out / 'demo_frame.mem').write_text(''.join(f'{b:02x}\n' for b in frame.ljust(256,b'\0')))
reply = bytes.fromhex('5a a5 02 06 d2 ff 3c 00 22 00')
reply += bytes([crc(reply[2:])])
(out / 'demo_expected.mem').write_text(''.join(f'{b:02x}\n' for b in reply.ljust(16,b'\0')))
template = ('\r\nIGOR Parallel8 JTAG | r=demo !=badCRC | hex+Enter=frame\r\n'
            'RX count=0xN FPGA bytes: '+ ' '.join(['xx']*11) + '\r\n'
            'cycles=0xCCCCCCCC accepted=0xAAAAAAAA rejected=0xBBBBBBBB error=0xEE CHECK=PPPP\r\n> ')
dynamic = {}
dynamic[template.index('N FPGA')] = 'hexchar(count)'
start = template.index('xx')
for i in range(11):
    dynamic[start+i*3] = f"count>{i} ? hexchar(captured[{i}][7:4]) : 8'h2d"
    dynamic[start+i*3+1] = f"count>{i} ? hexchar(captured[{i}][3:0]) : 8'h2d"
for token, signal in [('CCCCCCCC','snap_cycles'),('AAAAAAAA','snap_accepted'),('BBBBBBBB','snap_rejected'),('EE','snap_error')]:
    start = template.index(token)
    for i in range(len(token)):
        high = (len(token)-i)*4-1
        dynamic[start+i] = f'hexchar({signal}[{high}:{high-3}])'
start=template.index('PPPP')
for i,(a,b,c) in enumerate(zip('PASS','FAIL','DATA')):
    dynamic[start+i] = f'!demo_mode ? 8\'h{ord(c):02x} : check_pass ? 8\'h{ord(a):02x} : 8\'h{ord(b):02x}'
lines=[f'localparam STATUS_LENGTH={len(template)};', 'function [7:0] status_char; input [7:0] p; begin case(p)']
for i,c in enumerate(template):
    expr=dynamic.get(i, f"8'h{ord(c):02x}")
    lines.append(f"8'd{i}:status_char={expr};")
lines+=['default:status_char=8\'h20;', 'endcase end endfunction']
(out/'status_chars.vh').write_text('\n'.join(lines)+'\n')
top=(base/'igor_src_policy_de10_nano.v').read_text().replace('module igor_src_policy_de10_nano(', 'module igor_jtag_top(')
top=top.replace(' input wire UART_RX,\n','')
top=top.replace(' wire [3:0] state;', '''
 wire console_serial_rx;
 wire [7:0] host_data,terminal_data;
 wire host_valid,host_ready,terminal_valid,terminal_ready;
 wire address,chipselect,read_n,write_n,waitrequest;
 wire [31:0] readdata,writedata;
 altera_avalon_jtag_uart jtag(
  .clk(FPGA_CLK1_50),.rst_n(rst_n),.av_address(address),.av_chipselect(chipselect),
  .av_read_n(read_n),.av_write_n(write_n),.av_writedata(writedata),
  .av_readdata(readdata),.av_waitrequest(waitrequest),.av_irq());
 igor_jtag_bytes bridge(FPGA_CLK1_50,rst_n,terminal_data,terminal_valid,terminal_ready,
  host_data,host_valid,host_ready,address,chipselect,read_n,write_n,writedata,readdata,waitrequest);
 igor_jtag_console console(FPGA_CLK1_50,rst_n,stop_active,
  host_data,host_valid,host_ready,terminal_data,terminal_valid,terminal_ready,
  console_serial_rx,UART_TX,cycles,accepted,rejected,error_code);
 wire [3:0] state;''')
top=top.replace('.uart_rx(UART_RX)', '.uart_rx(console_serial_rx)')
(out/'igor_jtag_top.v').write_text(top)
(out / 'source_manifest.json').write_text(json.dumps({
    'core_sha256': hashlib.sha256((out/'igor_src_policy_core.v').read_bytes()).hexdigest(),
    'demo_observations': [205]*64+[0]*10,
    'demo_request_hex': frame.hex(' '), 'expected_reply_hex': reply.hex(' '),
    'expected_actions_q88': [-46,60,34], 'expected_cycles': 6916,
}, indent=2)+'\n')
print(out)
