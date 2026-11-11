// Two-host UART front end for the single GARDA protocol engine.
//
//   port A (laptop, JP1 pins 1/2) --\                         /-- garda_uart_protocol RX
//                                    >-- frame-level mux ----<
//   port B (Jetson, JP1 pins 3/4) --/                         \-- TX returned to the owner only
//
// The GARDA protocol is strictly one request -> one response, and a byte that
// arrives while a response is being sent latches protocol_fault. Two hosts must
// therefore never be merged bit-by-bit. This arbiter works at frame level:
//
// * A port is GRANTED when its line falls (start bit) after it has been idle for
//   at least IDLE_GUARD cycles (> 1 byte time). A port that is mid-frame never
//   satisfies the guard, so the core can only ever see whole bytes from one host.
// * While one port owns the link, the other port's frames are not forwarded (that
//   host gets no answer, times out and retries) and are counted as collisions.
// * The owner keeps the link until its RX line AND the core's TX line have been
//   idle for RELEASE_CYCLES (2 byte times) - i.e. after the response is complete.
// * The core's TX goes only to the owner; the other TX pin idles high.
// Nothing here can create or modify a frame, so framing/CRC checks stay in the core.
`timescale 1ns/1ps
`default_nettype none
module garda_uart_port_arbiter #(parameter [15:0] CLKS_PER_BIT=16'd391)(
 input wire clk,rst_n,
 input wire rx_a,rx_b,           // from the hosts (asynchronous)
 output reg rx_core,             // to garda_uart_protocol (idle high)
 input wire tx_core,             // from garda_uart_protocol
 output wire tx_a,tx_b,          // to the hosts
 output reg owner_valid,output reg owner,        // owner: 0 = A, 1 = B
 output reg [15:0] grants_a,grants_b,collisions);
localparam [31:0] IDLE_GUARD=CLKS_PER_BIT*32'd12;     // 12 bit times of idle before a start bit
localparam [31:0] RELEASE_CYCLES=CLKS_PER_BIT*32'd20; // 2 byte times of silence after the response
reg [1:0] ma,mb;wire sa=ma[1],sb=mb[1];
reg sa_q,sb_q;reg [31:0] idle_a,idle_b,quiet;
wire fall_a=sa_q && !sa,fall_b=sb_q && !sb;
wire start_a=fall_a && idle_a>=IDLE_GUARD,start_b=fall_b && idle_b>=IDLE_GUARD;
assign tx_a=owner_valid && !owner ? tx_core : 1'b1;
assign tx_b=owner_valid &&  owner ? tx_core : 1'b1;
always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin
  ma<=2'b11;mb<=2'b11;sa_q<=1;sb_q<=1;idle_a<=IDLE_GUARD;idle_b<=IDLE_GUARD;quiet<=0;rx_core<=1;   // idle at reset: first frame is accepted
  owner_valid<=0;owner<=0;grants_a<=0;grants_b<=0;collisions<=0;
 end else begin
  ma<={ma[0],rx_a};mb<={mb[0],rx_b};sa_q<=sa;sb_q<=sb;
  idle_a<=sa ? (idle_a==32'hffffffff ? idle_a : idle_a+1'b1) : 32'd0;
  idle_b<=sb ? (idle_b==32'hffffffff ? idle_b : idle_b+1'b1) : 32'd0;
  if(!owner_valid)begin
   rx_core<=1'b1;quiet<=0;
   if(start_a)begin owner_valid<=1;owner<=0;rx_core<=sa;if(grants_a!=16'hffff)grants_a<=grants_a+1'b1;
    if(start_b && collisions!=16'hffff)collisions<=collisions+1'b1; end   // simultaneous: A wins, B dropped
   else if(start_b)begin owner_valid<=1;owner<=1;rx_core<=sb;if(grants_b!=16'hffff)grants_b<=grants_b+1'b1;end
  end else begin
   rx_core<=owner ? sb : sa;
   if((owner ? start_a : start_b) && collisions!=16'hffff)collisions<=collisions+1'b1;
   if((owner ? sb : sa) && tx_core)begin
    if(quiet>=RELEASE_CYCLES)begin owner_valid<=0;rx_core<=1'b1;end else quiet<=quiet+1'b1;
   end else quiet<=0;
  end
 end
end
endmodule
`default_nettype wire
