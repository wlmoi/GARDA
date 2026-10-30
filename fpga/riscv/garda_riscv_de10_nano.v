// Self-test FPGA image: LED proof only, no motor or external communication.
`timescale 1ns/1ps
`default_nettype none
module garda_riscv_de10_nano(
 input wire FPGA_CLK1_50,input wire [1:0] KEY,output wire [7:0] LED
);
 wire raw_reset_n=KEY[0] && KEY[1];
 reg [1:0] reset_sync;
 always @(posedge FPGA_CLK1_50 or negedge raw_reset_n)
   if(!raw_reset_n) reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
 wire rst_n=reset_sync[1];
 wire done,passed,bus_fault,trap,irq,eoi;
 wire [31:0] signature;
 garda_riscv_soc #(.BOOT_FILE("../firmware/boot.hex")) soc(
   .clk(FPGA_CLK1_50),.rst_n(rst_n),.test_done(done),.test_pass(passed),
   .bus_fault(bus_fault),.signature(signature),.cpu_trap(trap),
   .accelerator_irq(irq),.irq_eoi(eoi),.cpu_trace_valid(),.cpu_trace_data()
 );
 assign LED={2'b00,eoi,irq,(done && !passed),trap || bus_fault,passed,rst_n};
endmodule
`default_nettype wire
