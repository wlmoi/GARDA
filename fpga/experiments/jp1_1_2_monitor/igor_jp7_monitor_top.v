`timescale 1ns/1ps
`default_nettype none
// DE10-Nano current src policy transport. No motor driver is connected here.
module igor_jp7_monitor_top(
 input wire FPGA_CLK1_50,
 input wire [1:0] KEY,
 input wire UART_RX,
 output wire UART_TX,
 output wire [7:0] LED
);
 reg [1:0] reset_sync;
 always @(posedge FPGA_CLK1_50 or negedge KEY[0])
   if (!KEY[0]) reset_sync <= 0;
   else reset_sync <= {reset_sync[0],1'b1};
 wire rst_n = reset_sync[1];
 // Inhibit includes the raw key; held presses latch until KEY0 reset.
 // The sampled path releases through two registers.
 reg [1:0] stop_sync;
 reg stop_latched;
 always @(posedge FPGA_CLK1_50 or negedge rst_n)
   if (!rst_n) stop_sync <= 2'b00;
   else stop_sync <= {stop_sync[0],!KEY[1]};
 always @(posedge FPGA_CLK1_50 or negedge rst_n)
   if (!rst_n) stop_latched <= 0;
   else if (!KEY[1]) stop_latched <= 1;
 wire stop_active = !KEY[1] | stop_sync[1] | stop_latched;

 wire policy_tx,echo_mode;
 wire [7:0] host_data,text_data;
 wire host_valid,host_ready,text_valid,text_ready;
 wire address,chipselect,read_n,write_n,waitrequest;
 wire [31:0] readdata,writedata;
 altera_avalon_jtag_uart jtag(.clk(FPGA_CLK1_50),.rst_n(rst_n),
  .av_address(address),.av_chipselect(chipselect),.av_read_n(read_n),.av_write_n(write_n),
  .av_writedata(writedata),.av_readdata(readdata),.av_waitrequest(waitrequest),.av_irq());
 igor_jtag_bytes bridge(FPGA_CLK1_50,rst_n,text_data,text_valid,text_ready,
  host_data,host_valid,host_ready,address,chipselect,read_n,write_n,writedata,readdata,waitrequest);
 igor_jp7_monitor monitor(FPGA_CLK1_50,rst_n,stop_active,UART_RX,host_data,host_valid,host_ready,
  text_data,text_valid,text_ready,echo_mode,accepted,rejected,cycles,error_code,state,response_valid,a0,a1,a2);
 // Diagnostic echo is physical pad RX->TX; it is not a neural inference result.
 assign UART_TX=echo_mode ? UART_RX : policy_tx;
 wire [3:0] state;
 wire [7:0] error_code;
 wire [15:0] error_flags;
 wire [31:0] accepted,rejected,cycles;
 wire permit,response_valid;
 wire signed [15:0] a0,a1,a2;
 igor_src_policy_uart #(
   .CLK_HZ(50000000),.BAUD(921600),
   .ROM_FILE("../../rtl/igor_src_policy/policy_weights.mem")
 ) policy(
   .clk(FPGA_CLK1_50),.rst_n(rst_n),.uart_rx(UART_RX),.uart_tx(policy_tx),
   .estop(stop_active),.debug_state(state),.error_code(error_code),
   .error_flags(error_flags),.accepted_frames(accepted),.rejected_frames(rejected),
   .last_latency_cycles(cycles),.safety_permit(permit),.response_valid(response_valid),
   .action0(a0),.action1(a1),.action2(a2)
 );
 assign LED = {error_code[3:0],stop_active,response_valid,rst_n,permit};
endmodule
`default_nettype wire
