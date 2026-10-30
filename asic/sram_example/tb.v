`timescale 1ns/1ps
module tb;
reg [7:0] ui_in,uio_in;
reg ena,clk,rst_n;
wire [7:0] uo_out,uio_out,uio_oe;
tt_um_wlmoi_igor_sram_example user_project (
 .ui_in(ui_in),.uio_in(uio_in),.uo_out(uo_out),.uio_out(uio_out),
 .uio_oe(uio_oe),.ena(ena),.clk(clk),.rst_n(rst_n)
);
endmodule
