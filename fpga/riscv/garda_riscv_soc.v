// Real upstream RV32IC control CPU + local ROM/RAM + GARDA Parallel16 MMIO.
// Board self-test only; this module has no actuator or robot safety interface.
`timescale 1ns/1ps
`default_nettype none
module garda_riscv_soc #(
 parameter BOOT_FILE="firmware/boot.hex",
 parameter ENABLE_TRACE=0
)(
 input wire clk,rst_n,
 output reg test_done,test_pass,bus_fault,
 output reg [31:0] signature,
 output wire cpu_trap,accelerator_irq,irq_eoi,
 output wire cpu_trace_valid,output wire [35:0] cpu_trace_data
);
 wire mem_valid,mem_instr;
 wire [31:0] mem_addr,mem_wdata,mem_rdata;
 wire [3:0] mem_wstrb;
 wire mem_ready;
 wire [31:0] cpu_eoi;
 picorv32 #(
   .ENABLE_COUNTERS(0),.ENABLE_COUNTERS64(0),.COMPRESSED_ISA(1),
   .ENABLE_MUL(0),.ENABLE_FAST_MUL(0),.ENABLE_DIV(0),
   .ENABLE_IRQ(1),.ENABLE_IRQ_TIMER(0),.ENABLE_IRQ_QREGS(1),
   .MASKED_IRQ(32'hffffffef),.LATCHED_IRQ(32'd0),
   .PROGADDR_RESET(0),.PROGADDR_IRQ(32'h10),.STACKADDR(32'h20000400),
   .ENABLE_TRACE(ENABLE_TRACE)
 ) cpu(
   .clk(clk),.resetn(rst_n),.trap(cpu_trap),
   .mem_valid(mem_valid),.mem_instr(mem_instr),.mem_ready(mem_ready),
   .mem_addr(mem_addr),.mem_wdata(mem_wdata),.mem_wstrb(mem_wstrb),.mem_rdata(mem_rdata),
   .pcpi_wr(1'b0),.pcpi_rd(32'd0),.pcpi_wait(1'b0),.pcpi_ready(1'b0),
   .irq({27'd0,accelerator_irq,4'd0}),.eoi(cpu_eoi),
   .trace_valid(cpu_trace_valid),.trace_data(cpu_trace_data)
 );
 assign irq_eoi=cpu_eoi[4];
 (* ramstyle="M10K" *) reg [31:0] boot_rom[0:2047];
 (* ramstyle="M10K" *) reg [31:0] data_ram[0:255];
 initial $readmemh(BOOT_FILE,boot_rom);
 reg local_response;
 reg [31:0] local_rdata;
 reg mmio_pending;
 wire rom_select=mem_addr<32'h00002000;
 wire ram_select=mem_addr[31:10]==(32'h20000000>>10);
 wire signature_select=mem_addr==32'h30000000;
 wire hwpe_select=mem_addr[31:8]==24'h100000;
 wire aligned=mem_addr[1:0]==0;
 wire write_access=|mem_wstrb;
 wire full_word=!write_access || mem_wstrb==4'b1111;
 wire valid_mmio=hwpe_select && aligned && full_word && !mem_instr;
 wire req_ready,resp_valid,resp_error;
 wire [31:0] resp_rdata;
 wire req_valid=mem_valid && valid_mmio && !mmio_pending && !local_response;
 wire resp_ready=mmio_pending && mem_valid;
 garda_policy_mmio accelerator(
   .clk(clk),.rst_n(rst_n),.req_valid(req_valid),.req_write(write_access),
   .req_addr(mem_addr[7:0]),.req_wdata(mem_wdata),.req_ready(req_ready),
   .resp_valid(resp_valid),.resp_ready(resp_ready),.resp_rdata(resp_rdata),
   .resp_error(resp_error),.irq(accelerator_irq)
 );
 assign mem_ready=local_response || (mmio_pending && resp_valid);
 assign mem_rdata=mmio_pending ? resp_rdata : local_rdata;
 always @(posedge clk or negedge rst_n) begin
   if(!rst_n) begin
     local_response<=0;local_rdata<=0;mmio_pending<=0;
     test_done<=0;test_pass<=0;signature<=0;bus_fault<=0;
   end else begin
     if(local_response && mem_valid) local_response<=0;
     if(req_valid && req_ready) mmio_pending<=1;
     if(mmio_pending && resp_valid && resp_ready) begin
       mmio_pending<=0;
       if(resp_error) bus_fault<=1;
     end
     if(mem_valid && !local_response && !mmio_pending && !valid_mmio) begin
       local_response<=1;local_rdata<=0;
       if(!aligned || !full_word) bus_fault<=1;
       else if(rom_select && !write_access) local_rdata<=boot_rom[mem_addr[12:2]];
       else if(ram_select && !mem_instr) begin
         if(write_access) data_ram[mem_addr[9:2]]<=mem_wdata;
         else local_rdata<=data_ram[mem_addr[9:2]];
       end else if(signature_select && write_access && !mem_instr) begin
         signature<=mem_wdata;test_done<=1;
         test_pass<=mem_wdata==32'h600d600d && !bus_fault;
       end else bus_fault<=1;
     end
   end
 end
endmodule
`default_nettype wire
