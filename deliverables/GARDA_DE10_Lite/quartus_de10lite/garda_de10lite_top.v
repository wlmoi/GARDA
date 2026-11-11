// DE10-Lite (MAX 10 10M50DAF484C7G) top level for the unmodified GARDA UART design (garda_uart_top).
//   UART: Arduino header D0 = FPGA RX (connect adapter TX), D1 = FPGA TX (connect adapter RX), 115200 8N1, 3.3 V logic.
//   LEDR[7:0] = garda_uart_top LED = {fault[3:0], done, busy, rst_n, enable}
//   LEDR8 = UART RX activity (stretched), LEDR9 = UART TX activity (stretched)
//   SW[3:0] -> design switches (SW2 ready-inhibit, SW3 protective stop; SW0/SW1 unused), SW[9:4] unused.
//   KEY0 = reset, KEY1 = E-stop (both active low).
`timescale 1ns/1ps
`default_nettype none
module garda_de10lite_top(
  input  wire        MAX10_CLK1_50,
  input  wire [1:0]  KEY,
  input  wire [9:0]  SW,
  input  wire        ARDUINO_RX,
  output wire        ARDUINO_TX,
  output wire [9:0]  LEDR);
  wire [7:0] led;
  garda_uart_top core(.FPGA_CLK1_50(MAX10_CLK1_50), .KEY(KEY), .SW(SW[3:0]), .UART_RX(ARDUINO_RX), .UART_TX(ARDUINO_TX), .LED(led));
  // Activity stretchers (~84 ms) so single frames are visible to the eye.
  reg rx_m = 1'b1, rx_s = 1'b1, tx_m = 1'b1, tx_s = 1'b1; reg [22:0] rx_cnt = 0, tx_cnt = 0;
  always @(posedge MAX10_CLK1_50) begin
    rx_m <= ARDUINO_RX; rx_s <= rx_m; tx_m <= ARDUINO_TX; tx_s <= tx_m;
    if (!rx_s) rx_cnt <= {23{1'b1}}; else if (rx_cnt != 0) rx_cnt <= rx_cnt - 1'b1;
    if (!tx_s) tx_cnt <= {23{1'b1}}; else if (tx_cnt != 0) tx_cnt <= tx_cnt - 1'b1;
  end
  assign LEDR = {tx_cnt != 0, rx_cnt != 0, led};
endmodule
`default_nettype wire
