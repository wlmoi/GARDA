// Synthesizable quantized deployment of src/igor_navigation's 74-128-64-3 PPO.
// Quantized integer equivalence is tested separately from FP32 approximation.
`timescale 1ns/1ps
`default_nettype none

module igor_src_policy_activation(
    input wire signed [39:0] accumulator,
    input wire output_layer,
    output wire signed [15:0] value,
    output wire saturated
);
    // Arithmetic floor division by 256, not truncation towards zero.
    wire signed [31:0] scaled = accumulator[39:8];
    assign saturated = !output_layer && (scaled > 32'sd32767);
    assign value = output_layer ?
        (scaled > 32'sd256 ? 16'sd256 :
        (scaled < -32'sd256 ? -16'sd256 : scaled[15:0])) :
        (scaled < 0 ? 16'sd0 :
        (scaled > 32'sd32767 ? 16'sd32767 : scaled[15:0]));
endmodule

module igor_src_policy_core #(
    parameter ROM_FILE = "rtl/igor_src_policy/policy_weights.mem"
)(
    input wire clk, rst_n,
    input wire load_input,
    input wire [6:0] input_index,
    input wire signed [15:0] input_value,
    input wire start, abort,
    input wire [1:0] output_index,
    output wire signed [15:0] output_value,
    output reg busy, done, fault,
    output reg [3:0] error_code,
    output reg [31:0] latency_cycles,
    output reg saturated
);
    localparam IDLE=4'd0, BIAS_ADDRESS=4'd1, BIAS_WAIT=4'd2,
               BIAS_TAKE=4'd3, WEIGHT_ADDRESS=4'd4, WEIGHT_WAIT=4'd5,
               MAC=4'd6, ACTIVATE=4'd7;
    reg [3:0] state;
    reg [1:0] layer;
    reg [7:0] neuron, k;
    reg [73:0] loaded;
    reg signed [15:0] observations [0:73];
    reg signed [15:0] hidden1 [0:127];
    reg signed [15:0] hidden2 [0:63];
    reg signed [15:0] actions [0:2];
    reg signed [39:0] accumulator;
    reg signed [15:0] operand;
    reg [14:0] address, weight_address;
    wire signed [15:0] weight;
    wire signed [31:0] product = operand * weight;
    wire signed [39:0] mac_sum = accumulator + {{8{product[31]}}, product};
    wire [7:0] input_count = layer==0 ? 8'd74 : (layer==1 ? 8'd128 : 8'd64);
    wire [7:0] output_count = layer==0 ? 8'd128 : (layer==1 ? 8'd64 : 8'd3);
    wire [14:0] bias_base = layer==0 ? 15'd9472 :
                                 (layer==1 ? 15'd17792 : 15'd18048);
    wire signed [15:0] activated;
    wire activation_saturated;
    igor_src_policy_rom #(.FILE(ROM_FILE)) weights(clk,address,weight);
    igor_src_policy_activation activation(accumulator,layer==2,activated,activation_saturated);
    assign output_value = done && !fault && !abort && output_index < 3 ?
                          actions[output_index] : 16'sd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; layer<=0; neuron<=0; k<=0; loaded<=0;
            accumulator<=0; operand<=0; address<=0; weight_address<=0;
            busy<=0; done<=0; fault<=0; error_code<=0; latency_cycles<=0;
            saturated<=0; actions[0]<=0; actions[1]<=0; actions[2]<=0;
        end else if (abort) begin
            // Cancellation never leaves a partially loaded or completed command.
            state<=IDLE; loaded<=0; busy<=0; done<=0;
            actions[0]<=0; actions[1]<=0; actions[2]<=0;
        end else if (fault) begin
            state<=IDLE; loaded<=0; busy<=0; done<=0;
        end else if ((load_input && (busy || input_index>=74)) ||
                     (start && (busy || load_input || loaded!={74{1'b1}}))) begin
            // 1=index, 2=write-while-running, 3=start-while-running,
            // 4=incomplete frame, 5=ambiguous simultaneous load/start.
            fault<=1; done<=0; busy<=0; state<=IDLE; loaded<=0;
            if (load_input && input_index>=74) error_code<=1;
            else if (load_input && busy) error_code<=2;
            else if (start && busy) error_code<=3;
            else if (start && load_input) error_code<=5;
            else error_code<=4;
        end else begin
            if (load_input) begin
                observations[input_index]<=input_value;
                loaded[input_index]<=1'b1;
                done<=0;
            end
            if (busy) latency_cycles<=latency_cycles+1'b1;
            case (state)
                IDLE: if (start) begin
                    busy<=1; done<=0; loaded<=0; latency_cycles<=0;
                    layer<=0; neuron<=0; weight_address<=0;
                    saturated<=0; state<=BIAS_ADDRESS;
                end
                BIAS_ADDRESS: begin address<=bias_base+neuron; state<=BIAS_WAIT; end
                BIAS_WAIT: state<=BIAS_TAKE;
                BIAS_TAKE: begin
                    accumulator<={{16{weight[15]}},weight,8'd0};
                    k<=0; state<=WEIGHT_ADDRESS;
                end
                WEIGHT_ADDRESS: begin
                    address<=weight_address;
                    operand<=layer==0 ? observations[k] :
                             (layer==1 ? hidden1[k] : hidden2[k]);
                    state<=WEIGHT_WAIT;
                end
                WEIGHT_WAIT: state<=MAC;
                MAC: begin
                    accumulator<=mac_sum;
                    weight_address<=weight_address+1'b1;
                    if (k==input_count-1'b1) state<=ACTIVATE;
                    else begin k<=k+1'b1; state<=WEIGHT_ADDRESS; end
                end
                ACTIVATE: begin
                    if (activation_saturated) saturated<=1;
                    if (layer==0) hidden1[neuron]<=activated;
                    else if (layer==1) hidden2[neuron]<=activated;
                    else actions[neuron]<=activated;
                    if (neuron==output_count-1'b1) begin
                        if (layer==2) begin busy<=0; done<=1; state<=IDLE; end
                        else begin
                            layer<=layer+1'b1; neuron<=0; state<=BIAS_ADDRESS;
                            weight_address<=layer==0 ? 15'd9600 : 15'd17856;
                        end
                    end else begin neuron<=neuron+1'b1; state<=BIAS_ADDRESS; end
                end
                default: begin
                    state<=IDLE; busy<=0; done<=0; loaded<=0;
                    fault<=1; error_code<=6;
                end
            endcase
        end
    end
endmodule
`default_nettype wire
