`timescale 1ns/1ps
// Fault injection validates bridge rejection; the main CPU test uses no forces.
module tb_garda_riscv_bus_faults;
 reg clk=0;always #10 clk=~clk;
 reg rst_n=0;
 wire done,passed,bus_fault,trap,irq,eoi,trace_valid;
 wire [31:0] signature;wire [35:0] trace_data;
 garda_riscv_soc #(.BOOT_FILE("../../riscv/firmware/boot.hex")) dut(
   clk,rst_n,done,passed,bus_fault,signature,trap,irq,eoi,trace_valid,trace_data);
 reg [31:0] address,data;reg [3:0] strobes;reg instruction;
 task reject(input [31:0] a,input [3:0] s,input bit instr,input bit adapter_error);
 begin
   @(negedge clk);rst_n=0;
   force dut.mem_valid=0;
   repeat(3) @(negedge clk);
   address=a;strobes=s;instruction=instr;data=32'h12345678;
   force dut.mem_addr=address;force dut.mem_wdata=data;
   force dut.mem_wstrb=strobes;force dut.mem_instr=instruction;
   rst_n=1;force dut.mem_valid=1;
   #1;if(!adapter_error && dut.req_valid) $fatal(1,"illegal bridge transaction forwarded %h",a);
   repeat(4) @(negedge clk);
   if(!bus_fault || done || passed || dut.accelerator.index_reg!==0)
     $fatal(1,"bridge failed to reject address=%h strobes=%b",a,s);
   release dut.mem_addr;release dut.mem_wdata;release dut.mem_wstrb;
   release dut.mem_instr;release dut.mem_valid;
 end endtask
 initial begin
   reject(32'h10000002,4'b1111,0,0);
   reject(32'h1000000c,4'b0011,0,0);
   reject(32'h00000000,4'b1111,0,0);
   reject(32'h40000000,4'b1111,0,0);
   reject(32'h10000004,4'b0000,1,0);
   reject(32'h10000020,4'b1111,0,1);
   $display("PASS bus faults: alignment, partial strobes, ROM write, unmapped, MMIO instruction fetch, adapter error");
   $finish;
 end
 initial begin #100000; $fatal(1,"bridge fault test timeout");end
endmodule
