// Board-level system test of garda_de10_lite_top (the exact Quartus top).
// A behavioural host drives real UART waveforms; a receiver model decodes and
// CRC-checks every response frame. Every transaction is written to TRACE_FILE
// as JSON lines; the Control Center replays this file as "SOFTWARE SIMULATION".
//
// Macros: CLKS (FPGA divisor), HOST_BIT_NS (host bit period, may differ from
// CLKS*20 to model real baud error), SHORT (baud smoke test only).
`timescale 1ns/1ps
`default_nettype none
`ifndef CLKS
`define CLKS 8
`endif
`ifndef HOST_BIT_NS
`define HOST_BIT_NS (`CLKS*2.0*`HALF_NS)
`endif
`ifndef TRACE_FILE
`define TRACE_FILE "sim/build/board_trace.jsonl"
`endif
module tb_board;
`ifndef HALF_NS
`define HALF_NS 10
`endif
reg clk=0;always #(`HALF_NS) clk=~clk;   // HALF_NS=11.111 models the 45 MHz core clock
reg [1:0] key=2'b00;reg [9:0] sw=0;reg rx=1,rxb=1;   // rx = laptop (port A), rxb = Jetson (port B)
wire tx;wire [9:0] ledr;wire [7:0] hex0,hex1,hex2,hex3,hex4,hex5;
garda_de10_lite_top #(.CLKS_PER_BIT(`CLKS),.BUILD_ID(32'h5EED0001),.RX_TIMEOUT_CYCLES(`CLKS*200)) dut(
 .MAX10_CLK1_50(clk),.KEY(key),.SW(sw),.LEDR(ledr),.HEX0(hex0),.HEX1(hex1),.HEX2(hex2),.HEX3(hex3),.HEX4(hex4),.HEX5(hex5),
 .JP1_RX({rxb,rx}),.JP1_TX(txv));   // port A = JP1 pins 1/2, port B = JP1 pins 3/4
wire [1:0] txv;wire txb=txv[1];assign tx=txv[0];
defparam dut.garda.inspection_rom.FILE="assets/neural_24_64_64_4/bram_unified_weights_padded.mem";
defparam dut.garda.neural.weights.FILE="assets/neural_24_64_64_4/bram_unified_weights_padded.mem";

real BIT;initial BIT=`HOST_BIT_NS;
integer fd,failures=0,checks=0,i,v;
reg [15:0] nn_in[0:2399],nn_out[0:399];

// ---------------- host receiver model ----------------
reg [7:0] rx_bytes[0:4095];integer rx_count=0;reg [7:0] b;integer k;
initial begin
 forever begin
  @(negedge tx);#(BIT*1.5);
  for(k=0;k<8;k=k+1)begin b[k]=tx;#(BIT);end
  rx_bytes[rx_count%4096]=b;rx_count=rx_count+1;
 end
end
function [7:0] crc8;input [7:0] p,val;integer j;reg [7:0] x;begin x=p^val;for(j=0;j<8;j=j+1)x=x[7]?(x<<1)^8'h07:x<<1;crc8=x;end endfunction
task send_byte;input [7:0] val;integer m;begin
 rx=0;#(BIT);for(m=0;m<8;m=m+1)begin rx=val[m];#(BIT);end rx=1;#(BIT);#(BIT*0.5);
end endtask

// ---------------- second host (Jetson Nano) on port B ----------------
reg [7:0] rxb_bytes[0:255];integer rxb_count=0;reg [7:0] bb;integer kb;
initial begin
 forever begin
  @(negedge txb);#(BIT*1.5);
  for(kb=0;kb<8;kb=kb+1)begin bb[kb]=txb;#(BIT);end
  rxb_bytes[rxb_count%256]=bb;rxb_count=rxb_count+1;
 end
end
task send_byte_b;input [7:0] val;integer m;begin
 rxb=0;#(BIT);for(m=0;m<8;m=m+1)begin rxb=val[m];#(BIT);end rxb=1;#(BIT);#(BIT*0.5);
end endtask
reg resp_b_ok;reg [31:0] resp_b;
task xfer_b;input [8*48-1:0] name;input [7:0] op;input [31:0] val;
 integer start,waited,kk;reg [7:0] c,rc;begin
 if(last_port!=1)#(BIT*40);last_port=1;start=rxb_count;
 c=crc8(0,8'ha5);c=crc8(c,op);c=crc8(c,val[7:0]);c=crc8(c,val[15:8]);c=crc8(c,val[23:16]);c=crc8(c,val[31:24]);
 send_byte_b(8'ha5);send_byte_b(op);send_byte_b(val[7:0]);send_byte_b(val[15:8]);send_byte_b(val[23:16]);send_byte_b(val[31:24]);
 send_byte_b(c);send_byte_b(8'h5a);
 waited=0;while(rxb_count<start+8 && waited<300)begin #(BIT);waited=waited+1;end
 resp_b_ok=0;resp_b=0;
 if(rxb_count>=start+8)begin
  rc=crc8(0,rxb_bytes[start%256]);for(kk=1;kk<6;kk=kk+1)rc=crc8(rc,rxb_bytes[(start+kk)%256]);
  resp_b={rxb_bytes[(start+5)%256],rxb_bytes[(start+4)%256],rxb_bytes[(start+3)%256],rxb_bytes[(start+2)%256]};
  resp_b_ok=rxb_bytes[start%256]==8'h5a && rxb_bytes[(start+1)%256]==op && rxb_bytes[(start+7)%256]==8'ha5 && rc==rxb_bytes[(start+6)%256];
 end
 #(BIT*2);
 $fdisplay(fd,"{\"t_ns\":%0d,\"step\":\"%0s\",\"port\":\"B\",\"op\":%0d,\"payload\":%0d,\"corrupt\":0,\"result\":\"%0s\",\"response\":%0d,\"motor_enable\":%0d,\"fault\":%0d,\"host_estop\":%0d,\"watchdog_trip\":%0d,\"ledr\":%0d}",
  $time,name,op,val,resp_b_ok ? "ok" : "timeout",resp_b,dut.garda.enable,dut.garda.fault,dut.garda.host_estop,dut.garda.watchdog_trip,ledr);
end endtask
integer a_before;reg last_port=0;   // real hosts leave a gap when the other host takes over

// xfer: send one frame and wait for the 8-byte response (or time out).
reg resp_ok;reg [31:0] resp;reg [8*48-1:0] label;
task xfer;input [8*48-1:0] name;input [7:0] op;input [31:0] val;input integer corrupt;
 integer start,waited;reg [7:0] c,rc;reg [8*16-1:0] st;begin
 label=name;if(last_port!=0)#(BIT*40);last_port=0;start=rx_count;
 c=crc8(0,8'ha5);c=crc8(c,op);c=crc8(c,val[7:0]);c=crc8(c,val[15:8]);c=crc8(c,val[23:16]);c=crc8(c,val[31:24]);
 send_byte(8'ha5);send_byte(op);send_byte(val[7:0]);send_byte(val[15:8]);send_byte(val[23:16]);send_byte(val[31:24]);
 send_byte(corrupt ? c^8'h5c : c);send_byte(8'h5a);
 waited=0;while(rx_count<start+8 && waited<300)begin #(BIT);waited=waited+1;end
 resp_ok=0;resp=0;st="timeout";
 if(rx_count>=start+8)begin
  rc=crc8(0,rx_bytes[start%4096]);for(k=1;k<6;k=k+1)rc=crc8(rc,rx_bytes[(start+k)%4096]);
  resp={rx_bytes[(start+5)%4096],rx_bytes[(start+4)%4096],rx_bytes[(start+3)%4096],rx_bytes[(start+2)%4096]};
  if(rx_bytes[start%4096]==8'h5a && rx_bytes[(start+1)%4096]==op && rx_bytes[(start+7)%4096]==8'ha5 && rc==rx_bytes[(start+6)%4096])
   begin resp_ok=1;st="ok";end else st="bad_frame";
 end
 #(BIT*2);
 $fdisplay(fd,"{\"t_ns\":%0d,\"step\":\"%0s\",\"op\":%0d,\"payload\":%0d,\"corrupt\":%0d,\"result\":\"%0s\",\"response\":%0d,\"motor_enable\":%0d,\"fault\":%0d,\"host_estop\":%0d,\"watchdog_trip\":%0d,\"ledr\":%0d}",
  $time,name,op,val,corrupt,st,resp,dut.garda.enable,dut.garda.fault,dut.garda.host_estop,dut.garda.watchdog_trip,ledr);
end endtask
task check;input cond;input [8*64-1:0] what;begin
 checks=checks+1;
 if(!cond)begin failures=failures+1;$display("FAIL  %0s (step %0s resp=%h ok=%0d)",what,label,resp,resp_ok);end
 else $display("ok    %0s",what);
end endtask
task wait_cycles;input integer n;begin repeat(n)@(posedge clk);end endtask
task power_on;begin key=2'b00;rx=1;rxb=1;wait_cycles(10);key=2'b11;wait_cycles(20);end endtask

initial begin
 fd=$fopen(`TRACE_FILE,"w");
 $readmemh("assets/neural_24_64_64_4/test_inputs.mem",nn_in);
 $readmemh("assets/neural_24_64_64_4/test_outputs.mem",nn_out);
 power_on;
 // 1. Identification ------------------------------------------------------
 xfer("identify",8'h20,0,0);check(resp_ok && resp==32'h47444C02,"IDENT returns GDL interface v2");
 xfer("link_info",8'h29,0,0);check(resp_ok && resp[31:16]==`CLKS && resp[15:0]==16'd45000,"LINK_INFO reports divisor and 45 MHz core clock");
 xfer("build_id",8'h28,0,0);check(resp_ok && resp==32'h5EED0001,"BUILD_ID matches build parameter");
 xfer("status",8'h07,0,0);check(resp_ok && resp[0]==0 && resp[15:8]!=0,"power-on: motor disabled with a non-zero fault code");
`ifndef SHORT
 // 2. Neural inference through UART, compared with the golden vectors -----
 for(v=0;v<3;v=v+1)begin
  for(i=0;i<24;i=i+1)xfer("nn_load_input",8'd10,i|(nn_in[v*24+i]<<8),0);
  xfer("nn_start",8'd11,0,0);
  wait_cycles(19000);
  xfer("nn_poll",8'd12,0,0);check(resp_ok && resp[16] && !resp[18],"neural done without fault");
  for(i=0;i<4;i=i+1)begin
   xfer("nn_read_output",8'd12,i,0);check(resp_ok && resp[15:0]==nn_out[v*4+i],"neural output matches golden vector");
  end
 end
 xfer("nn_cycles",8'd13,0,0);check(resp_ok && resp==32'd18192,"neural latency is 18192 cycles");
 // 2b. Neural command gate (Vx, Vy, omega demo mapping = outputs 0..2) -------
 for(i=0;i<3;i=i+1)begin
  xfer("nn_cmd_gated",8'h2D,i,0);
  check(resp_ok && resp[28] && $signed(resp[15:0])==($signed(nn_out[2*4+i])>253 ? 253 : ($signed(nn_out[2*4+i])< -256 ? -256 : $signed(nn_out[2*4+i]))),
        "NN_CMD: permitted output equals clamped golden value");
 end
 sw[3]=1;wait_cycles(10);
 xfer("nn_cmd_sw3",8'h2D,0,0);check(resp_ok && !resp[28] && resp[15:0]==0,"NN_CMD: SW3 protective stop forces Vx to 0 in hardware");
 sw[3]=0;wait_cycles(10);
 key[1]=0;wait_cycles(10);key[1]=1;wait_cycles(10);
 xfer("nn_cmd_after_key1",8'h2D,1,0);check(resp_ok && !resp[28] && resp[15:0]==0,"NN_CMD: KEY1 E-stop latches the neural gate closed after release");
 xfer("safe_reset",8'h22,32'h52534554,0);wait_cycles(`CLKS*200);
 xfer("nn_cmd_after_reset",8'h2D,0,0);check(resp_ok && !resp[28] && resp[15:0]==0,"NN_CMD: after reset no command until a new inference completes");
 // 3. Planner run + controlled safety-gate (E-stop) test ------------------
 xfer("config_write",8'd4,32'h00143d0f,0);xfer("config_lock",8'd5,0,0);
 xfer("map_begin",8'd1,1,0);
 for(i=0;i<16384;i=i+1)begin
  xfer("map_write",8'd2,i|(((i>>7)>=70 && (i>>7)<74 && (i&127)>=60 && (i&127)<68 ? 8'd254 : 8'd0)<<16),0);
  if(!resp_ok || resp[4:3]!=0)begin check(0,"map write accepted");i=16384;end
 end
 xfer("estop_test_arm",8'h25,32'd20000,0);check(resp_ok,"E-stop test armed (20000 cycles after result)");
 xfer("map_commit",8'd3,0,0);
 xfer("run",8'd6,0,0);
 wait_cycles(15000); // 4 tiles x 128 candidates x 20 poses ~ 10.6k cycles
 xfer("status_after_run",8'd7,0,0);check(resp_ok && resp[2] && resp[0] && resp[15:8]==0,"planner done, safety gate PERMITS motion (enable=1, fault 0)");
 xfer("read_command",8'd14,0,0);check(resp_ok && resp[4:0]!=0,"non-zero velocity command issued");
 wait_cycles(25000);
 xfer("status_after_estop",8'd7,0,0);check(resp_ok && !resp[0] && resp[15:8]==8'd2,"E-stop: enable=0, fault 2");
 xfer("estop_capture",8'h26,0,0);
 check(resp_ok && resp[0] && resp[2] && resp[3] && resp[31:24]==0,"capture: enabled before stop, host source, 0-cycle disable");
 check(hex5[6:0]==7'b1000010 && hex4[6:0]==7'b0001000 && hex3[6:0]==7'b0101111 && hex2[6:0]==7'b0100001 && hex1[6:0]==7'b0001000,
       "HEX5..HEX1 show GArdA by default (G = 6 without middle bar)");
 sw[0]=1;wait_cycles(10);
 check(hex4[6:0]==7'b0100100 && hex5[6:0]==7'b1000000 && hex4[7]==0,"SW0 UP: HEX5:HEX4 show fault 02 with host-E-stop DP");
 sw[0]=0;wait_cycles(10);
 check(ledr[8]==1 && ledr[0]==0,"LEDR8 lit, LEDR0 (motor enable) off");
 // 4. Protocol fault lockout, then UART safe reset recovers ---------------
 xfer("corrupt_crc_frame",8'd7,0,1);check(!resp_ok,"corrupted CRC gets no success response");
 xfer("status_while_faulted",8'd7,0,0);check(!resp_ok,"legacy lockout: no response while protocol_fault latched");
 xfer("safe_reset",8'h22,32'h52534554,0);
 wait_cycles(`CLKS*200);
 xfer("status_after_safe_reset",8'd7,0,0);check(resp_ok && resp[4:3]==0 && !resp[0],"safe reset cleared protocol fault; motor still disabled");
 xfer("ext_status_after_reset",8'h24,0,0);check(resp_ok && resp[0]==0 && resp[3]==0,"host E-stop and watchdog cleared by reset");
 // 5. Safe reset is refused while the physical E-stop is pressed ----------
 xfer("host_estop",8'h21,0,0);
 key[1]=0;wait_cycles(10);
 xfer("estop_capture_key",8'h26,0,0);check(resp_ok && resp[0],"capture valid after physical stop");
 xfer("safe_reset_while_key1",8'h22,32'h52534554,0);wait_cycles(`CLKS*200);
 xfer("ext_status_key1",8'h24,0,0);check(resp_ok && resp[0]==1 && resp[1]==1,"reset refused while KEY1 held (host E-stop still latched)");
 key[1]=1;wait_cycles(10);
 xfer("safe_reset",8'h22,32'h52534554,0);wait_cycles(`CLKS*200);
 xfer("ext_status",8'h24,0,0);check(resp_ok && resp[0]==0,"reset accepted after KEY1 released");
 // 6. Host-link watchdog --------------------------------------------------
 xfer("watchdog_arm_2ms",8'h23,32'd2,0);check(resp_ok,"watchdog armed (2 ms)");
 wait_cycles(150000);
 xfer("status_after_silence",8'd7,0,0);check(resp_ok && resp[15:8]==8'd3,"silent host: watchdog forces protective stop (fault 3)");
 xfer("ext_status_wd",8'h24,0,0);check(resp_ok && resp[3]==1,"watchdog trip flag set");
 // 7. Extension commands keep the strict payload contract -----------------
 xfer("safe_reset",8'h22,32'h52534554,0);wait_cycles(`CLKS*200);
 xfer("ident_bad_payload",8'h20,1,0);
 xfer("status_after_bad_payload",8'd7,0,0);check(resp_ok && resp[4]==1 && !resp[0],"IDENT with non-zero payload => sticky invalid_command");
 xfer("safe_reset_wrong_magic",8'h22,32'h12345678,0);wait_cycles(`CLKS*200);
 xfer("status_still_invalid",8'd7,0,0);check(resp_ok && resp[4]==1,"wrong reset magic does not reset");
 xfer("counters",8'h27,0,0);check(resp_ok && resp[31:16]>=resp[15:0],"frame/accepted counters readable");
 // 8. Two hosts: laptop on port A, Jetson Nano on port B ---------------
 xfer("safe_reset",8'h22,32'h52534554,0);wait_cycles(`CLKS*200);
 a_before=rx_count;
 xfer_b("jetson_identify",8'h20,0);check(resp_b_ok && resp_b==32'h47444C02,"port B (Jetson) IDENT answered on port B");
 check(rx_count==a_before,"port A received nothing while port B owned the link");
 xfer_b("jetson_port_info",8'h2B,0);check(resp_b_ok && resp_b[0]==1,"PORT_INFO on port B reports requesting port B");
 xfer("laptop_port_info",8'h2B,0,0);check(resp_ok && resp[0]==0,"PORT_INFO on port A reports requesting port A");
 fork   // collision: the Jetson starts a frame while the laptop's frame is on the wire
  xfer("laptop_status_during_collision",8'd7,0,0);
  begin #(BIT*25);xfer_b("jetson_frame_collides",8'h20,0);end
 join
 check(resp_ok && resp[4:3]==0,"port A transaction intact during collision (no protocol fault)");
 check(!resp_b_ok,"colliding port B frame dropped (that host retries)");
 xfer_b("jetson_retry",8'h20,0);check(resp_b_ok && resp_b==32'h47444C02,"port B retry after collision succeeds");
 xfer("laptop_port_info",8'h2B,0,0);check(resp_ok && resp[31:16]>=1,"collision counted in PORT_INFO");
 xfer("port_stats",8'h2A,0,0);check(resp_ok && resp[15:0]>=1 && resp[31:16]>=3,"per-port grant counters in PORT_STATS");
 fork   // safety: the Jetson's E-stop collides with a laptop frame and is NOT forwarded by the arbiter...
  xfer("laptop_status_while_jetson_estops",8'd7,0,0);
  begin #(BIT*25);xfer_b("jetson_estop_collides",8'h21,0);end
 join
 check(!resp_b_ok,"colliding Jetson E-stop frame got no reply (arbiter dropped it)");
 xfer("status_after_oob_estop",8'd7,0,0);check(resp_ok && !resp[0] && resp[15:8]==8'd2,"...but the out-of-band detector latched the E-stop anyway (fault 2)");
 xfer("safe_reset",8'h22,32'h52534554,0);wait_cycles(`CLKS*200);
 xfer_b("jetson_estop",8'h21,0);check(resp_b_ok,"Jetson host E-stop acknowledged on port B");
 xfer("status_after_jetson_estop",8'd7,0,0);check(resp_ok && !resp[0] && resp[15:8]==8'd2,"E-stop from port B stops the motors (seen from port A)");
 xfer("safe_reset",8'h22,32'h52534554,0);wait_cycles(`CLKS*200);   // clear the E-stop latched above
 // 9. Switches and indicators -----------------------------------------
 sw=10'b1000010000;wait_cycles(20);       // SW9 and SW4 up (no safety function)
 xfer("board_io",8'h2C,0,0);check(resp_ok && resp[9:0]==10'b1000010000 && resp[11:10]==2'b11 && resp[22],"BOARD_IO reports SW9..0, KEY1..0 and PLL lock");
 sw=10'b1000010010;wait_cycles(20);       // + SW1: LED test
 check(ledr==10'b1000010010,"SW1 UP: LEDR mirrors every switch");
 sw=10'b0000000001;wait_cycles(20);       // SW0: HEX status page
 check(hex5[6:0]!=7'b1000010,"SW0 UP: HEX leaves the GARDA banner for the status page");
 sw=10'b0000001000;wait_cycles(20);       // SW3: protective stop
 xfer("status_sw3",8'd7,0,0);check(resp_ok && resp[15:8]==8'd3 && !resp[0],"SW3 UP: protective stop, fault 03");
 sw=0;wait_cycles(20);
`endif
 $fclose(fd);
 $display("BOARD checks=%0d failures=%0d",checks,failures);
 if(failures!=0)$fatal(1,"FAIL board");
 $display("PASS board: DE10-Lite top system test");
 $finish;
end
endmodule
`default_nettype wire
