// SPDX-License-Identifier: Apache-2.0
`default_nettype none
// Pack all 6020 logical words into one physical 2048x64 SRAM.
// Each row holds four 16-bit words; a masked write modifies one quarter.
module igor_parameter_sram (
 input wire clk,rst_n,enable,write_enable,
 input wire [12:0] address,input wire [15:0] write_data,write_mask,
 output wire signed [15:0] read_data,read_even,read_odd
);
wire valid = address < 13'd6020;
wire [63:0] row_data;
wire [63:0] row_mask = {48'd0,write_mask} << {address[1:0],4'b0000};
reg [1:0] read_quarter;
reg read_valid;
always @(posedge clk or negedge rst_n) begin
 if (!rst_n) begin read_quarter<=0;read_valid<=0;end
 else if (enable && !write_enable) begin
  read_quarter<=address[1:0];read_valid<=valid;
 end
end
assign read_data = read_valid ? row_data[{read_quarter,4'b0000} +:16] : 16'd0;
wire [31:0] pair_data = read_quarter[1] ? row_data[63:32] : row_data[31:0];
assign read_even = read_valid ? pair_data[15:0] : 16'd0;
assign read_odd = read_valid ? pair_data[31:16] : 16'd0;
RM_IHPSG13_1P_2048x64_c2_bm_bist i_sram (
  .A_CLK(clk),.A_MEN(rst_n && enable && valid),.A_WEN(write_enable),
  .A_REN(!write_enable),.A_ADDR(address[12:2]),
  .A_DIN({4{write_data}}),.A_BM(row_mask),.A_DLY(1'b1),.A_DOUT(row_data),
  .A_BIST_CLK(1'b0),.A_BIST_EN(1'b0),.A_BIST_MEN(1'b0),
  .A_BIST_WEN(1'b0),.A_BIST_REN(1'b0),.A_BIST_ADDR(11'd0),
  .A_BIST_DIN(64'd0),.A_BIST_BM(64'd0)
 );
endmodule
`default_nettype wire
