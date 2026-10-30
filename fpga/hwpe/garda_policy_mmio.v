// GARDA policy MMIO adapter. Author: William Anthony.
// Experimental register interface; no CPU, TCDM, DMA, or safety gate is implied.
`timescale 1ns/1ps
`default_nettype none
module garda_policy_mmio(
 input wire clk, rst_n,
 input wire req_valid, input wire req_write, input wire [7:0] req_addr,
 input wire [31:0] req_wdata, output wire req_ready,
 output reg resp_valid, input wire resp_ready, output reg [31:0] resp_rdata,
 output reg resp_error, output wire irq
);
 localparam CTRL=8'h00, STATUS=8'h04, INDEX=8'h08, DATA=8'h0c,
            OUT0=8'h10, OUT1=8'h14, OUT2=8'h18, CYCLES=8'h1c;
 reg [6:0] index_reg;
 reg reset_pending;
 wire busy, done, fault, saturated;
 wire [3:0] error_code;
 wire [31:0] latency_cycles;
 wire [1:0] output_index = req_addr==OUT1 ? 2'd1 : req_addr==OUT2 ? 2'd2 : 2'd0;
 wire signed [15:0] output_value;
 assign req_ready = !reset_pending && (!resp_valid || resp_ready);
 wire accept = req_valid && req_ready;
 wire ctrl_write = accept && req_write && req_addr==CTRL;
 wire valid_cmd = req_wdata==32'd1 || req_wdata==32'd2 || req_wdata==32'd4;
 wire soft_reset = ctrl_write && req_wdata==32'd4;
 wire abort = ctrl_write && req_wdata==32'd2;
 wire start = ctrl_write && req_wdata==32'd1 && !busy && !fault;
 wire load_input = accept && req_write && req_addr==DATA && index_reg<74 && !busy && !fault;
 assign irq = done || fault;
 garda_src_policy_core core(
   .clk(clk), .rst_n(rst_n && !reset_pending), .load_input(load_input),
   .input_index(index_reg), .input_value(req_wdata[15:0]), .start(start), .abort(abort),
   .output_index(output_index), .output_value(output_value), .busy(busy), .done(done),
   .fault(fault), .error_code(error_code), .latency_cycles(latency_cycles), .saturated(saturated)
 );
 always @(posedge clk or negedge rst_n) begin
   if (!rst_n) begin
     index_reg<=0; reset_pending<=0; resp_valid<=0; resp_rdata<=0; resp_error<=0;
   end else begin
     reset_pending<=soft_reset;
     if (soft_reset) index_reg<=0;
     if (accept) begin
       resp_valid<=1; resp_rdata<=0; resp_error<=0;
       if (req_write) begin
         case (req_addr)
           CTRL: if (!valid_cmd || (req_wdata==32'd1 && (busy || fault))) resp_error<=1;
           INDEX: if (req_wdata>=74 || busy || fault) resp_error<=1; else index_reg<=req_wdata[6:0];
           DATA: if (index_reg>=74 || busy || fault) resp_error<=1; else index_reg<=index_reg+1'b1;
           default: resp_error<=1;
         endcase
       end else begin
         case (req_addr)
           STATUS: resp_rdata<={24'd0,error_code,saturated,fault,done,busy};
           INDEX: resp_rdata<={25'd0,index_reg};
           OUT0,OUT1,OUT2: resp_rdata<={{16{output_value[15]}},output_value};
           CYCLES: resp_rdata<=latency_cycles;
           default: resp_error<=1;
         endcase
       end
     end else if (resp_valid && resp_ready) resp_valid<=0;
   end
 end
endmodule
`default_nettype wire
