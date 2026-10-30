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
    wire signed [15:0] hidden1 [0:127];
    wire signed [15:0] hidden2 [0:63];
    reg signed [15:0] actions [0:2];
    wire signed [39:0] accumulator [0:7];
    reg signed [15:0] operand;
    reg [11:0] address, weight_address;
    wire [7:0] input_count = layer==0 ? 8'd74 : (layer==1 ? 8'd128 : 8'd64);
    // neuron is the base index of an eight-neuron group.
    wire [7:0] output_count = layer==0 ? 8'd128 : (layer==1 ? 8'd64 : 8'd3);
    wire [11:0] bias_base = layer==0 ? 12'd1184 : (layer==1 ? 12'd2224 : 12'd2296);
    wire signed [15:0] weight [0:7];
    wire signed [31:0] product [0:7];
    wire signed [39:0] mac_sum [0:7];
    wire signed [15:0] activated [0:7];
    wire [7:0] activation_saturated;
    generate
    begin: lane0
        localparam BANK_FILE = 0==0 ? "bank0.mem" : 0==1 ? "bank1.mem" :
          0==2 ? "bank2.mem" : 0==3 ? "bank3.mem" : 0==4 ? "bank4.mem" :
          0==5 ? "bank5.mem" : 0==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[0]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[0][15]}},weight[0],8'd0};
                else if(state==MAC) acc<=mac_sum[0];
            end
        end
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        assign hidden1[0*8+0]=h1[0];
        assign hidden1[1*8+0]=h1[1];
        assign hidden1[2*8+0]=h1[2];
        assign hidden1[3*8+0]=h1[3];
        assign hidden1[4*8+0]=h1[4];
        assign hidden1[5*8+0]=h1[5];
        assign hidden1[6*8+0]=h1[6];
        assign hidden1[7*8+0]=h1[7];
        assign hidden1[8*8+0]=h1[8];
        assign hidden1[9*8+0]=h1[9];
        assign hidden1[10*8+0]=h1[10];
        assign hidden1[11*8+0]=h1[11];
        assign hidden1[12*8+0]=h1[12];
        assign hidden1[13*8+0]=h1[13];
        assign hidden1[14*8+0]=h1[14];
        assign hidden1[15*8+0]=h1[15];
        assign hidden2[0*8+0]=h2[0];
        assign hidden2[1*8+0]=h2[1];
        assign hidden2[2*8+0]=h2[2];
        assign hidden2[3*8+0]=h2[3];
        assign hidden2[4*8+0]=h2[4];
        assign hidden2[5*8+0]=h2[5];
        assign hidden2[6*8+0]=h2[6];
        assign hidden2[7*8+0]=h2[7];
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[0];
                if(layer==1) h2[neuron[5:3]]<=activated[0];
            end
        end
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[0] = data;
        assign product[0] = operand * weight[0];
        assign mac_sum[0] = accumulator[0] + {{8{product[0][31]}},product[0]};
        igor_src_policy_activation activation(accumulator[0],layer==2,
                                               activated[0],activation_saturated[0]);
    end
    begin: lane1
        localparam BANK_FILE = 1==0 ? "bank0.mem" : 1==1 ? "bank1.mem" :
          1==2 ? "bank2.mem" : 1==3 ? "bank3.mem" : 1==4 ? "bank4.mem" :
          1==5 ? "bank5.mem" : 1==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[1]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[1][15]}},weight[1],8'd0};
                else if(state==MAC) acc<=mac_sum[1];
            end
        end
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        assign hidden1[0*8+1]=h1[0];
        assign hidden1[1*8+1]=h1[1];
        assign hidden1[2*8+1]=h1[2];
        assign hidden1[3*8+1]=h1[3];
        assign hidden1[4*8+1]=h1[4];
        assign hidden1[5*8+1]=h1[5];
        assign hidden1[6*8+1]=h1[6];
        assign hidden1[7*8+1]=h1[7];
        assign hidden1[8*8+1]=h1[8];
        assign hidden1[9*8+1]=h1[9];
        assign hidden1[10*8+1]=h1[10];
        assign hidden1[11*8+1]=h1[11];
        assign hidden1[12*8+1]=h1[12];
        assign hidden1[13*8+1]=h1[13];
        assign hidden1[14*8+1]=h1[14];
        assign hidden1[15*8+1]=h1[15];
        assign hidden2[0*8+1]=h2[0];
        assign hidden2[1*8+1]=h2[1];
        assign hidden2[2*8+1]=h2[2];
        assign hidden2[3*8+1]=h2[3];
        assign hidden2[4*8+1]=h2[4];
        assign hidden2[5*8+1]=h2[5];
        assign hidden2[6*8+1]=h2[6];
        assign hidden2[7*8+1]=h2[7];
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[1];
                if(layer==1) h2[neuron[5:3]]<=activated[1];
            end
        end
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[1] = data;
        assign product[1] = operand * weight[1];
        assign mac_sum[1] = accumulator[1] + {{8{product[1][31]}},product[1]};
        igor_src_policy_activation activation(accumulator[1],layer==2,
                                               activated[1],activation_saturated[1]);
    end
    begin: lane2
        localparam BANK_FILE = 2==0 ? "bank0.mem" : 2==1 ? "bank1.mem" :
          2==2 ? "bank2.mem" : 2==3 ? "bank3.mem" : 2==4 ? "bank4.mem" :
          2==5 ? "bank5.mem" : 2==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[2]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[2][15]}},weight[2],8'd0};
                else if(state==MAC) acc<=mac_sum[2];
            end
        end
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        assign hidden1[0*8+2]=h1[0];
        assign hidden1[1*8+2]=h1[1];
        assign hidden1[2*8+2]=h1[2];
        assign hidden1[3*8+2]=h1[3];
        assign hidden1[4*8+2]=h1[4];
        assign hidden1[5*8+2]=h1[5];
        assign hidden1[6*8+2]=h1[6];
        assign hidden1[7*8+2]=h1[7];
        assign hidden1[8*8+2]=h1[8];
        assign hidden1[9*8+2]=h1[9];
        assign hidden1[10*8+2]=h1[10];
        assign hidden1[11*8+2]=h1[11];
        assign hidden1[12*8+2]=h1[12];
        assign hidden1[13*8+2]=h1[13];
        assign hidden1[14*8+2]=h1[14];
        assign hidden1[15*8+2]=h1[15];
        assign hidden2[0*8+2]=h2[0];
        assign hidden2[1*8+2]=h2[1];
        assign hidden2[2*8+2]=h2[2];
        assign hidden2[3*8+2]=h2[3];
        assign hidden2[4*8+2]=h2[4];
        assign hidden2[5*8+2]=h2[5];
        assign hidden2[6*8+2]=h2[6];
        assign hidden2[7*8+2]=h2[7];
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[2];
                if(layer==1) h2[neuron[5:3]]<=activated[2];
            end
        end
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[2] = data;
        assign product[2] = operand * weight[2];
        assign mac_sum[2] = accumulator[2] + {{8{product[2][31]}},product[2]};
        igor_src_policy_activation activation(accumulator[2],layer==2,
                                               activated[2],activation_saturated[2]);
    end
    begin: lane3
        localparam BANK_FILE = 3==0 ? "bank0.mem" : 3==1 ? "bank1.mem" :
          3==2 ? "bank2.mem" : 3==3 ? "bank3.mem" : 3==4 ? "bank4.mem" :
          3==5 ? "bank5.mem" : 3==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[3]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[3][15]}},weight[3],8'd0};
                else if(state==MAC) acc<=mac_sum[3];
            end
        end
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        assign hidden1[0*8+3]=h1[0];
        assign hidden1[1*8+3]=h1[1];
        assign hidden1[2*8+3]=h1[2];
        assign hidden1[3*8+3]=h1[3];
        assign hidden1[4*8+3]=h1[4];
        assign hidden1[5*8+3]=h1[5];
        assign hidden1[6*8+3]=h1[6];
        assign hidden1[7*8+3]=h1[7];
        assign hidden1[8*8+3]=h1[8];
        assign hidden1[9*8+3]=h1[9];
        assign hidden1[10*8+3]=h1[10];
        assign hidden1[11*8+3]=h1[11];
        assign hidden1[12*8+3]=h1[12];
        assign hidden1[13*8+3]=h1[13];
        assign hidden1[14*8+3]=h1[14];
        assign hidden1[15*8+3]=h1[15];
        assign hidden2[0*8+3]=h2[0];
        assign hidden2[1*8+3]=h2[1];
        assign hidden2[2*8+3]=h2[2];
        assign hidden2[3*8+3]=h2[3];
        assign hidden2[4*8+3]=h2[4];
        assign hidden2[5*8+3]=h2[5];
        assign hidden2[6*8+3]=h2[6];
        assign hidden2[7*8+3]=h2[7];
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[3];
                if(layer==1) h2[neuron[5:3]]<=activated[3];
            end
        end
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[3] = data;
        assign product[3] = operand * weight[3];
        assign mac_sum[3] = accumulator[3] + {{8{product[3][31]}},product[3]};
        igor_src_policy_activation activation(accumulator[3],layer==2,
                                               activated[3],activation_saturated[3]);
    end
    begin: lane4
        localparam BANK_FILE = 4==0 ? "bank0.mem" : 4==1 ? "bank1.mem" :
          4==2 ? "bank2.mem" : 4==3 ? "bank3.mem" : 4==4 ? "bank4.mem" :
          4==5 ? "bank5.mem" : 4==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[4]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[4][15]}},weight[4],8'd0};
                else if(state==MAC) acc<=mac_sum[4];
            end
        end
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        assign hidden1[0*8+4]=h1[0];
        assign hidden1[1*8+4]=h1[1];
        assign hidden1[2*8+4]=h1[2];
        assign hidden1[3*8+4]=h1[3];
        assign hidden1[4*8+4]=h1[4];
        assign hidden1[5*8+4]=h1[5];
        assign hidden1[6*8+4]=h1[6];
        assign hidden1[7*8+4]=h1[7];
        assign hidden1[8*8+4]=h1[8];
        assign hidden1[9*8+4]=h1[9];
        assign hidden1[10*8+4]=h1[10];
        assign hidden1[11*8+4]=h1[11];
        assign hidden1[12*8+4]=h1[12];
        assign hidden1[13*8+4]=h1[13];
        assign hidden1[14*8+4]=h1[14];
        assign hidden1[15*8+4]=h1[15];
        assign hidden2[0*8+4]=h2[0];
        assign hidden2[1*8+4]=h2[1];
        assign hidden2[2*8+4]=h2[2];
        assign hidden2[3*8+4]=h2[3];
        assign hidden2[4*8+4]=h2[4];
        assign hidden2[5*8+4]=h2[5];
        assign hidden2[6*8+4]=h2[6];
        assign hidden2[7*8+4]=h2[7];
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[4];
                if(layer==1) h2[neuron[5:3]]<=activated[4];
            end
        end
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[4] = data;
        assign product[4] = operand * weight[4];
        assign mac_sum[4] = accumulator[4] + {{8{product[4][31]}},product[4]};
        igor_src_policy_activation activation(accumulator[4],layer==2,
                                               activated[4],activation_saturated[4]);
    end
    begin: lane5
        localparam BANK_FILE = 5==0 ? "bank0.mem" : 5==1 ? "bank1.mem" :
          5==2 ? "bank2.mem" : 5==3 ? "bank3.mem" : 5==4 ? "bank4.mem" :
          5==5 ? "bank5.mem" : 5==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[5]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[5][15]}},weight[5],8'd0};
                else if(state==MAC) acc<=mac_sum[5];
            end
        end
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        assign hidden1[0*8+5]=h1[0];
        assign hidden1[1*8+5]=h1[1];
        assign hidden1[2*8+5]=h1[2];
        assign hidden1[3*8+5]=h1[3];
        assign hidden1[4*8+5]=h1[4];
        assign hidden1[5*8+5]=h1[5];
        assign hidden1[6*8+5]=h1[6];
        assign hidden1[7*8+5]=h1[7];
        assign hidden1[8*8+5]=h1[8];
        assign hidden1[9*8+5]=h1[9];
        assign hidden1[10*8+5]=h1[10];
        assign hidden1[11*8+5]=h1[11];
        assign hidden1[12*8+5]=h1[12];
        assign hidden1[13*8+5]=h1[13];
        assign hidden1[14*8+5]=h1[14];
        assign hidden1[15*8+5]=h1[15];
        assign hidden2[0*8+5]=h2[0];
        assign hidden2[1*8+5]=h2[1];
        assign hidden2[2*8+5]=h2[2];
        assign hidden2[3*8+5]=h2[3];
        assign hidden2[4*8+5]=h2[4];
        assign hidden2[5*8+5]=h2[5];
        assign hidden2[6*8+5]=h2[6];
        assign hidden2[7*8+5]=h2[7];
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[5];
                if(layer==1) h2[neuron[5:3]]<=activated[5];
            end
        end
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[5] = data;
        assign product[5] = operand * weight[5];
        assign mac_sum[5] = accumulator[5] + {{8{product[5][31]}},product[5]};
        igor_src_policy_activation activation(accumulator[5],layer==2,
                                               activated[5],activation_saturated[5]);
    end
    begin: lane6
        localparam BANK_FILE = 6==0 ? "bank0.mem" : 6==1 ? "bank1.mem" :
          6==2 ? "bank2.mem" : 6==3 ? "bank3.mem" : 6==4 ? "bank4.mem" :
          6==5 ? "bank5.mem" : 6==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[6]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[6][15]}},weight[6],8'd0};
                else if(state==MAC) acc<=mac_sum[6];
            end
        end
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        assign hidden1[0*8+6]=h1[0];
        assign hidden1[1*8+6]=h1[1];
        assign hidden1[2*8+6]=h1[2];
        assign hidden1[3*8+6]=h1[3];
        assign hidden1[4*8+6]=h1[4];
        assign hidden1[5*8+6]=h1[5];
        assign hidden1[6*8+6]=h1[6];
        assign hidden1[7*8+6]=h1[7];
        assign hidden1[8*8+6]=h1[8];
        assign hidden1[9*8+6]=h1[9];
        assign hidden1[10*8+6]=h1[10];
        assign hidden1[11*8+6]=h1[11];
        assign hidden1[12*8+6]=h1[12];
        assign hidden1[13*8+6]=h1[13];
        assign hidden1[14*8+6]=h1[14];
        assign hidden1[15*8+6]=h1[15];
        assign hidden2[0*8+6]=h2[0];
        assign hidden2[1*8+6]=h2[1];
        assign hidden2[2*8+6]=h2[2];
        assign hidden2[3*8+6]=h2[3];
        assign hidden2[4*8+6]=h2[4];
        assign hidden2[5*8+6]=h2[5];
        assign hidden2[6*8+6]=h2[6];
        assign hidden2[7*8+6]=h2[7];
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[6];
                if(layer==1) h2[neuron[5:3]]<=activated[6];
            end
        end
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[6] = data;
        assign product[6] = operand * weight[6];
        assign mac_sum[6] = accumulator[6] + {{8{product[6][31]}},product[6]};
        igor_src_policy_activation activation(accumulator[6],layer==2,
                                               activated[6],activation_saturated[6]);
    end
    begin: lane7
        localparam BANK_FILE = 7==0 ? "bank0.mem" : 7==1 ? "bank1.mem" :
          7==2 ? "bank2.mem" : 7==3 ? "bank3.mem" : 7==4 ? "bank4.mem" :
          7==5 ? "bank5.mem" : 7==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[7]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[7][15]}},weight[7],8'd0};
                else if(state==MAC) acc<=mac_sum[7];
            end
        end
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        assign hidden1[0*8+7]=h1[0];
        assign hidden1[1*8+7]=h1[1];
        assign hidden1[2*8+7]=h1[2];
        assign hidden1[3*8+7]=h1[3];
        assign hidden1[4*8+7]=h1[4];
        assign hidden1[5*8+7]=h1[5];
        assign hidden1[6*8+7]=h1[6];
        assign hidden1[7*8+7]=h1[7];
        assign hidden1[8*8+7]=h1[8];
        assign hidden1[9*8+7]=h1[9];
        assign hidden1[10*8+7]=h1[10];
        assign hidden1[11*8+7]=h1[11];
        assign hidden1[12*8+7]=h1[12];
        assign hidden1[13*8+7]=h1[13];
        assign hidden1[14*8+7]=h1[14];
        assign hidden1[15*8+7]=h1[15];
        assign hidden2[0*8+7]=h2[0];
        assign hidden2[1*8+7]=h2[1];
        assign hidden2[2*8+7]=h2[2];
        assign hidden2[3*8+7]=h2[3];
        assign hidden2[4*8+7]=h2[4];
        assign hidden2[5*8+7]=h2[5];
        assign hidden2[6*8+7]=h2[6];
        assign hidden2[7*8+7]=h2[7];
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[7];
                if(layer==1) h2[neuron[5:3]]<=activated[7];
            end
        end
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[7] = data;
        assign product[7] = operand * weight[7];
        assign mac_sum[7] = accumulator[7] + {{8{product[7][31]}},product[7]};
        igor_src_policy_activation activation(accumulator[7],layer==2,
                                               activated[7],activation_saturated[7]);
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
                BIAS_ADDRESS: begin address<=bias_base+(neuron>>3); state<=BIAS_WAIT; end
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
                    if (neuron+8>=output_count) begin
                        if (layer==2) begin busy<=0; done<=1; state<=IDLE; end
                        else begin
                            layer<=layer+1'b1; neuron<=0; state<=BIAS_ADDRESS;
                            weight_address<=layer==0 ? 12'd1200 : 12'd2232;
                        end
                    end else begin neuron<=neuron+8; state<=BIAS_ADDRESS; end
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
