// William Anthony
// 13223048
// ISeeDesignITB
`timescale 1ns/1ps
`default_nettype none
module igor_uart_top #(parameter [15:0] CLKS_PER_BIT=16'd434,
 parameter [31:0] RX_TIMEOUT_CYCLES=32'd5000000)(
 input wire FPGA_CLK1_50,input wire [1:0] KEY,input wire [3:0] SW,
 input wire UART_RX,output wire UART_TX,output wire [7:0] LED);
reg [1:0] reset_sync;reg [3:0] sw_meta,sw_sync;
always @(posedge FPGA_CLK1_50 or negedge KEY[0])begin if(!KEY[0])reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};end
wire rst_n=reset_sync[1];
always @(posedge FPGA_CLK1_50 or negedge rst_n)begin if(!rst_n)begin sw_meta<=0;sw_sync<=0;end else begin sw_meta<=SW;sw_sync<=sw_meta;end end
wire command,protocol_fault;wire [7:0] op;wire [31:0] data;reg [31:0] response;reg invalid_command;
igor_uart_protocol #(.CLKS_PER_BIT(CLKS_PER_BIT),.RX_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES)) serial(FPGA_CLK1_50,rst_n,UART_RX,UART_TX,command,op,data,response,protocol_fault);
wire enable,busy,done;wire [4:0] vc;wire signed [6:0] wc;wire [7:0] fault,last;
wire [8:0] index;wire [31:0] latency,score,cost,goal,velocity,events;
// Enforce the complete command contract before any architectural side effect.
// Reserved bits must be zero; a correct CRC is not permission to reinterpret a
// malformed payload. An invalid command is sticky until external reset.
reg payload_ok;
always @(*) begin
 payload_ok=1'b0;
 case(op)
  1:payload_ok=1'b1; // Sequence validation belongs to the map manager.
  2:payload_ok=data[31:24]==0 && data[15]==0;
  4:payload_ok=data[31:28]==0 && data[27:20]==8'd1 && data[9:4]<=6'd16 && data[19:14]<=6'd32;
  8:payload_ok=data<32'd6020;
  10:payload_ok=data[7:5]==0 && data[31:24]==0 && data[4:0]<24;
  12:payload_ok=data[31:2]==0;
  3,5,6,7,9,11,13,14,15,16:payload_ok=data==0;
  default:payload_ok=1'b0;
 endcase
end
wire accepted_command=command && payload_ok && !invalid_command && !protocol_fault;
wire cfg_wr=accepted_command && op==4,cfg_lock=accepted_command && op==5,run=accepted_command && op==6;
wire mb=accepted_command && op==1,mw=accepted_command && op==2,mc=accepted_command && op==3;
// Begin command payload is visible during its command pulse. No stale sequence register.
igor_top core(FPGA_CLK1_50,rst_n,!protocol_fault && !invalid_command && !(command && !payload_ok) && !sw_sync[2],!KEY[1],sw_sync[3],run,cfg_wr,cfg_lock,data,
 mb,mw,mc,data,data[14:0],data[23:16],enable,vc,wc,fault,busy,done,latency,index,score,cost,goal,velocity,events,last);
wire signed [15:0] rom_data,nn_value;wire nn_busy,nn_done,nn_fault;wire [31:0] nn_cycles;
igor_neural_rom inspection_rom(FPGA_CLK1_50,data[12:0],rom_data);
igor_neural_core neural(FPGA_CLK1_50,rst_n,accepted_command && op==10,accepted_command && op==11,data[4:0],data[23:8],data[1:0],nn_value,nn_busy,nn_done,nn_fault,nn_cycles);
always @(posedge FPGA_CLK1_50 or negedge rst_n)begin
 if(!rst_n)begin invalid_command<=0;end
 else if(command)begin
  if(!payload_ok)invalid_command<=1;
 end
end
always @(*)begin
 response={7'd0,index,fault,3'd0,invalid_command,protocol_fault,done,busy,enable};
 case(op)
 8:response={16'd0,rom_data};
 9:response=latency;
 12:response={13'd0,nn_fault,nn_busy,nn_done,nn_value};
 13:response=nn_cycles;
 14:response={20'd0,wc,vc};
 15:response=events;
 16:response={24'd0,last};
 default:response={7'd0,index,fault,3'd0,invalid_command,protocol_fault,done,busy,enable};
 endcase
end
assign LED={fault[3:0],done,busy,rst_n,enable};
endmodule
`default_nettype wire
