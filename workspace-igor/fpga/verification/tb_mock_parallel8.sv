`timescale 1ns/1ps
module tb_mock_parallel8;
 localparam N=256;
 reg clk=0;always #10 clk=~clk;
 reg rst_n=0,load=0,start=0,abort=0;reg [6:0] input_index=0;
 reg signed[15:0] input_value=0;reg[1:0] output_index=0;
 wire signed[15:0] output_value;
 wire busy,done,fault,saturated;wire[3:0] error_code;wire[31:0] latency;
 igor_src_policy_core dut(clk,rst_n,load,input_index,input_value,start,abort,output_index,
 output_value,busy,done,fault,error_code,latency,saturated);
 reg[15:0] observations[0:N*74-1];reg signed[15:0] expected[0:N*3-1];
 integer vector_id,i,watchdog,logfile,checks=0;
 initial begin
  $readmemh("observations.hex",observations);$readmemh("expected.hex",expected);
  logfile=$fopen("rtl_results.csv","w");
  $fdisplay(logfile,"vector,output,expected_q88,actual_q88,latency_cycles");
  repeat(4)@(negedge clk);rst_n=1;
  for(vector_id=0;vector_id<N;vector_id=vector_id+1)begin
   for(i=0;i<74;i=i+1)begin
    @(negedge clk);load=1;input_index=i;input_value=observations[vector_id*74+i];
   end
   @(negedge clk);load=0;start=1;
   @(negedge clk);start=0;watchdog=0;
   while(!done && !fault && watchdog<20000)begin @(posedge clk);#1;watchdog=watchdog+1;end
   if(!done || fault)$fatal(1,"Vector %0d did not finish, fault=%0d",vector_id,error_code);
   if(latency!==32'd6916)$fatal(1,"Vector %0d latency mismatch: %0d",vector_id,latency);
   for(i=0;i<3;i=i+1)begin
    @(negedge clk);output_index=i;#1;
    if(output_value!==expected[vector_id*3+i])$fatal(1,"Vector %0d output %0d expected %0d got %0d",vector_id,i,expected[vector_id*3+i],output_value);
    $fdisplay(logfile,"%0d,%0d,%0d,%0d,%0d",vector_id,i,expected[vector_id*3+i],output_value,latency);
    checks=checks+1;
   end
   if(vector_id%32==31)$display("RTL vectors PASS: %0d/256",vector_id+1);
  end
  $fclose(logfile);$display("PASS: 256 synthetic vectors, 768 exact Q8.8 output checks, 6916 cycles each");$finish;
 end
 initial begin #500000000;$fatal(1,"Global RTL watchdog");end
endmodule
