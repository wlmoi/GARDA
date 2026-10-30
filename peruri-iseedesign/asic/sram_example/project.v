// SPDX-License-Identifier: Apache-2.0
`default_nettype none
// Minimal host-programmable parameter SRAM. The 256 words can hold W3.
module tt_um_wlmoi_igor_sram_example (
 input wire [7:0] ui_in,uio_in,
 output wire [7:0] uo_out,uio_out,uio_oe,
 input wire ena,clk,rst_n
);
reg [7:0] address;
reg [15:0] staged_data;
wire [15:0] read_data;
always @(posedge clk or negedge rst_n) begin
 if (!rst_n) begin address<=0;staged_data<=0;end
 else if (ena) begin
  if (ui_in[0]) address<=uio_in;
  if (ui_in[1]) staged_data[7:0]<=uio_in;
  if (ui_in[2]) staged_data[15:8]<=uio_in;
 end
end
igor_example_parameter_sram parameter_store (
 .clk(clk),.enable(rst_n && ena),.write_enable(ui_in[3]),
 .address(address),.write_data(staged_data),.read_data(read_data)
);
assign uo_out = ui_in[5] ? 8'hA7 : (ui_in[4] ? read_data[15:8] : read_data[7:0]);
assign uio_out=8'd0;
assign uio_oe=8'd0;
wire unused=&{ui_in[7:6],1'b0};
endmodule

module igor_example_parameter_sram (
 input wire clk,enable,write_enable,
 input wire [7:0] address,input wire [15:0] write_data,
 output wire [15:0] read_data
);
RM_IHPSG13_1P_256x16_c2_bm_bist i_sram (
 .A_CLK(clk),.A_MEN(enable),.A_WEN(write_enable),.A_REN(!write_enable),
 .A_ADDR(address),.A_DIN(write_data),.A_BM(16'hFFFF),.A_DLY(1'b1),.A_DOUT(read_data),
 .A_BIST_CLK(1'b0),.A_BIST_EN(1'b0),.A_BIST_MEN(1'b0),
 .A_BIST_WEN(1'b0),.A_BIST_REN(1'b0),.A_BIST_ADDR(8'd0),
 .A_BIST_DIN(16'd0),.A_BIST_BM(16'd0)
);
endmodule
`default_nettype wire
