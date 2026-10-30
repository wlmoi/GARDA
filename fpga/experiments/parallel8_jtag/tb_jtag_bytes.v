`timescale 1ns/1ps
module tb_jtag_bytes;
 reg clk=0;always #10 clk=~clk;
 reg rst_n=0;reg [7:0] tx_data=0;reg tx_valid=1;wire tx_ready;
 wire [7:0] rx_data;wire rx_valid;
 wire address,chipselect,read_n,write_n;wire [31:0] writedata;
 reg [31:0] readdata=0;reg waitrequest=1;
 integer ticks=0,writes=0,receives=0;
 igor_jtag_bytes dut(clk,rst_n,tx_data,tx_valid,tx_ready,rx_data,rx_valid,1'b1,
 address,chipselect,read_n,write_n,writedata,readdata,waitrequest);
 // Same registered handshake shape as the installed Intel IP, with FIFO-full
 // intervals. Assert byte order at each actual Avalon write side effect.
 always @(posedge clk) begin
  if(!rst_n)begin waitrequest<=1;ticks<=0;end
  else begin
   ticks<=ticks+1;
   waitrequest<=!(chipselect && (!write_n || !read_n) && waitrequest);
   if(chipselect && !read_n && waitrequest)begin
    if(address)readdata<=(ticks%29<10) ? 0 : 32'h00400000;
    else readdata<=receives==0 ? 32'h00008072 : 0;
   end
   if(chipselect && !write_n && waitrequest)begin
    if(writedata[7:0] !== writes[7:0])$fatal(1,"Dropped/duplicated TX byte");
    writes<=writes+1;
   end
   if(tx_ready)begin
    if(tx_data==199)tx_valid<=0;else tx_data<=tx_data+1'b1;
   end
   if(rx_valid)begin
    if(rx_data!==8'h72)$fatal(1,"RX corrupted");
    receives<=receives+1;
   end
   if(writes==200 && receives==1)begin
    $display("PASS: 200 ordered bytes, FIFO-full retry, registered Avalon handshake, host RX");$finish;
   end
  end
 end
 initial begin repeat(5)@(negedge clk);rst_n=1;end
 initial begin #1000000;$fatal(1,"Bridge watchdog");end
endmodule
