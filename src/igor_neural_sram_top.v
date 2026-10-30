// SPDX-License-Identifier: Apache-2.0
`default_nettype none
// Synchronous register interface. Host holds the inputs over a rising edge;
// SRAM transactions latched there execute on the next rising edge.
module tt_um_wlmoi_igor_neural_sram (
 input wire [7:0] ui_in,output reg [7:0] uo_out,
 input wire [7:0] uio_in,output wire [7:0] uio_out,uio_oe,
 input wire ena,clk,rst_n
);
reg [12:0] host_address,loaded_words;
reg [15:0] staged_data;
reg [1:0] staged_bytes;
reg loading,weights_ready,host_fault;
reg memory_write;
reg [12:0] write_address;
reg [15:0] write_word;
reg load_input,start;
reg [4:0] input_index;
reg [1:0] output_index;
reg [2:0] diagnostic_page;
wire [12:0] core_address;
wire signed [15:0] memory_data,memory_even,memory_odd,output_value;
wire busy,done,neural_fault;
wire [31:0] latency_cycles;
wire effective_ready=weights_ready && !host_fault;
// A new parameter image also invalidates old inputs, outputs and datapath faults.
wire neural_rst_n=rst_n && !loading;
wire [12:0] memory_address=memory_write ? write_address :
 (busy ? core_address : host_address);
igor_parameter_sram parameter_store(clk,rst_n,1'b1,memory_write,
 memory_address,write_word,16'hffff,memory_data,memory_even,memory_odd);
igor_neural_datapath neural(clk,neural_rst_n,load_input,start,input_index,staged_data,
 output_index,output_value,busy,done,neural_fault,latency_cycles,
 effective_ready,core_address,memory_data,memory_even,memory_odd);
always @(posedge clk or negedge rst_n) begin
 if (!rst_n) begin
  host_address<=0;loaded_words<=0;staged_data<=0;staged_bytes<=0;
  loading<=0;weights_ready<=0;host_fault<=0;memory_write<=0;
  write_address<=0;write_word<=0;load_input<=0;start<=0;
  input_index<=0;output_index<=0;diagnostic_page<=0;
 end else begin
  memory_write<=0;load_input<=0;start<=0;
  if (ena && ui_in[0]) begin
   // Also block commands in the cycle before the datapath observes start.
   case (ui_in[4:1])
    0:if (!busy && !start) host_address[7:0]<=uio_in;else host_fault<=1;
    1:if (!busy && !start && uio_in[7:5]==0) host_address[12:8]<=uio_in[4:0];else host_fault<=1;
    2:if (!busy && !start && !load_input) begin staged_data[7:0]<=uio_in;staged_bytes[0]<=1;end else host_fault<=1;
    3:if (!busy && !start && !load_input) begin staged_data[15:8]<=uio_in;staged_bytes[1]<=1;end else host_fault<=1;
    4:case(uio_in)
     1:if (!busy && !start && !load_input) begin
        loading<=1;weights_ready<=0;loaded_words<=0;host_address<=0;
        staged_bytes<=0;host_fault<=0;
       end else host_fault<=1;
     2:if (loading && !busy && !start && !host_fault &&
           staged_bytes==2'b11 && host_address==loaded_words && loaded_words<6020) begin
        memory_write<=1;write_address<=host_address;write_word<=staged_data;
        loaded_words<=loaded_words+1'b1;host_address<=host_address+1'b1;staged_bytes<=0;
       end else host_fault<=1;
     3:if (loading && loaded_words==6020 && !host_fault && !busy && !start) begin
        weights_ready<=1;loading<=0;
       end else host_fault<=1;
     default:host_fault<=1;
    endcase
    5:if (!busy && !start && !load_input && uio_in<24) input_index<=uio_in[4:0];else host_fault<=1;
    6:if (!busy && !start && effective_ready && staged_bytes==2'b11) begin load_input<=1;staged_bytes<=0;end else host_fault<=1;
    7:if (!busy && !start && !load_input && effective_ready) start<=1;else host_fault<=1;
    8:if (uio_in<4) output_index<=uio_in[1:0];else host_fault<=1;
    9:if (uio_in<5) diagnostic_page<=uio_in[2:0];else host_fault<=1;
    default:host_fault<=1;
   endcase
  end
 end
end
always @(*) begin
 case(ui_in[7:5])
  0:uo_out={1'b0,loading,neural_fault,host_fault,done,busy,effective_ready,rst_n};
  1:uo_out=busy ? 8'd0 : memory_data[7:0];
  2:uo_out=busy ? 8'd0 : memory_data[15:8];
  3:uo_out=effective_ready ? output_value[7:0] : 8'd0;
  4:uo_out=effective_ready ? output_value[15:8] : 8'd0;
  5:uo_out=loaded_words[7:0];
  6:uo_out={3'd0,loaded_words[12:8]};
  7:case(diagnostic_page)
    0:uo_out=8'ha6;
    1:uo_out=latency_cycles[7:0];
    2:uo_out=latency_cycles[15:8];
    3:uo_out=latency_cycles[23:16];
    4:uo_out=latency_cycles[31:24];
    default:uo_out=0;
   endcase
 endcase
end
assign uio_out=8'd0;
assign uio_oe=8'd0;
endmodule
`default_nettype wire
