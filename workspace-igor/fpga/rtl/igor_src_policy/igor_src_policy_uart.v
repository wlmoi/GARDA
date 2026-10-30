// Source FPGABridge protocol. A residual is NOT a motor command or motor permit.
// Any failed transaction produces no successful response; the host must stop.
`timescale 1ns/1ps
`default_nettype none
module igor_src_policy_uart #(
    parameter integer CLK_HZ=50000000,
    parameter integer BAUD=921600,
    parameter integer RX_TIMEOUT_CYCLES=1000000,
    parameter integer RESULT_TIMEOUT_CYCLES=1000000,
    parameter integer INFER_TIMEOUT_CYCLES=100000,
    parameter ROM_FILE="rtl/igor_src_policy/policy_weights.mem"
)(
    input wire clk, rst_n, uart_rx, estop,
    output wire uart_tx,
    output wire [3:0] debug_state,
    output reg [7:0] error_code,
    output wire [15:0] error_flags,
    output reg [31:0] accepted_frames, rejected_frames, last_latency_cycles,
    output wire safety_permit,
    output reg response_valid,
    output wire signed [15:0] action0, action1, action2
);
    localparam integer BIT_CYCLES=(CLK_HZ+BAUD/2)/BAUD;
    localparam RX=4'd0, LOAD=4'd1, START=4'd2, RUN=4'd3,
               CAP0=4'd4, CAP1=4'd5, CAP2=4'd6, TX=4'd7,
               TX_START_LAST=4'd8, TX_END_LAST=4'd9;
    reg estop_meta, estop_sync, estop_previous;
    wire estop_active=estop | estop_sync;
    // Assert immediately; release only after a two-flop synchronizer.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin estop_meta<=0; estop_sync<=0; end
        else begin estop_meta<=estop; estop_sync<=estop_meta; end
    end
    wire rx_valid, rx_error;
    wire [7:0] rx_data;
    reg tx_send, tx_cancel;
    reg [7:0] tx_data;
    wire tx_busy;
    igor_uart_rx #(.CLKS_PER_BIT(BIT_CYCLES)) receiver(
        clk,rst_n,uart_rx,rx_valid,rx_error,rx_data);
    igor_uart_tx #(.CLKS_PER_BIT(BIT_CYCLES)) transmitter(
        clk,rst_n && !estop_active && !tx_cancel,tx_send,tx_data,uart_tx,tx_busy);

    function [7:0] crc8;
        input [7:0] previous, data;
        reg [7:0] c;
        integer j;
        begin
            c=previous ^ data;
            for (j=0;j<8;j=j+1)
                c=c[0] ? (c>>1)^8'h8c : (c>>1);
            crc8=c;
        end
    endfunction
    function [7:0] action_crc;
        input [15:0] a,b,c;
        reg [7:0] check;
        begin
            check=crc8(0,8'h02); check=crc8(check,8'h06);
            check=crc8(check,a[7:0]); check=crc8(check,a[15:8]);
            check=crc8(check,b[7:0]); check=crc8(check,b[15:8]);
            check=crc8(check,c[7:0]); check=crc8(check,c[15:8]);
            action_crc=check;
        end
    endfunction

    reg [3:0] mode;
    // Only implemented fault codes require flops. Reserved bits are tied low,
    // avoiding undriven/unreachable-bit latch inference in Quartus synthesis.
    reg [11:0] error_history;
    assign error_flags={3'b000,error_history,1'b0};
    reg [7:0] position, crc, low_byte;
    reg invalid_observation;
    reg signed [15:0] frame_observation [0:73];
    wire signed [15:0] received_word={rx_data,low_byte};
    wire [7:0] payload_index=position-8'd4;
    reg [6:0] load_index;
    reg core_load,core_start,core_abort;
    reg [6:0] core_input_index;
    reg signed [15:0] core_input_value;
    reg [1:0] core_output_index;
    wire signed [15:0] core_output_value;
    wire core_busy,core_done,core_fault,core_saturated;
    wire [3:0] core_error;
    wire [31:0] core_latency;
    igor_src_policy_core #(.ROM_FILE(ROM_FILE)) core(
        clk,rst_n,core_load,core_input_index,core_input_value,
        core_start,core_abort | estop_active,core_output_index,
        core_output_value,core_busy,core_done,core_fault,core_error,
        core_latency,core_saturated);
    reg signed [15:0] sample0,sample1,sample2;
    reg result_valid;
    reg [31:0] rx_timer,infer_timer,result_timer;
    reg [3:0] tx_index;
    reg [7:0] response_crc;
    assign safety_permit=result_valid && !estop_active && !core_fault;
    assign action0=safety_permit ? sample0 : 16'sd0;
    assign action1=safety_permit ? sample1 : 16'sd0;
    assign action2=safety_permit ? sample2 : 16'sd0;
    assign debug_state=estop_active ? 4'hf : (core_fault ? 4'he : mode);

    // One call per cycle at most. Last error + sticky history make failures traceable.
    // Codes: 1 E-stop, 2 framing, 3 header, 4 opcode, 5 length, 6 CRC,
    // 7 inter-byte timeout, 8 normalized-observation range, 9 busy,
    // 10 internal core, 11 stale residual, 12 inference watchdog.
    task reject;
        input [7:0] code;
        begin
            error_code<=code; error_history<=error_history | (12'h1 << (code[3:0]-1'b1));
            // Audit counters saturate: long-running faults must never look like
            // a fresh/reset device after wrapping through zero.
            if (rejected_frames!=32'hffffffff)
                rejected_frames<=rejected_frames+1'b1;
            result_valid<=0; position<=0; mode<=RX;
            rx_timer<=0; infer_timer<=0;
            core_abort<=1; core_start<=0; core_load<=0;
            tx_send<=0; tx_cancel<=1;
        end
    endtask

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mode<=RX; position<=0; crc<=0; low_byte<=0;
            invalid_observation<=0; load_index<=0;
            core_load<=0; core_start<=0; core_abort<=0;
            core_input_index<=0; core_input_value<=0; core_output_index<=0;
            sample0<=0; sample1<=0; sample2<=0; result_valid<=0;
            rx_timer<=0; infer_timer<=0; result_timer<=0;
            tx_index<=0; response_crc<=0; tx_send<=0; tx_data<=0; tx_cancel<=0;
            error_code<=0; error_history<=0; accepted_frames<=0;
            rejected_frames<=0; last_latency_cycles<=0; response_valid<=0;
            estop_previous<=0;
        end else begin
            core_load<=0; core_start<=0; core_abort<=0;
            tx_send<=0; tx_cancel<=0; response_valid<=0;
            estop_previous<=estop_active;
            if (result_valid) result_timer<=result_timer+1'b1;
            if (mode==RUN) infer_timer<=infer_timer+1'b1;
            if (position!=0) rx_timer<=rx_timer+1'b1;

            if (estop_active) begin
                result_valid<=0; position<=0; mode<=RX; rx_timer<=0;
                core_abort<=1; tx_cancel<=1;
                if (!estop_previous) begin
                    error_code<=1; error_history<=error_history | 12'h001;
                    if (rejected_frames!=32'hffffffff)
                        rejected_frames<=rejected_frames+1'b1;
                end
            end else if (core_fault && mode!=RX) reject(8'd10);
            else if (rx_error) reject(8'd2);
            else if (rx_valid && mode!=RX) reject(8'd9);
            else if (mode==RUN && infer_timer>=INFER_TIMEOUT_CYCLES-1) reject(8'd12);
            else if (position!=0 && !rx_valid && rx_timer>=RX_TIMEOUT_CYCLES-1) reject(8'd7);
            else if (result_valid && result_timer>=RESULT_TIMEOUT_CYCLES-1) reject(8'd11);
            else begin
                if (rx_valid) begin
                    rx_timer<=0;
                    case (position)
                        0: if (rx_data==8'h5a) begin
                            position<=1; result_valid<=0;
                        end
                        1: if (rx_data==8'ha5) position<=2;
                           else if (rx_data!=8'h5a) reject(8'd3);
                        2: if (rx_data==8'h01) begin
                            crc<=crc8(0,rx_data); position<=3;
                        end else reject(8'd4);
                        3: if (rx_data==8'h94) begin
                            crc<=crc8(crc,rx_data); position<=4;
                            invalid_observation<=0;
                        end else reject(8'd5);
                        152: begin
                            position<=0;
                            if (rx_data!=crc) reject(8'd6);
                            else if (invalid_observation) reject(8'd8);
                            else begin
                                if (accepted_frames!=32'hffffffff)
                                    accepted_frames<=accepted_frames+1'b1;
                                load_index<=0; mode<=LOAD;
                            end
                        end
                        default: begin
                            crc<=crc8(crc,rx_data);
                            position<=position+1'b1;
                            if (!payload_index[0]) low_byte<=rx_data;
                            else begin
                                frame_observation[payload_index[7:1]]<=received_word;
                                if (payload_index[7:1]<64) begin
                                    if (received_word<0 || received_word>16'sd256)
                                        invalid_observation<=1;
                                end else if (received_word < -16'sd256 || received_word>16'sd256)
                                    invalid_observation<=1;
                            end
                        end
                    endcase
                end
                case (mode)
                    RX: begin end
                    LOAD: begin
                        core_load<=1; core_input_index<=load_index;
                        core_input_value<=frame_observation[load_index];
                        if (load_index==73) mode<=START;
                        else load_index<=load_index+1'b1;
                    end
                    START: begin core_start<=1; mode<=RUN; infer_timer<=0; end
                    RUN: if (core_done) begin
                        last_latency_cycles<=core_latency;
                        core_output_index<=0; mode<=CAP0;
                    end
                    CAP0: begin sample0<=core_output_value; core_output_index<=1; mode<=CAP1; end
                    CAP1: begin sample1<=core_output_value; core_output_index<=2; mode<=CAP2; end
                    CAP2: begin
                        sample2<=core_output_value;
                        response_crc<=action_crc(sample0,sample1,core_output_value);
                        result_valid<=1; result_timer<=0; response_valid<=1;
                        tx_index<=0; mode<=TX;
                    end
                    TX: if (!tx_busy && !tx_send) begin
                        case (tx_index)
                            0: tx_data<=8'h5a;
                            1: tx_data<=8'ha5;
                            2: tx_data<=8'h02;
                            3: tx_data<=8'h06;
                            4: tx_data<=sample0[7:0];
                            5: tx_data<=sample0[15:8];
                            6: tx_data<=sample1[7:0];
                            7: tx_data<=sample1[15:8];
                            8: tx_data<=sample2[7:0];
                            9: tx_data<=sample2[15:8];
                            default: tx_data<=response_crc;
                        endcase
                        tx_send<=1;
                        if (tx_index==10) mode<=TX_START_LAST;
                        else tx_index<=tx_index+1'b1;
                    end
                    TX_START_LAST: if (tx_busy) mode<=TX_END_LAST;
                    TX_END_LAST: if (!tx_busy) mode<=RX;
                    default: reject(8'd10);
                endcase
            end
        end
    end
endmodule
`default_nettype wire
