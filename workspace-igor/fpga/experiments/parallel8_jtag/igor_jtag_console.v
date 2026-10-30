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

module igor_jtag_console #(parameter integer AUTO_DELAY=150000000,
 parameter integer REPLY_TIMEOUT=5000000)(
 input wire clk,rst_n,estop,
 input wire [7:0] host_data,input wire host_valid,output wire host_ready,
 output wire [7:0] terminal_data,output wire terminal_valid,input wire terminal_ready,
 output wire serial_rx,input wire serial_tx,
 input wire [31:0] cycles,accepted,rejected,input wire [7:0] error_code);
 localparam IDLE=0,DEMO=1,WAIT_REPLY=2,REPORT=3;
 reg [1:0] state;
 reg [7:0] frame[0:255];reg [7:0] expected[0:15];
 reg [7:0] captured[0:10];
 reg [7:0] index;reg [3:0] count;
 reg [31:0] timer,boot_timer,snap_cycles,snap_accepted,snap_rejected;
 reg [7:0] snap_error;
 reg auto_pending,bad_crc,check_pass,matched,demo_mode;
 reg nibble_pending,hex_started;reg [3:0] nibble;
 reg send;reg [7:0] send_data;wire busy;
 wire got,framing;wire [7:0] received;
 integer i;
 initial begin $readmemh("demo_frame.mem",frame);$readmemh("demo_expected.mem",expected);end
 igor_uart_tx #(.CLKS_PER_BIT(54)) inject(clk,rst_n,send,send_data,serial_rx,busy);
 igor_uart_rx #(.CLKS_PER_BIT(54)) monitor(clk,rst_n,serial_tx,got,framing,received);
 assign host_ready=state==IDLE && !busy && !send;
 assign terminal_valid=state==REPORT;
 assign terminal_data=status_char(index);
 function [7:0] hexchar;input [3:0] x;begin hexchar=x<10 ? 8'h30+x : 8'h41+x-10;end endfunction
 function ishex;input [7:0] x;begin ishex=(x>="0"&&x<="9")||(x>="a"&&x<="f")||(x>="A"&&x<="F");end endfunction
 function [3:0] unhex;input [7:0] x;begin unhex=x<="9" ? x-"0" : (x|8'h20)-"a"+10;end endfunction
 `include "status_chars.vh"
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n)begin
   state<=IDLE;index<=0;count<=0;timer<=0;boot_timer<=0;auto_pending<=1;
   bad_crc<=0;check_pass<=0;matched<=1;demo_mode<=1;send<=0;send_data<=0;
   snap_cycles<=0;snap_accepted<=0;snap_rejected<=0;snap_error<=0;
   nibble_pending<=0;hex_started<=0;nibble<=0;
   for(i=0;i<11;i=i+1)captured[i]<=0;
  end else begin
   send<=0;
   if(auto_pending && boot_timer<AUTO_DELAY)boot_timer<=boot_timer+1'b1;
   if(got)begin
    if(count<11)begin captured[count]<=received;count<=count+1'b1;
      if(received!=expected[count])matched<=0;
    end else matched<=0;
   end
   case(state)
    IDLE: begin
     timer<=0;
     if(auto_pending && boot_timer==AUTO_DELAY && !busy && !send)begin
      auto_pending<=0;bad_crc<=0;demo_mode<=1;index<=0;count<=0;matched<=1;state<=DEMO;
     end else if(host_valid && host_ready)begin
      auto_pending<=0;
      if(host_data=="r" || host_data=="R" || host_data=="!")begin
       bad_crc<=host_data=="!";demo_mode<=1;index<=0;count<=0;matched<=1;nibble_pending<=0;hex_started<=0;state<=DEMO;
       for(i=0;i<11;i=i+1)captured[i]<=0;
      end else if(ishex(host_data))begin
       demo_mode<=0;
       hex_started<=1;
       if(!hex_started)begin
        count<=0;matched<=1;
        for(i=0;i<11;i=i+1)captured[i]<=0;
       end
       if(!nibble_pending)begin nibble<=unhex(host_data);nibble_pending<=1;end
       else begin send_data<={nibble,unhex(host_data)};send<=1;nibble_pending<=0;end
      end else if((host_data==13 || host_data==10) && hex_started)begin
       bad_crc<=0;timer<=0;nibble_pending<=0;hex_started<=0;state<=WAIT_REPLY;
      end
     end
    end
    DEMO: if(!busy && !send)begin
     send_data<=frame[index] ^ ((bad_crc && index==152) ? 8'h01 : 8'h00);send<=1;
     if(index==152)begin timer<=0;state<=WAIT_REPLY;end else index<=index+1'b1;
    end
    WAIT_REPLY: begin
     timer<=timer+1'b1;
     if(count==11 || timer==REPLY_TIMEOUT)begin
      snap_cycles<=cycles;snap_accepted<=accepted;snap_rejected<=rejected;snap_error<=error_code;
      check_pass<=bad_crc ? (count==0 && error_code==6) : (count==11 && matched && cycles==6916 && !estop);
      index<=0;state<=REPORT;
     end
    end
    REPORT: if(terminal_ready)begin
     if(index==STATUS_LENGTH-1)begin state<=IDLE;count<=0;matched<=1;end
     else index<=index+1'b1;
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
`default_nettype wire
