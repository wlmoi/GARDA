`timescale 1ns/1ps
`default_nettype none
// Avalon master for Intel JTAG UART. A stalled host never drops output bytes.
module igor_jtag_bytes(input wire clk,rst_n,
 input wire [7:0] tx_data,input wire tx_valid,output reg tx_ready,
 output reg [7:0] rx_data,output reg rx_valid,input wire rx_ready,
 output wire address,chipselect,read_n,write_n,output wire [31:0] writedata,
 input wire [31:0] readdata,input wire waitrequest);
 localparam IDLE=0,CHECK=1,WRITE=2,READ=3,GAP=4;
 reg [2:0] state;
 assign address=state==CHECK;
 assign chipselect=state==CHECK || state==WRITE || state==READ;
 assign read_n=!(state==CHECK || state==READ);
 assign write_n=state!=WRITE;
 assign writedata={24'b0,tx_data};
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin state<=IDLE;tx_ready<=0;rx_valid<=0;rx_data<=0;end
  else begin
   tx_ready<=0;rx_valid<=0;
   case(state)
    IDLE: if(tx_valid)state<=CHECK;else if(rx_ready)state<=READ;
    CHECK: if(!waitrequest)begin if(readdata[31:16]!=0)state<=WRITE;else state<=GAP;end
    WRITE: if(!waitrequest)begin tx_ready<=1;state<=GAP;end
    READ: if(!waitrequest)begin rx_data<=readdata[7:0];rx_valid<=readdata[15];state<=GAP;end
    GAP: state<=IDLE;
    default: state<=IDLE;
   endcase
  end
 end
endmodule


`default_nettype wire
