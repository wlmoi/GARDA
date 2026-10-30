// IGOR source-policy parameters: row-major W1,b1,W2,b2,W3,b3.
`timescale 1ns/1ps
`default_nettype none
module igor_src_policy_rom #(
    parameter FILE = "rtl/igor_src_policy/policy_weights.mem"
)(
    input wire clk,
    input wire [14:0] address,
    output reg signed [15:0] data
);
    // One registered read port; Quartus may map this ROM into M10K blocks.
    (* ramstyle = "M10K" *) reg [15:0] memory [0:32767];
    initial $readmemh(FILE, memory);
    // Canonical synchronous read is required for Quartus M10K inference.
    // Core-generated addresses are 0..18050; padding makes all other reads zero.
    always @(posedge clk) data <= memory[address];
endmodule
`default_nettype wire
