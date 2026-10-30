// SPDX-License-Identifier: Apache-2.0
`default_nettype none
// 152 live activation words, striped for simultaneous even/odd operand reads.
// Writes hold both read outputs, supporting prefetch across neuron boundaries.
module igor_activation_sram(input wire clk,rst_n,enable,write_enable,
 input wire [7:0] address,input wire [15:0] write_data,
 output wire signed [15:0] read_even,read_odd);
wire valid=address<8'd152;
wire [15:0] bank_data[0:1];
reg read_valid;
always @(posedge clk or negedge rst_n)begin
 if(!rst_n)read_valid<=0;
 else if(enable && !write_enable)read_valid<=valid;
end
assign read_even=read_valid ? bank_data[0]:16'd0;
assign read_odd=read_valid ? bank_data[1]:16'd0;
genvar b;
generate for(b=0;b<2;b=b+1)begin: banks
 wire selected=rst_n && enable && valid && (!write_enable || address[0]==b);
 RM_IHPSG13_1P_256x16_c2_bm_bist i_sram(
  .A_CLK(clk),.A_MEN(selected),.A_WEN(write_enable),.A_REN(!write_enable),
  .A_ADDR({1'b0,address[7:1]}),.A_DIN(write_data),.A_BM(16'hffff),.A_DLY(1'b1),
  .A_DOUT(bank_data[b]),.A_BIST_CLK(1'b0),.A_BIST_EN(1'b0),.A_BIST_MEN(1'b0),
  .A_BIST_WEN(1'b0),.A_BIST_REN(1'b0),.A_BIST_ADDR(8'd0),
  .A_BIST_DIN(16'd0),.A_BIST_BM(16'd0));
end endgenerate
endmodule
`default_nettype wire
