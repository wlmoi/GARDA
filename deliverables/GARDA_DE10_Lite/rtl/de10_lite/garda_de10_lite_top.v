// GARDA DE10-Lite board top (Terasic DE10-Lite, MAX 10 10M50DAF484C7G).
//
// Pin names follow the DE10-Lite User Manual (Terasic, 2022-10-17) tables 3-2..3-7.
//   MAX10_CLK1_50  PIN_P11  50 MHz oscillator -> PLL 45 MHz core clock; VGA uses it directly
//   KEY[0]         PIN_B8   reset (active low)          KEY[1] PIN_A7 E-stop (press = stop)
//   SW[2]          PIN_D12  UP = "not ready"            SW[3]  PIN_C12 UP = protective stop
//   Port A (laptop, USB-TTL cable): JP1 pin 1 = GPIO_0 PIN_V10 RX <- adapter TXD, pin 2 = GPIO_1 PIN_W10 TX -> adapter RXD
//   Port B (Jetson Nano J41):       JP1 pin 3 = GPIO_2 PIN_V9  RX <- Jetson pin 8, pin 4 = GPIO_3 PIN_W9 TX -> Jetson pin 10
//   Both 3.3 V. GND: JP1 pin 12 (adapter) and pin 30 (Jetson pin 6).
//   GND            JP1 pin 12 (or 30)
//
// Indicators
//   LEDR[0] motor_enable  LEDR[1] reset released  LEDR[2] busy  LEDR[3] done
//   LEDR[7:4] fault_code[3:0]   LEDR[8] host E-stop or watchdog latched
//   LEDR[9] UART frame activity (stretched ~42 ms)      SW1 UP: LEDR mirrors SW9..0 (switch test)
//   HEX5..HEX1 = "GArdA" (SW0 DOWN)  |  SW0 UP: HEX5:4 fault, HEX3:2 last fault, HEX1:0 commands
`timescale 1ns/1ps
`default_nettype none
`include "garda_build_config.vh"
// Clocking: core (GARDA, UART, sniffer, HEX/LED) runs on the 45 MHz PLL output.
// VGA runs on the 50 MHz oscillator (25 MHz pixel rate) behind a 2-flop synchroniser.
module garda_de10_lite_top #(parameter [31:0] CLOCK_HZ=`GARDA_CLOCK_HZ,
 parameter [15:0] CLKS_PER_BIT=`GARDA_CLKS_PER_BIT,
 parameter [31:0] BUILD_ID=`GARDA_BUILD_ID,
 parameter [31:0] RX_TIMEOUT_CYCLES=CLOCK_HZ/10)(   // 100 ms, as the 5 000 000 cycles at 50 MHz
 input wire MAX10_CLK1_50,
 input wire [1:0] KEY,
 input wire [9:0] SW,
 output wire [9:0] LEDR,
 output wire [7:0] HEX0,HEX1,HEX2,HEX3,HEX4,HEX5,
 input wire [1:0] JP1_RX,     // [0] port A (pin 1), [1] port B (pin 3); weak pull-ups
 output wire [1:0] JP1_TX,    // [0] port A (pin 2), [1] port B (pin 4)
 // VGA connector (manual table 3-11): live status screen, 640x480 @ 60 Hz.
 output wire [3:0] VGA_R,VGA_G,VGA_B,
 output wire VGA_HS,VGA_VS);
localparam [31:0] LEASE_CYCLES=CLOCK_HZ/50;           // 20 ms map freshness and command lease
localparam [15:0] CYCLES_PER_MS=CLOCK_HZ/1000;
wire UART_RX,UART_TX;   // core side of the two-host arbiter (declared here, arbiter below)
wire clk,pll_locked;
reg [9:0] sw_m,sw_q,ledr_q;reg [1:0] key_m,key_q;   // board I/O snapshot (core clock)
garda_clock core_clock(.clk50(MAX10_CLK1_50),.clk(clk),.locked(pll_locked));
wire key0_ok=KEY[0] & pll_locked;                     // hold everything in reset until the PLL locks

// Sniffer reset comes only from KEY0 / PLL lock (never from its own pulse).
reg [1:0] sniff_rst;
always @(posedge clk or negedge key0_ok)begin if(!key0_ok)sniff_rst<=0;else sniff_rst<={sniff_rst[0],1'b1};end
wire soft_reset,safe_reset_matched;
// Two hosts (laptop on port A, Jetson on port B) share the single protocol engine frame by frame.
wire port_owner_valid,port_owner;wire [15:0] grants_a,grants_b,collisions;
garda_uart_port_arbiter #(.CLKS_PER_BIT(CLKS_PER_BIT)) ports(.clk(clk),.rst_n(sniff_rst[1]),
 .rx_a(JP1_RX[0]),.rx_b(JP1_RX[1]),.rx_core(UART_RX),.tx_core(UART_TX),.tx_a(JP1_TX[0]),.tx_b(JP1_TX[1]),
 .owner_valid(port_owner_valid),.owner(port_owner),.grants_a(grants_a),.grants_b(grants_b),.collisions(collisions));
garda_safe_reset_sniffer #(.CLKS_PER_BIT(CLKS_PER_BIT)) safe_reset(clk,sniff_rst[1],UART_RX,!KEY[1],soft_reset,safe_reset_matched);
// Out-of-band E-stop: watches each raw RX pin, so a host E-stop is never dropped by the arbiter.
wire oob_estop_a,oob_estop_b;
garda_estop_sniffer #(.CLKS_PER_BIT(CLKS_PER_BIT)) estop_a(.clk(clk),.rst_n(sniff_rst[1]),.rx(JP1_RX[0]),.estop(oob_estop_a));
garda_estop_sniffer #(.CLKS_PER_BIT(CLKS_PER_BIT)) estop_b(.clk(clk),.rst_n(sniff_rst[1]),.rx(JP1_RX[1]),.estop(oob_estop_b));

wire [7:0] led,fault,last_fault;wire host_estop,watchdog_trip,frame;wire [15:0] accepted_count;wire [47:0] obs;reg [20:0] activity;
garda_lite_uart_top #(.CLKS_PER_BIT(CLKS_PER_BIT),.RX_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES),
 .CYCLES_PER_MS(CYCLES_PER_MS),.BUILD_ID(BUILD_ID),.DEADLINE_CYCLES(LEASE_CYCLES),.FRESH_CYCLES(LEASE_CYCLES)) garda(
 clk,{KEY[1],key0_ok & !soft_reset},SW[3:0],UART_RX,UART_TX,led,
 fault,last_fault,host_estop,watchdog_trip,frame,accepted_count,obs,{collisions,grants_b,grants_a},port_owner,
 {pll_locked,ledr_q,key_q,sw_q},oob_estop_a || oob_estop_b);
// Board I/O snapshot for BOARD_IO (registered; the switches are asynchronous inputs).
always @(posedge clk)begin sw_m<=SW;sw_q<=sw_m;key_m<=KEY;key_q<=key_m;ledr_q<=LEDR;end
always @(posedge clk or negedge sniff_rst[1])begin
 if(!sniff_rst[1])activity<=0;else if(frame)activity<=21'h1fffff;else if(activity!=0)activity<=activity-1'b1;
end
// SW1 UP: LED test - each LEDR shows its own switch. DOWN: GARDA status (see header).
wire [9:0] status_leds={activity!=0,host_estop || watchdog_trip,led};
assign LEDR=sw_q[1] ? sw_q : status_leds;

// ---- VGA (observation only) -------------------------------------------------
// Snapshot in the core domain, then two flops in the 50 MHz domain. Multi-bit
// values may show a mixed old/new value for one 20 ns sample, never longer than
// one video frame - acceptable for a display that cannot influence the core.
// layout: [98:83] grants_b [82:67] grants_a [66] activity [65] watchdog_trip [64] host_estop [63:56] last_fault [55:48] fault [47:0] obs
reg [98:0] vga_bus;
always @(posedge clk)vga_bus<={grants_b,grants_a,activity!=0,watchdog_trip,host_estop,last_fault,fault,obs};
(* altera_attribute = "-name SYNCHRONIZER_IDENTIFICATION FORCED_IF_ASYNCHRONOUS" *) reg [98:0] vga_meta;
reg [98:0] vga_sync;reg [1:0] vga_rst;
always @(posedge MAX10_CLK1_50 or negedge KEY[0])begin if(!KEY[0])vga_rst<=0;else vga_rst<={vga_rst[0],1'b1};end
always @(posedge MAX10_CLK1_50)begin vga_meta<=vga_bus;vga_sync<=vga_meta;end
wire [47:0] vobs=vga_sync[47:0];
reg [9:0] vga_sw_m,vga_sw;always @(posedge MAX10_CLK1_50)begin vga_sw_m<=SW;vga_sw<=vga_sw_m;end
garda_vga_status screen(.clk(MAX10_CLK1_50),.rst_n(vga_rst[1]),
 .motor_enable(vobs[12]),.busy(vobs[14]),.done(vobs[13]),.protocol_fault(vobs[16]),.invalid_command(vobs[15]),
 .host_estop(vga_sync[64]),.key_estop(vobs[17]),.watchdog_armed(vobs[18]),.watchdog_trip(vga_sync[65]),
 .nn_busy(vobs[19]),.nn_done(vobs[20]),.nn_fault(vobs[21]),.uart_activity(vga_sync[66]),
 .fault(vga_sync[55:48]),.last_fault(vga_sync[63:56]),.last_op(vobs[29:22]),.v_cmd(vobs[4:0]),.w_cmd(vobs[11:5]),
 .frames(vobs[45:30]),.port_a(vga_sync[82:67]),.port_b(vga_sync[98:83]),.sw(vga_sw),.vga_r(VGA_R),.vga_g(VGA_G),.vga_b(VGA_B),.vga_hs(VGA_HS),.vga_vs(VGA_VS));

// SW0 DOWN (default): "GArdA" permanently lit on HEX5..HEX1 - visible proof the board runs GARDA.
//   G = "6" without the middle bar.  HEX0: dark, its DP blinks on UART activity.
// SW0 UP: status page HEX5:4 fault, HEX3:2 last fault, HEX1:0 accepted commands (DP4 host E-stop, DP2 watchdog).
localparam [6:0] SEG_G=7'b1000010,SEG_A=7'b0001000,SEG_R=7'b0101111,SEG_D=7'b0100001,SEG_OFF=7'b1111111;
wire [7:0] st5,st4,st3,st2,st1,st0;
garda_hex7 h5(fault[7:4],1'b0,st5);
garda_hex7 h4(fault[3:0],host_estop,st4);
garda_hex7 h3(last_fault[7:4],1'b0,st3);
garda_hex7 h2(last_fault[3:0],watchdog_trip,st2);
garda_hex7 h1(accepted_count[7:4],1'b0,st1);
garda_hex7 h0(accepted_count[3:0],activity!=0,st0);
wire page=sw_q[0];
assign HEX5=page ? st5 : {1'b1,SEG_G};
assign HEX4=page ? st4 : {1'b1,SEG_A};
assign HEX3=page ? st3 : {1'b1,SEG_R};
assign HEX2=page ? st2 : {1'b1,SEG_D};
assign HEX1=page ? st1 : {1'b1,SEG_A};
assign HEX0=page ? st0 : {!(activity!=0),SEG_OFF};
endmodule

// Common-anode 7-segment decoder: segment on = 0. Bit order {DP,g,f,e,d,c,b,a}.
module garda_hex7(input wire [3:0] value,input wire dp,output reg [7:0] seg);
always @(*)begin
 case(value)
  4'h0:seg[6:0]=7'b1000000; 4'h1:seg[6:0]=7'b1111001; 4'h2:seg[6:0]=7'b0100100; 4'h3:seg[6:0]=7'b0110000;
  4'h4:seg[6:0]=7'b0011001; 4'h5:seg[6:0]=7'b0010010; 4'h6:seg[6:0]=7'b0000010; 4'h7:seg[6:0]=7'b1111000;
  4'h8:seg[6:0]=7'b0000000; 4'h9:seg[6:0]=7'b0010000; 4'ha:seg[6:0]=7'b0001000; 4'hb:seg[6:0]=7'b0000011;
  4'hc:seg[6:0]=7'b1000110; 4'hd:seg[6:0]=7'b0100001; 4'he:seg[6:0]=7'b0000110; default:seg[6:0]=7'b0001110;
 endcase
 seg[7]=!dp;
end
endmodule
`default_nettype wire
