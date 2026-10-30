`default_nettype none
`include "defines.vh"
// One physical read/write port. The falling edge prepares the next instruction
// for the rising-edge execution grant without changing the four-context cadence.
module program_memory (
 input wire clk, rst_n,
 input wire [7:0] address,
 input wire write_enable,
 input wire high_byte,
 input wire [7:0] write_data,
 output wire [15:0] read_data
);
`ifdef JP_FPGA_SYNC_MEMORY
 reg [15:0] words [0:255];
 reg [15:0] read_q;
 always @(posedge clk) begin
  if (write_enable) begin
   if (high_byte) words[address][15:8] <= write_data;
   else words[address][7:0] <= write_data;
  end
 end
 always @(negedge clk) read_q <= words[address];
 assign read_data = read_q;
`else
`ifdef JP_REGISTER_MEMORY
 reg [15:0] words [0:255];
 always @(posedge clk) begin
  if (write_enable) begin
   if (high_byte) words[address][15:8] <= write_data;
   else words[address][7:0] <= write_data;
  end
 end
 assign read_data = words[address];
`else
 wire memory_clock = ~clk;
 RM_IHPSG13_1P_256x16_c2_bm_bist i_sram (
  .A_CLK(memory_clock), .A_MEN(rst_n),
  .A_WEN(write_enable), .A_REN(!write_enable),
  .A_ADDR(address), .A_DIN({write_data, write_data}),
  .A_BM(high_byte ? 16'hFF00 : 16'h00FF),
  .A_DLY(1'b1), .A_DOUT(read_data),
  .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
  .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(8'd0),
  .A_BIST_DIN(16'd0), .A_BIST_BM(16'd0)
 );
`endif
`endif
endmodule
