`timescale 1ns/1ps
`ifndef SWV
`define SWV 4'b0000
`endif
`ifndef KEYV
`define KEYV 2'b11
`endif
module tb;
 reg clk=0, rx=1; reg [1:0] key=2'b11; reg [3:0] sw=`SWV; wire tx; wire [7:0] led;
 reg [7:0] frames [0:4095]; integer nframes, f, i, b;
 garda_uart_top dut(.FPGA_CLK1_50(clk),.KEY(key),.SW(sw),.UART_RX(rx),.UART_TX(tx),.LED(led));
 always #10 clk=~clk;
 task send_byte(input [7:0] d); integer k; begin
   rx=0; repeat(434) @(posedge clk);
   for(k=0;k<8;k=k+1) begin rx=d[k]; repeat(434) @(posedge clk); end
   rx=1; repeat(434) @(posedge clk); end endtask
 // independent UART receiver on the FPGA TX pin
 reg [7:0] r; integer j;
 initial forever begin @(negedge tx); repeat(217) @(posedge clk);
   for(j=0;j<8;j=j+1) begin repeat(434) @(posedge clk); r[j]=tx; end
   repeat(434) @(posedge clk); $display("RX %02x", r); end
 initial begin
  $readmemh("frames.hex", frames); nframes = `NFRAMES;
  key=2'b10; repeat(10) @(posedge clk); key=`KEYV; repeat(50) @(posedge clk);
  for(f=0;f<nframes;f=f+1) begin
    $display("FRAME %0d", f);
    for(b=0;b<8;b=b+1) send_byte(frames[f*8+b]);
    repeat(434*10*12) @(posedge clk);   // 12 byte times: response (8 bytes) fully received
    if (f==`NN_WAIT_AT) repeat(60000) @(posedge clk);
  end
  $display("DONE"); $finish;
 end
endmodule
