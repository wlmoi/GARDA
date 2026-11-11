// GARDA DE10-Lite safe-reset channel.
//
// The legacy protocol latches protocol_fault on any framing/CRC error and then
// ignores every later frame until KEY0 reset. This sniffer listens on the same
// RX wire with its own unmodified garda_uart_rx instance and recognises exactly
// one constant 8-byte frame:
//
//     A5 22 54 45 53 52 <CRC8> 5A     (op 0x22 SAFE_RESET, payload "RSET")
//
// After a match it waits RESET_DELAY_CYCLES (so the core can finish sending its
// response frame) and then pulses reset for 16 clocks. Reset only ever returns
// GARDA to its safe power-on state (motor_enable=0, config unlocked, no map),
// so it cannot grant motor permission. The request is ignored while the
// physical E-stop (KEY1) is pressed, so it cannot be used to release a held
// E-stop button.
`timescale 1ns/1ps
`default_nettype none
module garda_safe_reset_sniffer #(parameter [15:0] CLKS_PER_BIT=16'd434)(
 input wire clk,rst_n,rx,block,output reg reset_pulse,output reg matched);
function [7:0] crc8;input [7:0] prior,value;reg [7:0] c;integer j;
 begin c=prior^value;for(j=0;j<8;j=j+1)c=c[7] ? (c<<1)^8'h07 : c<<1;crc8=c;end endfunction
function [7:0] frame_crc;input dummy;reg [7:0] c;
 begin c=crc8(8'd0,8'ha5);c=crc8(c,8'h22);c=crc8(c,8'h54);c=crc8(c,8'h45);c=crc8(c,8'h53);c=crc8(c,8'h52);frame_crc=c;end endfunction
localparam [7:0] CRC=frame_crc(1'b0);
localparam [63:0] FRAME={8'ha5,8'h22,8'h54,8'h45,8'h53,8'h52,CRC,8'h5a};
localparam [31:0] RESET_DELAY_CYCLES=CLKS_PER_BIT*32'd120; // 12 byte times
localparam [31:0] BYTE_GAP_CYCLES=CLKS_PER_BIT*32'd40;     // 4 byte times of silence clears the window
wire valid,error;wire [7:0] data;
garda_uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) receiver(clk,rst_n,rx,valid,error,data);
reg [63:0] window;reg [3:0] fill;reg [31:0] gap,delay;reg pending;reg [4:0] pulse_count;
reg [1:0] block_meta;
wire [63:0] next_window={window[55:0],data};
wire [3:0] next_fill=fill==4'd8 ? 4'd8 : fill+1'b1;
always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin window<=0;fill<=0;gap<=0;delay<=0;pending<=0;pulse_count<=0;reset_pulse<=0;matched<=0;block_meta<=0;end
 else begin
  block_meta<={block_meta[0],block};
  matched<=0;
  if(error)begin fill<=0;gap<=0;end
  else if(valid)begin
   gap<=0;
   if(next_fill==4'd8 && next_window==FRAME)begin
    fill<=0;window<=0;matched<=1;
    if(!block_meta[1] && !pending && pulse_count==0)begin pending<=1;delay<=0;end
   end else begin window<=next_window;fill<=next_fill;end
  end else if(fill!=0)begin
   if(gap>=BYTE_GAP_CYCLES)begin fill<=0;gap<=0;end else gap<=gap+1'b1;
  end
  if(pending)begin
   if(block_meta[1])pending<=0;                        // E-stop pressed meanwhile: abandon
   else if(delay>=RESET_DELAY_CYCLES)begin pending<=0;pulse_count<=5'd16;end
   else delay<=delay+1'b1;
  end
  if(pulse_count!=0)begin reset_pulse<=1;pulse_count<=pulse_count-1'b1;end else reset_pulse<=0;
 end
end
endmodule
`default_nettype wire
