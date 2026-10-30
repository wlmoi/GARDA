`timescale 1ns/1ps
module tb;
parameter VECTORS=100;
parameter NETLIST_SMOKE=0;
reg clk=0;always #10 clk=~clk;
reg rst_n=0,ena=1;
reg [7:0] ui=0,di=0;
wire [7:0] qo,uio_out,uio_oe;
tt_um_wlmoi_garda_neural_sram dut(ui,qo,di,uio_out,uio_oe,ena,clk,rst_n);
reg [15:0] image[0:6019],inputs[0:2399],gold[0:399];
integer i,n,j,cycles;
reg [15:0] actual;
reg [31:0] measured_cycles;
task cycle;begin @(posedge clk);#1;@(negedge clk);#1;end endtask
task wr(input [3:0] r,input [7:0] v);begin ui={3'd0,r,1'b1};di=v;cycle;ui=0;end endtask
task reset;begin ui=0;rst_n=0;cycle;cycle;rst_n=1;cycle;end endtask
task upload;begin
 if(VECTORS<100)begin $display("upload start at %0t",$time);$fflush();end
 wr(4,1);
 for(i=0;i<6020;i=i+1)begin wr(2,image[i][7:0]);wr(3,image[i][15:8]);wr(4,2);end
 if(dut.loaded_words!==6020 || dut.weights_ready!==0)$fatal(1,"upload count/commit");
 if(VECTORS<100)begin $display("upload complete at %0t",$time);$fflush();end
end endtask
initial begin
 $readmemh("assets/neural_24_64_64_4/bram_unified_weights.mem",image);
 $readmemh("assets/neural_24_64_64_4/test_inputs.mem",inputs);
 $readmemh("verification/build/neural_sram/independent_expected.hex",gold);
 reset;
 if(uio_oe!==0 || uio_out!==0)$fatal(1,"pin direction");
 wr(7,0);if(!dut.host_fault || dut.busy)$fatal(1,"unloaded start");
 reset;wr(4,1);wr(4,3);if(!dut.host_fault || dut.weights_ready)$fatal(1,"early commit");
 reset;wr(4,1);wr(2,0);wr(4,2);
 if(!dut.host_fault || dut.loaded_words!==0)$fatal(1,"missing staged byte");
 reset;wr(4,1);wr(0,1);wr(2,0);wr(3,0);wr(4,2);
 if(!dut.host_fault || dut.loaded_words!==0)$fatal(1,"out of order write");
 reset;upload;
 // Check all words through external read pins before commit.
 for(i=0;i<6020;i=i+1)begin
  wr(0,i&255);wr(1,i>>8);cycle;
  ui=8'h20;#1;actual[7:0]=qo;ui=8'h40;#1;actual[15:8]=qo;ui=0;
  if(actual!==image[i])$fatal(1,"host readback %0d",i);
 end
 wr(4,3);if(!dut.weights_ready || dut.host_fault)$fatal(1,"commit");
 if(VECTORS<100)begin $display("readback/commit complete at %0t",$time);$fflush();end
 for(n=0;n<VECTORS;n=n+1)begin
  for(j=0;j<24;j=j+1)begin
   wr(5,j);wr(2,inputs[n*24+j][7:0]);wr(3,inputs[n*24+j][15:8]);wr(6,0);cycle;
  end
  wr(7,0);cycle;cycles=0;
  while(!dut.done && cycles<20000)begin cycle;cycles=cycles+1;end
  if(!dut.done || dut.host_fault || dut.neural_fault)$fatal(1,"inference %0d",n);
  if(VECTORS<100)begin $display("vector %0d complete at %0t",n,$time);$fflush();end
  for(j=0;j<4;j=j+1)begin
   wr(9,j+1);ui=8'he0;#1;measured_cycles[j*8+:8]=qo;ui=0;
  end
  wr(9,0);
  if(measured_cycles!==3080)$fatal(1,"latency %0d",measured_cycles);
  for(j=0;j<4;j=j+1)begin
   wr(8,j);ui=8'h60;#1;actual[7:0]=qo;ui=8'h80;#1;actual[15:8]=qo;ui=0;
   if(actual!==gold[n*4+j])$fatal(1,"vector %0d output %0d got %h expected %h",n,j,actual,gold[n*4+j]);
  end
 end
 if(!NETLIST_SMOKE)begin
 // Independent oracle flags hidden overflow for an all-32767 input vector.
 for(j=0;j<24;j=j+1)begin wr(5,j);wr(2,8'hff);wr(3,8'h7f);wr(6,0);cycle;end
 wr(7,0);cycle;cycles=0;
 while(!dut.done && cycles<20000)begin cycle;cycles=cycles+1;end
 if(!dut.done || !dut.neural_fault || dut.host_fault)$fatal(1,"hidden overflow must fault");
 for(j=0;j<4;j=j+1)begin
  wr(8,j);ui=8'h60;#1;if(qo!==0)$fatal(1,"overflow low output");
  ui=8'h80;#1;if(qo!==0)$fatal(1,"overflow high output");ui=0;
 end
 $display("PASS hidden overflow: fault sticky and all outputs suppressed");
 // A fresh upload must invalidate the old result and loaded inputs.
 upload;if(dut.done || dut.weights_ready)$fatal(1,"stale result after BEGIN");
 wr(4,3);if(dut.done)$fatal(1,"stale result after COMMIT");
 // Reset invalidates readiness, while physical cells retain their contents.
 reset;wr(0,0);wr(1,0);cycle;ui=8'h20;#1;
 if(qo!==image[0][7:0] || dut.weights_ready)$fatal(1,"retention/validity");ui=0;
 upload;wr(4,3);
 // A complete image alone does not authorize incomplete inputs.
 wr(7,0);cycle;if(!dut.neural_fault || dut.busy)$fatal(1,"missing inputs");
 reset;upload;wr(4,3);
 end
 for(j=0;j<24;j=j+1)begin wr(5,j);wr(2,0);wr(3,0);wr(6,0);cycle;end
 wr(7,0);
 // Attempt BEGIN immediately after START, before busy has risen.
 wr(4,1);if(!dut.host_fault || !dut.weights_ready)$fatal(1,"pending-start ownership");
 wr(4,2);if(dut.memory_write)$fatal(1,"write during inference");
 ui=8'h60;#1;if(qo!==0)$fatal(1,"fault must hide result");ui=0;
 $display("PASS neural SRAM: 6020 readbacks, %0d vectors/%0d outputs, 3080 cycles, fail-closed ownership",VECTORS,VECTORS*4);
 $finish;
end
initial begin #60000000;$fatal(1,"test timeout");end
endmodule
