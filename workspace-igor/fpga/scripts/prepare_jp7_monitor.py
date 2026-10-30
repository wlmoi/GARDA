"""Isolated physical JP7 monitor with JTAG status and transparent echo mode."""
from pathlib import Path
import shutil
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--header',choices=['JP7','JP1_3_4','JP1_1_2'],default='JP7')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
folder={'JP7':'jp7_monitor','JP1_3_4':'jp1_3_4_monitor','JP1_1_2':'jp1_1_2_monitor'}[args.header]
out=root/'experiments'/folder;out.mkdir(exist_ok=True)
if args.header=='JP1_1_2' and (out/'igor_jp7_monitor.v').exists() and 'result_seq' in (out/'igor_jp7_monitor.v').read_text():
 raise SystemExit('JP1_1_2 contains verified result-latch telemetry. Open and rebuild the existing project; refusing to overwrite it with the basic monitor template.')
base=root/'experiments/parallel8_jp7'
for n in ['igor_src_policy_core.v','igor_src_policy.sdc','pin_assignment.tcl']+[f'bank{i}.mem' for i in range(8)]:shutil.copyfile(base/n,out/n)
if args.header!='JP7':
 for n in ['igor_jp7_monitor.v','tb_jp7_monitor.v']:shutil.copyfile(root/'experiments/jp7_monitor'/n,out/n)
 rx,tx=('W12','D11') if args.header=='JP1_3_4' else ('V12','E8')
 pins=(out/'pin_assignment.tcl').read_text().replace('PIN_Y15 -to UART_RX',f'PIN_{rx} -to UART_RX').replace('PIN_AC24 -to UART_TX',f'PIN_{tx} -to UART_TX')
 pins=pins.replace('JP7 pin 1 RX/Y15, pin 2 TX/AC24',f'{args.header} RX/{rx}, TX/{tx}')
 (out/'pin_assignment.tcl').write_text(pins)
bridge=(root/'experiments/parallel8_jtag/igor_jtag_console.v').read_text().split('module igor_jtag_console')[0]
(out/'igor_jtag_bytes.v').write_text(bridge+'\n`default_nettype wire\n')
top=(base/'igor_src_policy_de10_nano.v').read_text().replace('module igor_src_policy_de10_nano(', 'module igor_jp7_monitor_top(')
top=top.replace(' wire [3:0] state;', '''
 wire policy_tx,echo_mode;
 wire [7:0] host_data,text_data;
 wire host_valid,host_ready,text_valid,text_ready;
 wire address,chipselect,read_n,write_n,waitrequest;
 wire [31:0] readdata,writedata;
 altera_avalon_jtag_uart jtag(.clk(FPGA_CLK1_50),.rst_n(rst_n),
  .av_address(address),.av_chipselect(chipselect),.av_read_n(read_n),.av_write_n(write_n),
  .av_writedata(writedata),.av_readdata(readdata),.av_waitrequest(waitrequest),.av_irq());
 igor_jtag_bytes bridge(FPGA_CLK1_50,rst_n,text_data,text_valid,text_ready,
  host_data,host_valid,host_ready,address,chipselect,read_n,write_n,writedata,readdata,waitrequest);
 igor_jp7_monitor monitor(FPGA_CLK1_50,rst_n,stop_active,UART_RX,host_data,host_valid,host_ready,
  text_data,text_valid,text_ready,echo_mode,accepted,rejected,cycles,error_code,state);
 // Diagnostic echo is physical pad RX->TX; it is not a neural inference result.
 assign UART_TX=echo_mode ? UART_RX : policy_tx;
 wire [3:0] state;''').replace('.uart_tx(UART_TX)', '.uart_tx(policy_tx)')
(out/'igor_jp7_monitor_top.v').write_text(top)
qsf=(base/'igor_parallel8_jp7.qsf').read_text().replace('igor_src_policy_de10_nano','igor_jp7_monitor_top')
for n in ['igor_jtag_bytes.v','igor_jp7_monitor.v']:qsf+=f'\nset_global_assignment -name VERILOG_FILE {n}\n'
for n in ['altera_avalon_jtag_uart','altera_avalon_jtag_uart_scfifo_r','altera_avalon_jtag_uart_scfifo_w']:
 qsf+=f'set_global_assignment -name SYSTEMVERILOG_FILE "D:/Quartus-Program/ip/altera/sopc_builder_ip/altera_avalon_jtag_uart/{n}.sv"\n'
(out/'igor_jp7_monitor.qsf').write_text(qsf)
(out/'igor_jp7_monitor.qpf').write_text('QUARTUS_VERSION = "25.1"\nPROJECT_REVISION = "igor_jp7_monitor"\n')
label={'JP7':'JP7','JP1_3_4':'JP1 pins 3/4','JP1_1_2':'JP1 pins 1/2'}[args.header]
template='\r\n'+label+' q=status e=echo i=infer\r\nmode=M stop=S pin=P edges=XXXXXXXX rxbytes=YYYYYYYY last=LL framing=FFFFFFFF accepted=AAAAAAAA rejected=BBBBBBBB error=EE state=T cycles=CCCCCCCC\r\n> '
dynamic={template.index('mode=M')+5:"echo_mode ? 8'h45 : 8'h49",template.index('stop=S')+5:"snap_stop ? 8'h31 : 8'h30",template.index('pin=P')+4:"snap_pin ? 8'h31 : 8'h30",template.index('state=T')+6:'hexchar(snap_state)'}
for token,signal in [('XXXXXXXX','snap_edges'),('YYYYYYYY','snap_rxbytes'),('LL','snap_last'),('FFFFFFFF','snap_framing'),('AAAAAAAA','snap_accepted'),('BBBBBBBB','snap_rejected'),('EE','snap_error'),('CCCCCCCC','snap_cycles')]:
 start=template.index(token)
 for i in range(len(token)):
  hi=(len(token)-i)*4-1;dynamic[start+i]=f'hexchar({signal}[{hi}:{hi-3}])'
lines=[f'localparam LENGTH={len(template)};', 'function [7:0] char_at;input [7:0] pos;begin case(pos)']
for i,c in enumerate(template):
 expr=dynamic.get(i,"8'h%02x"%ord(c));lines.append(f"8'd{i}:char_at={expr};")
lines+=['default:char_at=32;endcase end endfunction']
(out/'monitor_chars.vh').write_text('\n'.join(lines)+'\n')
print(out)
