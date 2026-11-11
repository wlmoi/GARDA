// Lockstep equivalence: original garda_uart_top vs DE10-Lite garda_lite_uart_top.
// Both receive the identical RX waveform and identical KEY/SW inputs. Traffic uses
// only legacy opcodes (and invalid opcodes outside 0x20..0x29). The UART TX line,
// LEDs, motor command and fault code must agree on EVERY clock edge.
`timescale 1ns/1ps
`default_nettype none
module tb_lockstep;
reg clk=0;always #10 clk=~clk;
reg [1:0] key=0;reg [3:0] sw=0;reg rx=1;
wire tx_a,tx_b;wire [7:0] led_a,led_b;
garda_uart_top #(.CLKS_PER_BIT(8),.RX_TIMEOUT_CYCLES(256)) a(.FPGA_CLK1_50(clk),.KEY(key),.SW(sw),.UART_RX(rx),.UART_TX(tx_a),.LED(led_a));
garda_lite_uart_top #(.CLKS_PER_BIT(8),.RX_TIMEOUT_CYCLES(256)) b(.FPGA_CLK1_50(clk),.KEY(key),.SW(sw),.UART_RX(rx),.UART_TX(tx_b),.LED(led_b),
 .obs_fault(),.obs_last_fault(),.obs_host_estop(),.obs_watchdog_trip(),.obs_frame(),.obs_accepted_count(),.obs_status(),.port_stats(48'd0),.port_owner(1'b0),.board_io(23'd0),.oob_estop(1'b0));
defparam a.inspection_rom.FILE="assets/neural_24_64_64_4/bram_unified_weights_padded.mem";
defparam a.neural.weights.FILE="assets/neural_24_64_64_4/bram_unified_weights_padded.mem";
defparam b.inspection_rom.FILE="assets/neural_24_64_64_4/bram_unified_weights_padded.mem";
defparam b.neural.weights.FILE="assets/neural_24_64_64_4/bram_unified_weights_padded.mem";
integer cycles=0,mismatches=0,frames=0,enables=0,i,n,seed;
reg [15:0] nn_in[0:2399];
always @(posedge clk)begin
 cycles<=cycles+1;
 if(a.enable)enables<=enables+1;
 if(tx_a!==tx_b || led_a!==led_b || a.enable!==b.enable || a.vc!==b.vc || a.wc!==b.wc || a.fault!==b.fault ||
    a.serial.response_sample!==b.serial.response_sample || a.invalid_command!==b.invalid_command)begin
  mismatches=mismatches+1;
  if(mismatches<5)$display("MISMATCH t=%0t tx %b/%b led %h/%h fault %0d/%0d",$time,tx_a,tx_b,led_a,led_b,a.fault,b.fault);
 end
end
function [7:0] crc8;input [7:0] p,v;integer j;reg [7:0] x;begin x=p^v;for(j=0;j<8;j=j+1)x=x[7]?(x<<1)^8'h07:x<<1;crc8=x;end endfunction
task tick;begin @(posedge clk);#1;end endtask
task reset_all;begin @(negedge clk);key=0;rx=1;sw=0;repeat(5)tick;@(negedge clk);key=3;repeat(10)tick;end endtask
task byte_tx;input [7:0] v;integer k;begin
 @(negedge clk);rx=0;repeat(8)@(negedge clk);
 for(k=0;k<8;k=k+1)begin rx=v[k];repeat(8)@(negedge clk);end
 rx=1;repeat(12)@(negedge clk);
end endtask
task frame;input [7:0] op;input [31:0] v;input bad;reg [7:0] c;begin
 c=crc8(0,8'ha5);c=crc8(c,op);c=crc8(c,v[7:0]);c=crc8(c,v[15:8]);c=crc8(c,v[23:16]);c=crc8(c,v[31:24]);
 byte_tx(8'ha5);byte_tx(op);byte_tx(v[7:0]);byte_tx(v[15:8]);byte_tx(v[23:16]);byte_tx(v[31:24]);byte_tx(bad?c^8'h5c:c);byte_tx(8'h5a);
 repeat(760)tick;frames=frames+1;
end endtask
// Random legacy frame: valid-looking and malformed payloads for opcodes 0..19 and 0x80..0xff.
task random_frame;reg [7:0] op;reg [31:0] v;integer r;begin
 r=$random(seed);op=r[4:0];if(op>19)op=8'h80|r[12:8];
 v=$random(seed);
 case(r[15:13])
  0,1:v=0; 2:v=v&32'h00ff_7fff; 3:v=32'h00143d0f; 4:v=v&32'h0000_1fff; 5:v=v&32'h00ff_ff1f; default:;
 endcase
 frame(op,v,(r[23:16]==0));
end endtask
initial begin
 seed=20261111;$readmemh("assets/neural_24_64_64_4/test_inputs.mem",nn_in);
 // Phase 1: random legacy traffic with periodic resets and switch/E-stop changes.
 for(n=0;n<12;n=n+1)begin
  reset_all;sw={$random(seed)}%2 ? 4'b0000 : {$random(seed)}%16;
  for(i=0;i<25;i=i+1)begin random_frame;if(i==12)begin key[1]=0;repeat(50)tick;key[1]=1;end end
 end
 // Phase 2: full planner run (config, lock, 16384-cell map, commit, run, reads), then E-stop.
 reset_all;frame(4,32'h00143d0f,0);frame(5,0,0);frame(1,1,0);
 for(i=0;i<16384;i=i+1)frame(2,i|((((i>>7)>=70 && (i>>7)<74 && (i&127)>=60 && (i&127)<68) ? 254 : (i%3))<<16),0);
 frame(3,0,0);frame(6,0,0);repeat(15000)tick;frame(7,0,0);frame(14,0,0);frame(9,0,0);
 key[1]=0;repeat(30)tick;frame(7,0,0);frame(15,0,0);frame(16,0,0);key[1]=1;
 // Phase 3: neural inference vector 0 through the UART.
 reset_all;for(i=0;i<24;i=i+1)frame(10,i|(nn_in[i]<<8),0);frame(11,0,0);
 repeat(19000)tick;for(i=0;i<4;i=i+1)frame(12,i,0);frame(13,0,0);
 $display("LOCKSTEP cycles=%0d frames=%0d enable_cycles=%0d mismatches=%0d",cycles,frames,enables,mismatches);
 if(mismatches!=0)$fatal(1,"FAIL lockstep");
 if(enables==0)$fatal(1,"FAIL lockstep: planner never granted motor_enable, coverage too weak");
 $display("PASS lockstep: DE10-Lite top is cycle-identical to garda_uart_top on legacy traffic");
 $finish;
end
endmodule
`default_nettype wire
