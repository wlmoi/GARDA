`timescale 1ns/1ps
module tb_jp7_monitor;
 reg clk=0;always #10 clk=~clk;
 reg response_valid=0;
 reg rst_n=0,pin_rx=1;reg[7:0] host_data=0;reg host_valid=0;
 wire ready,valid,echo_mode;wire[7:0] text;
 igor_jp7_monitor dut(clk,rst_n,1'b0,pin_rx,host_data,host_valid,ready,text,valid,1'b1,
 echo_mode,32'd1,32'd2,32'd6916,8'd6,4'd0,response_valid,16'hffd2,16'd60,16'd34);
 task send_byte;input[7:0] value;input stopbit;integer k;begin
  @(negedge clk);pin_rx=0;repeat(54)@(negedge clk);
  for(k=0;k<8;k=k+1)begin pin_rx=value[k];repeat(54)@(negedge clk);end
  pin_rx=stopbit;repeat(54)@(negedge clk);pin_rx=1;repeat(100)@(negedge clk);
 end endtask
 task command;input[7:0] value;begin
  wait(ready);@(negedge clk);host_valid=1;host_data=value;@(negedge clk);host_valid=0;
  wait(valid);wait(!valid);
 end endtask
 always @(posedge clk)if(valid)$write("%c",text);
 initial begin
  repeat(5)@(negedge clk);rst_n=1;
  send_byte(8'ha5,1);send_byte(8'h33,0);
  command("q");if(dut.snap_rxbytes!=1 || dut.snap_last!=8'ha5 || dut.snap_framing!=1 || dut.snap_edges==0)$fatal(1,"Physical counters failed");
  @(negedge clk);response_valid=1;@(negedge clk);response_valid=0;
  command("q");if(dut.snap_seq!=1 || dut.snap_a0!=16'hffd2 || dut.snap_a1!=60 || dut.snap_a2!=34)$fatal(1,"Result latch failed");
  command("q");if(dut.snap_seq!=1)$fatal(1,"Stale result counted twice");
  command("e");if(!echo_mode)$fatal(1,"Echo mode failed");
  command("i");if(echo_mode)$fatal(1,"Inference mode failed");
  $display("PASS: physical UART decoding/counters, framing error, status snapshot, echo/inference selection");$finish;
 end
 initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
