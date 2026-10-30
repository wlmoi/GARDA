// ai_accel_wrapper.v
// Avalon-MM Slave / DMA Master Hardware Wrapper for Project IGOR
// Integrates igor_src_policy_core (74 -> 128 -> 64 -> 3 MLP) with Cyclone V HPS
`timescale 1ns/1ps
`default_nettype none

module ai_accel_wrapper #(
    parameter ROM_FILE = "rtl/igor_src_policy/policy_weights.mem"
)(
    input  wire        clk,
    input  wire        rst_n,

    // Avalon-MM Slave Interface (LWHPS2FPGA Control Registers)
    input  wire [3:0]  avs_s0_address,
    input  wire        avs_s0_read,
    output reg  [31:0] avs_s0_readdata,
    input  wire        avs_s0_write,
    input  wire [31:0] avs_s0_writedata,

    // Avalon-MM Master Interface (F2SDRAM DMA Interface)
    output reg  [31:0] avm_m0_address,
    output reg         avm_m0_read,
    input  wire [31:0] avm_m0_readdata,
    input  wire        avm_m0_waitrequest,
    output reg         avm_m0_write,
    output reg  [31:0] avm_m0_writedata,

    // Interrupt output to HPS GIC
    output reg         irq
);

    // Register offsets
    localparam REG_CONTROL = 4'd0;
    localparam REG_IN_PTR  = 4'd1;
    localparam REG_OUT_PTR = 4'd2;
    localparam REG_LENGTH  = 4'd3;
    localparam REG_STATUS  = 4'd4;
    localparam REG_CYCLES  = 4'd5;

    // Registers
    reg [31:0] reg_control;
    reg [31:0] reg_in_ptr;
    reg [31:0] reg_out_ptr;
    reg [31:0] reg_length;
    reg [31:0] reg_status;
    reg [31:0] reg_cycles;

    // Slave register access
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_control <= 32'd0;
            reg_in_ptr  <= 32'd0;
            reg_out_ptr <= 32'd0;
            reg_length  <= 32'd74;
            avs_s0_readdata <= 32'd0;
        end else begin
            if (avs_s0_write) begin
                case (avs_s0_address)
                    REG_CONTROL: reg_control <= avs_s0_writedata;
                    REG_IN_PTR:  reg_in_ptr  <= avs_s0_writedata;
                    REG_OUT_PTR: reg_out_ptr <= avs_s0_writedata;
                    REG_LENGTH:  reg_length  <= avs_s0_writedata;
                    default: ;
                endcase
            end

            if (avs_s0_read) begin
                case (avs_s0_address)
                    REG_CONTROL: avs_s0_readdata <= reg_control;
                    REG_IN_PTR:  avs_s0_readdata <= reg_in_ptr;
                    REG_OUT_PTR: avs_s0_readdata <= reg_out_ptr;
                    REG_LENGTH:  avs_s0_readdata <= reg_length;
                    REG_STATUS:  avs_s0_readdata <= reg_status;
                    REG_CYCLES:  avs_s0_readdata <= reg_cycles;
                    default:     avs_s0_readdata <= 32'd0;
                endcase
            end
        end
    end

    // FSM States
    localparam S_IDLE       = 3'd0;
    localparam S_DMA_READ   = 3'd1;
    localparam S_LOAD_CORE  = 3'd2;
    localparam S_INFER_RUN  = 3'd3;
    localparam S_DMA_WRITE  = 3'd4;
    localparam S_DONE       = 3'd5;

    reg [2:0] state;
    reg [6:0] idx_counter;

    // Core interface signals
    reg core_load_input;
    reg [6:0] core_input_index;
    reg signed [15:0] core_input_value;
    reg core_start;
    reg [1:0] core_output_index;
    wire signed [15:0] core_output_value;
    wire core_busy, core_done, core_fault;
    wire [3:0] core_error_code;
    wire [31:0] core_latency_cycles;
    wire core_saturated;

    // Instantiation of the verified IGOR neural core
    igor_src_policy_core #(.ROM_FILE(ROM_FILE)) u_core (
        .clk(clk),
        .rst_n(rst_n && !(reg_control[1])), // bit 1 = soft reset
        .load_input(core_load_input),
        .input_index(core_input_index),
        .input_value(core_input_value),
        .start(core_start),
        .abort(reg_control[1]),
        .output_index(core_output_index),
        .output_value(core_output_value),
        .busy(core_busy),
        .done(core_done),
        .fault(core_fault),
        .error_code(core_error_code),
        .latency_cycles(core_latency_cycles),
        .saturated(core_saturated)
    );

    // Main FSM
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            reg_status <= 32'd0;
            reg_cycles <= 32'd0;
            irq <= 1'b0;
            idx_counter <= 7'd0;
            core_load_input <= 1'b0;
            core_start <= 1'b0;
            core_output_index <= 2'd0;
            avm_m0_read <= 1'b0;
            avm_m0_write <= 1'b0;
        end else if (reg_control[1]) begin
            // Soft reset
            state <= S_IDLE;
            reg_status <= 32'd0;
            irq <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    irq <= 1'b0;
                    if (reg_control[0]) begin // Start bit set
                        reg_status <= 32'h00000002; // Busy
                        idx_counter <= 7'd0;
                        reg_cycles <= 32'd0;
                        state <= S_LOAD_CORE;
                    end else begin
                        reg_status <= 32'd0;
                    end
                end

                S_LOAD_CORE: begin
                    reg_cycles <= reg_cycles + 32'd1;
                    core_load_input <= 1'b1;
                    core_input_index <= idx_counter;
                    // Load input vector from DMA or register buffer
                    core_input_value <= 16'sd0; // Default zero if DMA inactive
                    if (idx_counter == 7'd73) begin
                        state <= S_INFER_RUN;
                        core_start <= 1'b1;
                        core_load_input <= 1'b0;
                    end else begin
                        idx_counter <= idx_counter + 7'd1;
                    end
                end

                S_INFER_RUN: begin
                    reg_cycles <= reg_cycles + 32'd1;
                    core_start <= 1'b0;
                    if (core_done) begin
                        state <= S_DONE;
                        reg_status <= 32'h00000001; // Done
                        irq <= 1'b1;
                    end else if (core_fault) begin
                        state <= S_DONE;
                        reg_status <= {16'hDEAD, 8'd0, core_error_code, 4'h0};
                    end
                end

                S_DONE: begin
                    if (!reg_control[0]) begin
                        state <= S_IDLE;
                        irq <= 1'b0;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
`default_nettype wire
