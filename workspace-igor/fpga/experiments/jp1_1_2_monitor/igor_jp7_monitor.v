`timescale 1ns/1ps
`default_nettype none
module igor_jp7_monitor(input wire clk,rst_n,stop_active,pin_rx,
 input wire [7:0] host_data,input wire host_valid,output wire host_ready,
 output wire [7:0] text_data,output wire text_valid,input wire text_ready,
 output reg echo_mode,input wire [31:0] accepted,rejected,cycles,
 input wire [7:0] error_code,input wire [3:0] debug_state,
 input wire response_valid,input wire [15:0] a0,a1,a2);
 reg [31:0] result_seq,snap_seq;reg [15:0] result0,result1,result2,snap_a0,snap_a1,snap_a2;
 reg meta,sync,previous;
 reg [31:0] edges,rxbytes,framing;
 reg [7:0] last;
 wire rx_valid,rx_error;wire [7:0] rx_data;
 igor_uart_rx #(.CLKS_PER_BIT(54)) pad_decode(clk,rst_n,pin_rx,rx_valid,rx_error,rx_data);
 reg reporting;reg [7:0] index;
 reg [31:0] snap_edges,snap_rxbytes,snap_framing,snap_accepted,snap_rejected,snap_cycles;
 reg [7:0] snap_last,snap_error;reg [3:0] snap_state;reg snap_stop,snap_pin;
 assign host_ready=!reporting;
 assign text_valid=reporting;
 assign text_data=char_at(index);
 function [7:0] hexchar;input [3:0] n;begin hexchar=n<10 ? 48+n : 65+n-10;end endfunction
 `include "monitor_chars.vh"
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   result_seq<=0;snap_seq<=0;result0<=0;result1<=0;result2<=0;snap_a0<=0;snap_a1<=0;snap_a2<=0;
   meta<=1;sync<=1;previous<=1;edges<=0;rxbytes<=0;framing<=0;last<=0;
   reporting<=0;index<=0;echo_mode<=0;
   snap_edges<=0;snap_rxbytes<=0;snap_framing<=0;snap_accepted<=0;snap_rejected<=0;snap_cycles<=0;
   snap_last<=0;snap_error<=0;snap_state<=0;snap_stop<=0;snap_pin<=1;
  end else begin
   if(response_valid)begin result_seq<=result_seq+1;result0<=a0;result1<=a1;result2<=a2;end
   meta<=pin_rx;sync<=meta;previous<=sync;
   if(sync!=previous && edges!=32'hffffffff)edges<=edges+1'b1;
   if(rx_valid)begin if(rxbytes!=32'hffffffff)rxbytes<=rxbytes+1'b1;last<=rx_data;end
   if(rx_error && framing!=32'hffffffff)framing<=framing+1'b1;
   if(host_valid && host_ready && (host_data=="q" || host_data=="e" || host_data=="i"))begin
    if(host_data=="e")echo_mode<=1;
    if(host_data=="i")echo_mode<=0;
    snap_seq<=result_seq;snap_a0<=result0;snap_a1<=result1;snap_a2<=result2;
    snap_edges<=edges;snap_rxbytes<=rxbytes;snap_framing<=framing;snap_last<=last;
    snap_accepted<=accepted;snap_rejected<=rejected;snap_cycles<=cycles;snap_error<=error_code;
    snap_stop<=stop_active;snap_state<=debug_state;snap_pin<=sync;
    reporting<=1;index<=0;
   end else if(reporting && text_ready)begin
    if(index==LENGTH-1)reporting<=0;else index<=index+1'b1;
   end
  end
 end
endmodule
`default_nettype wire
