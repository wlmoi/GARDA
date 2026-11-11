// Out-of-band host E-stop detector (one per UART port, BEFORE the two-host arbiter).
//
// The arbiter drops frames from a port that does not currently own the shared
// link. An E-stop must never wait for the link, so each raw RX pin also feeds this
// independent receiver (the unmodified garda_uart_rx). It recognises exactly one
// constant, CRC-valid 8-byte frame:
//
//     A5 21 00 00 00 00 <CRC8> 5A      (op 0x21 HOST_ESTOP, payload 0)
//
// and pulses `estop` for one clock. The DE10-Lite UART top ORs this pulse into its
// host E-stop latch, so the stop takes effect even while the other host is
// transmitting. It can only REMOVE motor permission.
`timescale 1ns/1ps
`default_nettype none
module garda_estop_sniffer #(parameter [15:0] CLKS_PER_BIT=16'd391)(
 input wire clk,rst_n,rx,output reg estop);
function [7:0] crc8;input [7:0] prior,value;reg [7:0] c;integer j;
 begin c=prior^value;for(j=0;j<8;j=j+1)c=c[7] ? (c<<1)^8'h07 : c<<1;crc8=c;end endfunction
function [7:0] frame_crc;input dummy;reg [7:0] c;
 begin c=crc8(8'd0,8'ha5);c=crc8(c,8'h21);c=crc8(c,8'h00);c=crc8(c,8'h00);c=crc8(c,8'h00);c=crc8(c,8'h00);frame_crc=c;end endfunction
localparam [7:0] CRC=frame_crc(1'b0);
localparam [63:0] FRAME={8'ha5,8'h21,8'h00,8'h00,8'h00,8'h00,CRC,8'h5a};
localparam [31:0] BYTE_GAP_CYCLES=CLKS_PER_BIT*32'd40;
wire valid,error;wire [7:0] data;
garda_uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) receiver(clk,rst_n,rx,valid,error,data);
reg [63:0] window;reg [3:0] fill;reg [31:0] gap;
wire [63:0] next_window={window[55:0],data};
wire [3:0] next_fill=fill==4'd8 ? 4'd8 : fill+1'b1;
always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin window<=0;fill<=0;gap<=0;estop<=0;end
 else begin
  estop<=0;
  if(error)begin fill<=0;gap<=0;end
  else if(valid)begin
   gap<=0;
   if(next_fill==4'd8 && next_window==FRAME)begin estop<=1;fill<=0;window<=0;end
   else begin window<=next_window;fill<=next_fill;end
  end else if(fill!=0)begin
   if(gap>=BYTE_GAP_CYCLES)begin fill<=0;gap<=0;end else gap<=gap+1'b1;
  end
 end
end
endmodule
`default_nettype wire
