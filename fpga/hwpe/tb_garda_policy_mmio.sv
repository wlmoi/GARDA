`timescale 1ns/1ps
module tb_garda_policy_mmio;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=0, req_valid=0, req_write=0, resp_ready=0;
 reg [7:0] req_addr=0; reg [31:0] req_wdata=0;
 wire req_ready, resp_valid, resp_error, irq; wire [31:0] resp_rdata;
 garda_policy_mmio dut(clk,rst_n,req_valid,req_write,req_addr,req_wdata,req_ready,resp_valid,resp_ready,resp_rdata,resp_error,irq);
 reg [15:0] observations[0:17463]; reg [15:0] expected[0:707];
 reg [31:0] result, held_result; reg err; integer i, vector_id, output_id;
 task xfer(input bit wr,input [7:0] addr,input [31:0] data,output [31:0] value,output bit error);
 begin
  @(negedge clk); req_valid=1; req_write=wr; req_addr=addr; req_wdata=data; resp_ready=0;
  do @(posedge clk); while(!req_ready);
  @(negedge clk); req_valid=0;
  if(!resp_valid) $fatal(1,"missing response");
  value=resp_rdata; error=resp_error; resp_ready=1;
  @(posedge clk); @(negedge clk); resp_ready=0;
 end endtask
 task write_ok(input [7:0] addr,input [31:0] data);
 begin xfer(1,addr,data,result,err); if(err) $fatal(1,"write rejected addr=%h",addr); end endtask
 task read_ok(input [7:0] addr,output [31:0] data);
 begin xfer(0,addr,0,data,err); if(err) $fatal(1,"read rejected addr=%h",addr); end endtask
 initial begin
  $readmemh("../../verification/src_policy/artifacts/observations.hex",observations);
  $readmemh("../../verification/src_policy/artifacts/expected.hex",expected);
  repeat(3) @(posedge clk); @(negedge clk); rst_n=1;
  // A stalled response blocks subsequent requests and remains stable.
  @(negedge clk); req_valid=1;req_write=0;req_addr=8'h04;resp_ready=0;
  @(posedge clk); @(negedge clk); req_valid=1;req_write=1;req_addr=8'h08;req_wdata=12;
  repeat(3) begin @(posedge clk); #1; if(req_ready || !resp_valid || resp_rdata!==0) $fatal(1,"response backpressure failed"); end
  @(negedge clk); req_valid=0;resp_ready=1; @(posedge clk); @(negedge clk);resp_ready=0;
  read_ok(8'h08,result); if(result!==0) $fatal(1,"stalled request was accepted");
  xfer(1,8'h08,74,result,err); if(!err) $fatal(1,"invalid index accepted");
  xfer(0,8'h02,0,result,err); if(!err) $fatal(1,"invalid address accepted");
  xfer(1,8'h00,3,result,err); if(!err) $fatal(1,"invalid combined command accepted");
  read_ok(8'h04,result); if(result!==0 || irq) $fatal(1,"invalid command caused a side effect");
  write_ok(8'h00,1);
  read_ok(8'h04,result); if(!result[2] || result[7:4]!==4'd4 || !irq) $fatal(1,"incomplete frame did not fault");
  write_ok(8'h00,4); read_ok(8'h04,result); if(result!==0 || irq) $fatal(1,"reset failed");
  // Exercise abort and reject a data write while the policy is busy.
  for(i=0;i<74;i=i+1) write_ok(8'h0c,{16'b0,observations[i]});
  write_ok(8'h00,1);
  xfer(1,8'h0c,0,result,err); if(!err) $fatal(1,"busy data write accepted");
  xfer(1,8'h00,1,result,err); if(!err) $fatal(1,"busy start accepted");
  read_ok(8'h04,result); if(!result[0] || result[2]) $fatal(1,"busy rejection disturbed inference");
  write_ok(8'h00,2); read_ok(8'h04,result); if(result[2:0]!==0 || irq) $fatal(1,"abort failed");
  // Run the complete independent vector set; reset and reload for every frame.
  for(vector_id=0;vector_id<236;vector_id=vector_id+1) begin
   write_ok(8'h00,4);
   for(i=0;i<74;i=i+1) write_ok(8'h0c,{16'b0,observations[vector_id*74+i]});
   write_ok(8'h00,1);
   for(i=0;i<7200 && !irq;i=i+1) @(posedge clk);
   if(!irq) $fatal(1,"inference timeout vector=%0d",vector_id);
   read_ok(8'h04,result); if(result[2:0]!==3'b010) $fatal(1,"wrong done vector=%0d status=%h",vector_id,result);
   read_ok(8'h1c,result); if(result!==3556) $fatal(1,"wrong latency vector=%0d cycles=%d",vector_id,result);
   for(output_id=0;output_id<3;output_id=output_id+1) begin
    read_ok(8'h10+4*output_id,result);
    if(result!=={{16{expected[vector_id*3+output_id][15]}},expected[vector_id*3+output_id]})
      $fatal(1,"output mismatch vector=%0d output=%0d got=%h expected=%h",vector_id,output_id,result,expected[vector_id*3+output_id]);
   end
   if(vector_id==0) begin
    // Read OUT0, stall its response and change the pending request to OUT1.
    @(negedge clk); req_valid=1;req_write=0;req_addr=8'h10;resp_ready=0;
    @(posedge clk); @(negedge clk); held_result=resp_rdata;req_addr=8'h14;
    repeat(3) begin
     @(posedge clk); #1;
     if(req_ready || !resp_valid || resp_error || resp_rdata!==held_result ||
        resp_rdata!=={{16{expected[0][15]}},expected[0]})
       $fatal(1,"stalled output response changed when request address changed");
    end
    @(negedge clk);req_valid=0;resp_ready=1;@(posedge clk);@(negedge clk);resp_ready=0;
   end
  end
  write_ok(8'h00,4); read_ok(8'h10,result); if(result!==0 || irq) $fatal(1,"reset output not zero");
  $display("PASS: MMIO backpressure, faults, abort, 236 vectors/708 signed outputs, 3556 cycles"); $finish;
 end
 initial begin #30000000; $fatal(1,"test timeout"); end
endmodule
