// Synthesizable quantized deployment of src/garda_navigation's 74-128-64-3 PPO.
// Quantized integer equivalence is tested separately from FP32 approximation.
`timescale 1ns/1ps
`default_nettype none

module garda_src_policy_activation(
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

module garda_src_policy_core #(
    parameter ROM_FILE = "rtl/garda_src_policy/policy_weights.mem"
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
    wire signed [15:0] hidden1 [0:127];
    wire signed [15:0] hidden2 [0:63];
    reg signed [15:0] actions [0:2];
    wire signed [39:0] accumulator [0:15];
    reg signed [15:0] operand;
    reg [10:0] address, weight_address;
    wire [7:0] input_count = layer==0 ? 8'd74 : (layer==1 ? 8'd128 : 8'd64);
    // neuron is the base index of an sixteen-neuron group.
    wire [7:0] output_count = layer==0 ? 8'd128 : (layer==1 ? 8'd64 : 8'd3);
    wire [10:0] bias_base = layer==0 ? 11'd592 : (layer==1 ? 11'd1112 : 11'd1180);
    wire signed [15:0] weight [0:15];
    wire signed [31:0] product [0:15];
    wire signed [39:0] mac_sum [0:15];
    wire signed [15:0] activated [0:15];
    wire [15:0] activation_saturated;
    generate
    begin: lane0
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 0 < 3;
        assign accumulator[0] = acc;
        assign hidden1[0*16+0]=h1[0];
        assign hidden1[1*16+0]=h1[1];
        assign hidden1[2*16+0]=h1[2];
        assign hidden1[3*16+0]=h1[3];
        assign hidden1[4*16+0]=h1[4];
        assign hidden1[5*16+0]=h1[5];
        assign hidden1[6*16+0]=h1[6];
        assign hidden1[7*16+0]=h1[7];
        assign hidden2[0*16+0]=h2[0];
        assign hidden2[1*16+0]=h2[1];
        assign hidden2[2*16+0]=h2[2];
        assign hidden2[3*16+0]=h2[3];
        initial $readmemh("bank0.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[0];
                if(layer==1) h2[neuron[5:4]] <= activated[0];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[0][15]}},weight[0],8'd0};
                else if(state==MAC) acc<=mac_sum[0];
            end
        end
        assign weight[0] = data;
        assign product[0] = active ? operand * weight[0] : 32'sd0;
        assign mac_sum[0] = accumulator[0] + {{8{product[0][31]}},product[0]};
        garda_src_policy_activation activation(accumulator[0],layer==2,
                                               activated[0],activation_saturated[0]);
    end
    begin: lane1
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 1 < 3;
        assign accumulator[1] = acc;
        assign hidden1[0*16+1]=h1[0];
        assign hidden1[1*16+1]=h1[1];
        assign hidden1[2*16+1]=h1[2];
        assign hidden1[3*16+1]=h1[3];
        assign hidden1[4*16+1]=h1[4];
        assign hidden1[5*16+1]=h1[5];
        assign hidden1[6*16+1]=h1[6];
        assign hidden1[7*16+1]=h1[7];
        assign hidden2[0*16+1]=h2[0];
        assign hidden2[1*16+1]=h2[1];
        assign hidden2[2*16+1]=h2[2];
        assign hidden2[3*16+1]=h2[3];
        initial $readmemh("bank1.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[1];
                if(layer==1) h2[neuron[5:4]] <= activated[1];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[1][15]}},weight[1],8'd0};
                else if(state==MAC) acc<=mac_sum[1];
            end
        end
        assign weight[1] = data;
        assign product[1] = active ? operand * weight[1] : 32'sd0;
        assign mac_sum[1] = accumulator[1] + {{8{product[1][31]}},product[1]};
        garda_src_policy_activation activation(accumulator[1],layer==2,
                                               activated[1],activation_saturated[1]);
    end
    begin: lane2
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 2 < 3;
        assign accumulator[2] = acc;
        assign hidden1[0*16+2]=h1[0];
        assign hidden1[1*16+2]=h1[1];
        assign hidden1[2*16+2]=h1[2];
        assign hidden1[3*16+2]=h1[3];
        assign hidden1[4*16+2]=h1[4];
        assign hidden1[5*16+2]=h1[5];
        assign hidden1[6*16+2]=h1[6];
        assign hidden1[7*16+2]=h1[7];
        assign hidden2[0*16+2]=h2[0];
        assign hidden2[1*16+2]=h2[1];
        assign hidden2[2*16+2]=h2[2];
        assign hidden2[3*16+2]=h2[3];
        initial $readmemh("bank2.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[2];
                if(layer==1) h2[neuron[5:4]] <= activated[2];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[2][15]}},weight[2],8'd0};
                else if(state==MAC) acc<=mac_sum[2];
            end
        end
        assign weight[2] = data;
        assign product[2] = active ? operand * weight[2] : 32'sd0;
        assign mac_sum[2] = accumulator[2] + {{8{product[2][31]}},product[2]};
        garda_src_policy_activation activation(accumulator[2],layer==2,
                                               activated[2],activation_saturated[2]);
    end
    begin: lane3
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 3 < 3;
        assign accumulator[3] = acc;
        assign hidden1[0*16+3]=h1[0];
        assign hidden1[1*16+3]=h1[1];
        assign hidden1[2*16+3]=h1[2];
        assign hidden1[3*16+3]=h1[3];
        assign hidden1[4*16+3]=h1[4];
        assign hidden1[5*16+3]=h1[5];
        assign hidden1[6*16+3]=h1[6];
        assign hidden1[7*16+3]=h1[7];
        assign hidden2[0*16+3]=h2[0];
        assign hidden2[1*16+3]=h2[1];
        assign hidden2[2*16+3]=h2[2];
        assign hidden2[3*16+3]=h2[3];
        initial $readmemh("bank3.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[3];
                if(layer==1) h2[neuron[5:4]] <= activated[3];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[3][15]}},weight[3],8'd0};
                else if(state==MAC) acc<=mac_sum[3];
            end
        end
        assign weight[3] = data;
        assign product[3] = active ? operand * weight[3] : 32'sd0;
        assign mac_sum[3] = accumulator[3] + {{8{product[3][31]}},product[3]};
        garda_src_policy_activation activation(accumulator[3],layer==2,
                                               activated[3],activation_saturated[3]);
    end
    begin: lane4
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 4 < 3;
        assign accumulator[4] = acc;
        assign hidden1[0*16+4]=h1[0];
        assign hidden1[1*16+4]=h1[1];
        assign hidden1[2*16+4]=h1[2];
        assign hidden1[3*16+4]=h1[3];
        assign hidden1[4*16+4]=h1[4];
        assign hidden1[5*16+4]=h1[5];
        assign hidden1[6*16+4]=h1[6];
        assign hidden1[7*16+4]=h1[7];
        assign hidden2[0*16+4]=h2[0];
        assign hidden2[1*16+4]=h2[1];
        assign hidden2[2*16+4]=h2[2];
        assign hidden2[3*16+4]=h2[3];
        initial $readmemh("bank4.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[4];
                if(layer==1) h2[neuron[5:4]] <= activated[4];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[4][15]}},weight[4],8'd0};
                else if(state==MAC) acc<=mac_sum[4];
            end
        end
        assign weight[4] = data;
        assign product[4] = active ? operand * weight[4] : 32'sd0;
        assign mac_sum[4] = accumulator[4] + {{8{product[4][31]}},product[4]};
        garda_src_policy_activation activation(accumulator[4],layer==2,
                                               activated[4],activation_saturated[4]);
    end
    begin: lane5
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 5 < 3;
        assign accumulator[5] = acc;
        assign hidden1[0*16+5]=h1[0];
        assign hidden1[1*16+5]=h1[1];
        assign hidden1[2*16+5]=h1[2];
        assign hidden1[3*16+5]=h1[3];
        assign hidden1[4*16+5]=h1[4];
        assign hidden1[5*16+5]=h1[5];
        assign hidden1[6*16+5]=h1[6];
        assign hidden1[7*16+5]=h1[7];
        assign hidden2[0*16+5]=h2[0];
        assign hidden2[1*16+5]=h2[1];
        assign hidden2[2*16+5]=h2[2];
        assign hidden2[3*16+5]=h2[3];
        initial $readmemh("bank5.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[5];
                if(layer==1) h2[neuron[5:4]] <= activated[5];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[5][15]}},weight[5],8'd0};
                else if(state==MAC) acc<=mac_sum[5];
            end
        end
        assign weight[5] = data;
        assign product[5] = active ? operand * weight[5] : 32'sd0;
        assign mac_sum[5] = accumulator[5] + {{8{product[5][31]}},product[5]};
        garda_src_policy_activation activation(accumulator[5],layer==2,
                                               activated[5],activation_saturated[5]);
    end
    begin: lane6
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 6 < 3;
        assign accumulator[6] = acc;
        assign hidden1[0*16+6]=h1[0];
        assign hidden1[1*16+6]=h1[1];
        assign hidden1[2*16+6]=h1[2];
        assign hidden1[3*16+6]=h1[3];
        assign hidden1[4*16+6]=h1[4];
        assign hidden1[5*16+6]=h1[5];
        assign hidden1[6*16+6]=h1[6];
        assign hidden1[7*16+6]=h1[7];
        assign hidden2[0*16+6]=h2[0];
        assign hidden2[1*16+6]=h2[1];
        assign hidden2[2*16+6]=h2[2];
        assign hidden2[3*16+6]=h2[3];
        initial $readmemh("bank6.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[6];
                if(layer==1) h2[neuron[5:4]] <= activated[6];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[6][15]}},weight[6],8'd0};
                else if(state==MAC) acc<=mac_sum[6];
            end
        end
        assign weight[6] = data;
        assign product[6] = active ? operand * weight[6] : 32'sd0;
        assign mac_sum[6] = accumulator[6] + {{8{product[6][31]}},product[6]};
        garda_src_policy_activation activation(accumulator[6],layer==2,
                                               activated[6],activation_saturated[6]);
    end
    begin: lane7
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 7 < 3;
        assign accumulator[7] = acc;
        assign hidden1[0*16+7]=h1[0];
        assign hidden1[1*16+7]=h1[1];
        assign hidden1[2*16+7]=h1[2];
        assign hidden1[3*16+7]=h1[3];
        assign hidden1[4*16+7]=h1[4];
        assign hidden1[5*16+7]=h1[5];
        assign hidden1[6*16+7]=h1[6];
        assign hidden1[7*16+7]=h1[7];
        assign hidden2[0*16+7]=h2[0];
        assign hidden2[1*16+7]=h2[1];
        assign hidden2[2*16+7]=h2[2];
        assign hidden2[3*16+7]=h2[3];
        initial $readmemh("bank7.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[7];
                if(layer==1) h2[neuron[5:4]] <= activated[7];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[7][15]}},weight[7],8'd0};
                else if(state==MAC) acc<=mac_sum[7];
            end
        end
        assign weight[7] = data;
        assign product[7] = active ? operand * weight[7] : 32'sd0;
        assign mac_sum[7] = accumulator[7] + {{8{product[7][31]}},product[7]};
        garda_src_policy_activation activation(accumulator[7],layer==2,
                                               activated[7],activation_saturated[7]);
    end
    begin: lane8
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 8 < 3;
        assign accumulator[8] = acc;
        assign hidden1[0*16+8]=h1[0];
        assign hidden1[1*16+8]=h1[1];
        assign hidden1[2*16+8]=h1[2];
        assign hidden1[3*16+8]=h1[3];
        assign hidden1[4*16+8]=h1[4];
        assign hidden1[5*16+8]=h1[5];
        assign hidden1[6*16+8]=h1[6];
        assign hidden1[7*16+8]=h1[7];
        assign hidden2[0*16+8]=h2[0];
        assign hidden2[1*16+8]=h2[1];
        assign hidden2[2*16+8]=h2[2];
        assign hidden2[3*16+8]=h2[3];
        initial $readmemh("bank8.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[8];
                if(layer==1) h2[neuron[5:4]] <= activated[8];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[8][15]}},weight[8],8'd0};
                else if(state==MAC) acc<=mac_sum[8];
            end
        end
        assign weight[8] = data;
        assign product[8] = active ? operand * weight[8] : 32'sd0;
        assign mac_sum[8] = accumulator[8] + {{8{product[8][31]}},product[8]};
        garda_src_policy_activation activation(accumulator[8],layer==2,
                                               activated[8],activation_saturated[8]);
    end
    begin: lane9
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 9 < 3;
        assign accumulator[9] = acc;
        assign hidden1[0*16+9]=h1[0];
        assign hidden1[1*16+9]=h1[1];
        assign hidden1[2*16+9]=h1[2];
        assign hidden1[3*16+9]=h1[3];
        assign hidden1[4*16+9]=h1[4];
        assign hidden1[5*16+9]=h1[5];
        assign hidden1[6*16+9]=h1[6];
        assign hidden1[7*16+9]=h1[7];
        assign hidden2[0*16+9]=h2[0];
        assign hidden2[1*16+9]=h2[1];
        assign hidden2[2*16+9]=h2[2];
        assign hidden2[3*16+9]=h2[3];
        initial $readmemh("bank9.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[9];
                if(layer==1) h2[neuron[5:4]] <= activated[9];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[9][15]}},weight[9],8'd0};
                else if(state==MAC) acc<=mac_sum[9];
            end
        end
        assign weight[9] = data;
        assign product[9] = active ? operand * weight[9] : 32'sd0;
        assign mac_sum[9] = accumulator[9] + {{8{product[9][31]}},product[9]};
        garda_src_policy_activation activation(accumulator[9],layer==2,
                                               activated[9],activation_saturated[9]);
    end
    begin: lane10
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 10 < 3;
        assign accumulator[10] = acc;
        assign hidden1[0*16+10]=h1[0];
        assign hidden1[1*16+10]=h1[1];
        assign hidden1[2*16+10]=h1[2];
        assign hidden1[3*16+10]=h1[3];
        assign hidden1[4*16+10]=h1[4];
        assign hidden1[5*16+10]=h1[5];
        assign hidden1[6*16+10]=h1[6];
        assign hidden1[7*16+10]=h1[7];
        assign hidden2[0*16+10]=h2[0];
        assign hidden2[1*16+10]=h2[1];
        assign hidden2[2*16+10]=h2[2];
        assign hidden2[3*16+10]=h2[3];
        initial $readmemh("bank10.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[10];
                if(layer==1) h2[neuron[5:4]] <= activated[10];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[10][15]}},weight[10],8'd0};
                else if(state==MAC) acc<=mac_sum[10];
            end
        end
        assign weight[10] = data;
        assign product[10] = active ? operand * weight[10] : 32'sd0;
        assign mac_sum[10] = accumulator[10] + {{8{product[10][31]}},product[10]};
        garda_src_policy_activation activation(accumulator[10],layer==2,
                                               activated[10],activation_saturated[10]);
    end
    begin: lane11
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 11 < 3;
        assign accumulator[11] = acc;
        assign hidden1[0*16+11]=h1[0];
        assign hidden1[1*16+11]=h1[1];
        assign hidden1[2*16+11]=h1[2];
        assign hidden1[3*16+11]=h1[3];
        assign hidden1[4*16+11]=h1[4];
        assign hidden1[5*16+11]=h1[5];
        assign hidden1[6*16+11]=h1[6];
        assign hidden1[7*16+11]=h1[7];
        assign hidden2[0*16+11]=h2[0];
        assign hidden2[1*16+11]=h2[1];
        assign hidden2[2*16+11]=h2[2];
        assign hidden2[3*16+11]=h2[3];
        initial $readmemh("bank11.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[11];
                if(layer==1) h2[neuron[5:4]] <= activated[11];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[11][15]}},weight[11],8'd0};
                else if(state==MAC) acc<=mac_sum[11];
            end
        end
        assign weight[11] = data;
        assign product[11] = active ? operand * weight[11] : 32'sd0;
        assign mac_sum[11] = accumulator[11] + {{8{product[11][31]}},product[11]};
        garda_src_policy_activation activation(accumulator[11],layer==2,
                                               activated[11],activation_saturated[11]);
    end
    begin: lane12
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 12 < 3;
        assign accumulator[12] = acc;
        assign hidden1[0*16+12]=h1[0];
        assign hidden1[1*16+12]=h1[1];
        assign hidden1[2*16+12]=h1[2];
        assign hidden1[3*16+12]=h1[3];
        assign hidden1[4*16+12]=h1[4];
        assign hidden1[5*16+12]=h1[5];
        assign hidden1[6*16+12]=h1[6];
        assign hidden1[7*16+12]=h1[7];
        assign hidden2[0*16+12]=h2[0];
        assign hidden2[1*16+12]=h2[1];
        assign hidden2[2*16+12]=h2[2];
        assign hidden2[3*16+12]=h2[3];
        initial $readmemh("bank12.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[12];
                if(layer==1) h2[neuron[5:4]] <= activated[12];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[12][15]}},weight[12],8'd0};
                else if(state==MAC) acc<=mac_sum[12];
            end
        end
        assign weight[12] = data;
        assign product[12] = active ? operand * weight[12] : 32'sd0;
        assign mac_sum[12] = accumulator[12] + {{8{product[12][31]}},product[12]};
        garda_src_policy_activation activation(accumulator[12],layer==2,
                                               activated[12],activation_saturated[12]);
    end
    begin: lane13
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 13 < 3;
        assign accumulator[13] = acc;
        assign hidden1[0*16+13]=h1[0];
        assign hidden1[1*16+13]=h1[1];
        assign hidden1[2*16+13]=h1[2];
        assign hidden1[3*16+13]=h1[3];
        assign hidden1[4*16+13]=h1[4];
        assign hidden1[5*16+13]=h1[5];
        assign hidden1[6*16+13]=h1[6];
        assign hidden1[7*16+13]=h1[7];
        assign hidden2[0*16+13]=h2[0];
        assign hidden2[1*16+13]=h2[1];
        assign hidden2[2*16+13]=h2[2];
        assign hidden2[3*16+13]=h2[3];
        initial $readmemh("bank13.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[13];
                if(layer==1) h2[neuron[5:4]] <= activated[13];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[13][15]}},weight[13],8'd0};
                else if(state==MAC) acc<=mac_sum[13];
            end
        end
        assign weight[13] = data;
        assign product[13] = active ? operand * weight[13] : 32'sd0;
        assign mac_sum[13] = accumulator[13] + {{8{product[13][31]}},product[13]};
        garda_src_policy_activation activation(accumulator[13],layer==2,
                                               activated[13],activation_saturated[13]);
    end
    begin: lane14
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 14 < 3;
        assign accumulator[14] = acc;
        assign hidden1[0*16+14]=h1[0];
        assign hidden1[1*16+14]=h1[1];
        assign hidden1[2*16+14]=h1[2];
        assign hidden1[3*16+14]=h1[3];
        assign hidden1[4*16+14]=h1[4];
        assign hidden1[5*16+14]=h1[5];
        assign hidden1[6*16+14]=h1[6];
        assign hidden1[7*16+14]=h1[7];
        assign hidden2[0*16+14]=h2[0];
        assign hidden2[1*16+14]=h2[1];
        assign hidden2[2*16+14]=h2[2];
        assign hidden2[3*16+14]=h2[3];
        initial $readmemh("bank14.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[14];
                if(layer==1) h2[neuron[5:4]] <= activated[14];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[14][15]}},weight[14],8'd0};
                else if(state==MAC) acc<=mac_sum[14];
            end
        end
        assign weight[14] = data;
        assign product[14] = active ? operand * weight[14] : 32'sd0;
        assign mac_sum[14] = accumulator[14] + {{8{product[14][31]}},product[14]};
        garda_src_policy_activation activation(accumulator[14],layer==2,
                                               activated[14],activation_saturated[14]);
    end
    begin: lane15
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || 15 < 3;
        assign accumulator[15] = acc;
        assign hidden1[0*16+15]=h1[0];
        assign hidden1[1*16+15]=h1[1];
        assign hidden1[2*16+15]=h1[2];
        assign hidden1[3*16+15]=h1[3];
        assign hidden1[4*16+15]=h1[4];
        assign hidden1[5*16+15]=h1[5];
        assign hidden1[6*16+15]=h1[6];
        assign hidden1[7*16+15]=h1[7];
        assign hidden2[0*16+15]=h2[0];
        assign hidden2[1*16+15]=h2[1];
        assign hidden2[2*16+15]=h2[2];
        assign hidden2[3*16+15]=h2[3];
        initial $readmemh("bank15.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[15];
                if(layer==1) h2[neuron[5:4]] <= activated[15];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[15][15]}},weight[15],8'd0};
                else if(state==MAC) acc<=mac_sum[15];
            end
        end
        assign weight[15] = data;
        assign product[15] = active ? operand * weight[15] : 32'sd0;
        assign mac_sum[15] = accumulator[15] + {{8{product[15][31]}},product[15]};
        garda_src_policy_activation activation(accumulator[15],layer==2,
                                               activated[15],activation_saturated[15]);
    end
    endgenerate
    assign output_value = done && !fault && !abort && output_index < 3 ?
                          actions[output_index] : 16'sd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; layer<=0; neuron<=0; k<=0; loaded<=0;
             operand<=0; address<=0; weight_address<=0;
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
                BIAS_ADDRESS: begin address<=bias_base+(neuron>>4); state<=BIAS_WAIT; end
                BIAS_WAIT: state<=BIAS_TAKE;
                BIAS_TAKE: begin
                    
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
                    
                    weight_address<=weight_address+1'b1;
                    if (k==input_count-1'b1) state<=ACTIVATE;
                    else begin k<=k+1'b1; state<=WEIGHT_ADDRESS; end
                end
                ACTIVATE: begin
                    if (|activation_saturated) saturated<=1;
                    if(layer==2) begin
                        actions[0]<=activated[0];
                        actions[1]<=activated[1];
                        actions[2]<=activated[2];
                    end
                    if (neuron+16>=output_count) begin
                        if (layer==2) begin busy<=0; done<=1; state<=IDLE; end
                        else begin
                            layer<=layer+1'b1; neuron<=0; state<=BIAS_ADDRESS;
                            weight_address<=layer==0 ? 11'd600 : 11'd1116;
                        end
                    end else begin neuron<=neuron+16; state<=BIAS_ADDRESS; end
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
