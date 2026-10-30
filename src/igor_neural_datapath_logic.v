// William Anthony / iSeeDesignITB
`timescale 1ns/1ps
`default_nettype none
// Fixed-model inference: fixed parameter logic and flip-flop activation storage.
// Registered reads preserve the two-lane MAC pipeline and inference schedule.
module igor_neural_datapath_logic(input wire clk,rst_n,load_input,start,
 input wire [4:0] input_index,input wire signed [15:0] input_value,
 input wire [1:0] output_index,output wire signed [15:0] output_value,
 output reg busy,done,fault,output reg [31:0] latency_cycles,
 input wire weights_ready,output reg [12:0] address,
 input wire signed [15:0] weight,weight_even,weight_odd);
reg signed [15:0] outputs[0:3];
reg [23:0] loaded;
reg [2:0] state;
reg [1:0] layer;
reg [6:0] neuron,k;
reg signed [39:0] accumulator;
reg [7:0] activation_address;
reg signed [15:0] next_operand0,next_operand1;
reg signed [15:0] operand0_q,operand1_q,weight0_q,weight1_q,bias_q;
reg pipe_valid;
wire signed [31:0] product0=operand0_q*weight0_q;
wire signed [31:0] product1=operand1_q*weight1_q;
wire signed [39:0] sum=accumulator+{{8{product0[31]}},product0}
 +{{8{product1[31]}},product1};
wire signed [31:0] scaled=accumulator[39:8];
wire signed [15:0] nonlinear=scaled>32'sd256 ? 16'sd256 :
 (scaled < -32'sd256 ? -16'sd256 : scaled[15:0]);
assign output_value=done && !fault && weights_ready ? outputs[output_index] : 16'sd0;
wire [6:0] input_count=layer==0 ? 7'd24:7'd64;
wire [6:0] output_count=layer==2 ? 7'd4:7'd64;
wire last_neuron=neuron==output_count-1'b1;
wire final_neuron=layer==2 && last_neuron;
wire [1:0] next_layer=last_neuron ? layer+1'b1 : layer;
wire [6:0] next_neuron=last_neuron ? 7'd0 : neuron+1'b1;
wire [12:0] bias_base=layer==0 ? 13'd1536:(layer==1 ? 13'd5696:13'd6016);
wire [12:0] next_bias_base=next_layer==0 ? 13'd1536:(next_layer==1 ? 13'd5696:13'd6016);
wire [12:0] next_row=next_layer==0 ?
 (({6'd0,next_neuron}<<4)+({6'd0,next_neuron}<<3)) :
 ((next_layer==1 ? 13'd1600:13'd5760)+({6'd0,next_neuron}<<6));
// Logical activation map: inputs 0..23, h1 24..87, h2 88..151.
wire [7:0] next_activation_base=next_layer==0 ? 8'd0:(next_layer==1 ? 8'd24:8'd88);
wire signed [15:0] hidden_value=scaled<0 ? 16'sd0:
 (scaled>32767 ? 16'sd32767:scaled[15:0]);
wire host_activation_write=load_input && !busy && input_index<24;
wire result_activation_write=busy && state==6 && layer!=2;
wire activation_write=host_activation_write || result_activation_write;
wire [7:0] activation_memory_address=host_activation_write ? {3'd0,input_index}:
 (result_activation_write ? (layer==0 ? 8'd24:8'd88)+{1'b0,neuron} : activation_address);
wire signed [15:0] activation_even,activation_odd;
// The output-store edge replaces a read. Pair 0 and pair 1 have already been
// prefetched, so both output registers hold pair 1 during this edge.
igor_activation_logic activation_store(clk,rst_n,
 activation_write || (busy && state!=6),activation_write,
 activation_memory_address,host_activation_write ? input_value:hidden_value,
 activation_even,activation_odd);
always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin
  loaded<=0;state<=0;layer<=0;neuron<=0;k<=0;accumulator<=0;
  activation_address<=0;next_operand0<=0;next_operand1<=0;
  operand0_q<=0;operand1_q<=0;weight0_q<=0;weight1_q<=0;
  bias_q<=0;pipe_valid<=0;address<=0;
  busy<=0;done<=0;fault<=0;latency_cycles<=0;
 end else begin
  if(load_input)begin
   if(busy || input_index>=24)fault<=1;
   else begin loaded[input_index]<=1;done<=0;end
  end
  if(busy)latency_cycles<=latency_cycles+1'b1;
  case(state)
   0:if(start)begin
    if(loaded==24'hffffff && weights_ready && !fault && !load_input)begin
     busy<=1;done<=0;latency_cycles<=0;layer<=0;neuron<=0;state<=1;
    end else fault<=1;
   end
   1:begin address<=bias_base+{6'd0,neuron};pipe_valid<=0;state<=2;end
   2:begin
    address<=0;activation_address<=0;k<=0;state<=3;
   end
   3:begin
    accumulator<={{16{weight[15]}},weight,8'd0};
    address<=2;activation_address<=2;state<=4;
   end
   4:begin
    weight0_q<=weight_even;weight1_q<=weight_odd;
    operand0_q<=activation_even;operand1_q<=activation_odd;pipe_valid<=1;
    if(pipe_valid)accumulator<=sum;
    if(k==input_count-2)begin
     // Prefetch the next row while the last pair and bias finish.
     if(!final_neuron)begin
      address<=next_row;activation_address<=next_activation_base+2;
     end
     state<=5;
    end else begin
     k<=k+2;
     if(k==input_count-4)begin
      if(!final_neuron)begin
       address<=next_bias_base+{6'd0,next_neuron};activation_address<=next_activation_base;
      end
     end else begin
      address<=address+2;activation_address<=activation_address+2;
     end
    end
   end
   5:begin
    accumulator<=sum;
    if(!final_neuron)begin
     bias_q<=weight;next_operand0<=activation_even;next_operand1<=activation_odd;
     address<=next_row+2;activation_address<=next_activation_base+4;
    end
    state<=6;
   end
   6:begin
    if(layer==2)outputs[neuron[1:0]]<=nonlinear;
    if(layer!=2 && scaled>32767)fault<=1;
    if(final_neuron)begin busy<=0;done<=1;state<=0;loaded<=0;end
    else begin
     layer<=next_layer;neuron<=next_neuron;k<=2;
     accumulator<={{16{bias_q[15]}},bias_q,8'd0};pipe_valid<=1;
     weight0_q<=weight_even;weight1_q<=weight_odd;
     operand0_q<=next_operand0;operand1_q<=next_operand1;
     address<=next_row+4;
     state<=4;
    end
   end
   default:begin busy<=0;done<=0;fault<=1;state<=0;end
  endcase
  if(start && busy)fault<=1;
 end
end
endmodule
`default_nettype wire
