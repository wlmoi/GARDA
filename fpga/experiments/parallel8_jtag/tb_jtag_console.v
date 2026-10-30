`timescale 1ns/1ps
module tb_jtag_console;
 reg clk=0;always #10 clk=~clk;
 reg rst_n=0,estop=0;reg [7:0] host_data=0;reg host_valid=0;
 wire host_ready;wire [7:0] text;wire text_valid;
 wire serial_rx,serial_tx;
 wire [31:0] accepted,rejected,cycles;
 wire [7:0] error_code;wire [15:0] flags;wire [3:0] debug_state;
 wire permit,valid;wire signed [15:0] a0,a1,a2;
 igor_jtag_console #(.AUTO_DELAY(10),.REPLY_TIMEOUT(200000)) console(
 clk,rst_n,estop,host_data,host_valid,host_ready,text,text_valid,1'b1,
 serial_rx,serial_tx,cycles,accepted,rejected,error_code);
 igor_src_policy_uart #(.BAUD(921600)) policy(
 .clk(clk),.rst_n(rst_n),.uart_rx(serial_rx),.uart_tx(serial_tx),.estop(estop),
 .debug_state(debug_state),.error_code(error_code),.error_flags(flags),
 .accepted_frames(accepted),.rejected_frames(rejected),.last_latency_cycles(cycles),
 .safety_permit(permit),.response_valid(valid),.action0(a0),.action1(a1),.action2(a2));
 integer reports=0;
 always @(posedge clk)if(text_valid)begin
  $write("%c",text);
  if(console.index==console.STATUS_LENGTH-1)begin
   reports=reports+1;
   if(reports<=2 && !console.check_pass)$fatal(1,"Report comparison failed");
   if(reports==1 && (cycles!=6916 || accepted!=1 || rejected!=0 || a0!=-46 || a1!=60 || a2!=34))
    $fatal(1,"Parallel8 result mismatch");
   if(reports==2 && (error_code!=6 || rejected!=1 || permit || a0 || a1 || a2))
    $fatal(1,"Bad CRC not fail-closed");
   if(reports==3 && (console.demo_mode || accepted!=2 || cycles!=6916 || a0!=-46 || a1!=60 || a2!=34))
    $fatal(1,"Pasted hexadecimal frame failed");
   if(reports==4 && (!console.check_pass || accepted!=3))$fatal(1,"r+Enter failed");
   if(reports==5)begin
    if(console.check_pass || error_code!=1 || permit || a0 || a1 || a2)$fatal(1,"Estop failed");
    $display("\nPASS: real Parallel8 serial inference, CRC rejection, pasted hex frame, E-stop, console reports; blank CR/LF ignored, r+Enter works");$finish;
   end
  end
 end
 task command;input[7:0] c;begin
  wait(host_ready);@(negedge clk);host_data=c;host_valid=1;@(negedge clk);host_valid=0;
 end endtask
 integer j;
 initial begin
  repeat(5)@(negedge clk);rst_n=1;
  wait(reports==1);repeat(5)@(negedge clk);
  for(j=0;j<10;j=j+1)begin command(13);command(10);end
  repeat(200100)@(negedge clk);
  if(reports!=1 || console.state!=0 || accepted!=1)$fatal(1,"Empty CR/LF created a transaction");
  command("!");
  wait(reports==2);repeat(5)@(negedge clk);
  for(j=0;j<153;j=j+1)begin
   command(console.hexchar(console.frame[j][7:4]));
   command(console.hexchar(console.frame[j][3:0]));command(" ");
  end
  command(13);command(10);
  wait(reports==3);repeat(5)@(negedge clk);command("r");command(13);command(10);
  wait(reports==4);repeat(200100)@(negedge clk);
  if(reports!=4 || console.state!=0)$fatal(1,"r+Enter produced extra reports");
  estop=1;command("r");
 end
 initial begin #100000000;$fatal(1,"Test watchdog");end
endmodule
