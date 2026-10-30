`timescale 1ns/1ps
module tb_garda_riscv_soc;
 parameter BOOT_FILE="../../riscv/firmware/boot.hex";
 parameter EXPECT_PASS=1;
 reg clk=0;always #10 clk=~clk;
 reg rst_n=0;
 wire done,passed,bus_fault,trap,irq,eoi,trace_valid;
 wire [31:0] signature;wire [35:0] trace_data;
 garda_riscv_soc #(.BOOT_FILE(BOOT_FILE),.ENABLE_TRACE(1)) dut(
   clk,rst_n,done,passed,bus_fault,signature,trap,irq,eoi,trace_valid,trace_data);
 integer cycles=0,input_writes=0,starts=0,outputs_read=0,interrupts=0,quiet_cycles=0,fetches=0;
 integer prior_irq=0,frame=0,j;
 reg [15:0] expected[0:707];reg [31:0] want;
 reg saw_compressed=0;
 initial begin
   $readmemh("../../verification/src_policy/artifacts/expected.hex",expected);
   repeat(5) @(negedge clk);rst_n=1;
 end
 always @(posedge clk) if(rst_n) begin
   cycles=cycles+1;
   if(trap) $fatal(1,"real CPU trapped pc=%h",dut.cpu.reg_pc);
   if(bus_fault) $fatal(1,"SoC bus fault addr=%h",dut.mem_addr);
   if(eoi && !prior_irq) interrupts=interrupts+1;
   prior_irq=eoi;
   if(dut.cpu.do_waitirq && !dut.mem_valid && !irq) quiet_cycles=quiet_cycles+1;
   if(dut.mem_valid && dut.mem_ready && dut.mem_instr) fetches=fetches+1;
   if(dut.cpu.reg_pc==32'h100) saw_compressed=1;
   if(dut.req_valid && dut.req_ready) begin
     if(dut.write_access && dut.mem_addr[7:0]==8'h0c) input_writes=input_writes+1;
     if(dut.write_access && dut.mem_addr[7:0]==0 && dut.mem_wdata==1) starts=starts+1;
     if(!dut.write_access && dut.mem_addr[7:0]>=8'h10 && dut.mem_addr[7:0]<=8'h18) outputs_read=outputs_read+1;
   end
   if(done) begin
     if(!EXPECT_PASS) begin
       if(passed || signature!==32'hbad00001 || starts!=1 || interrupts!=1)
         $fatal(1,"corrupted oracle did not produce explicit firmware failure");
       $display("PASS negative firmware oracle: CPU detected mismatched inference output and reported BAD00001");
       $finish;
     end
     if(!passed || signature!==32'h600d600d) $fatal(1,"firmware failure signature=%h",signature);
     if(input_writes!=222 || starts!=3 || outputs_read!=9 || interrupts!=3)
       $fatal(1,"missing CPU/HWPE traffic in=%d start=%d out=%d irq=%d",input_writes,starts,outputs_read,interrupts);
     if(quiet_cycles<9000 || fetches<500 || !saw_compressed) $fatal(1,"no real CPU execution/sleep evidence quiet=%d fetch=%d",quiet_cycles,fetches);
     for(frame=0;frame<3;frame=frame+1) for(j=0;j<3;j=j+1) begin
       case(frame) 0:want={{16{expected[j][15]}},expected[j]};
        1:want={{16{expected[3+j][15]}},expected[3+j]};
        2:want={{16{expected[51+j][15]}},expected[51+j]}; endcase
       if(dut.data_ram[frame*3+j]!==want) $fatal(1,"RAM result mismatch frame=%d output=%d",frame,j);
     end
     $display("PASS real PicoRV32 RV32IC: cycles=%0d fetches=%0d inputs=%0d starts=%0d outputs=%0d IRQs=%0d waitirq_quiet=%0d signature=%h",cycles,fetches,input_writes,starts,outputs_read,interrupts,quiet_cycles,signature);
     $finish;
   end
   if(cycles>100000) $fatal(1,"CPU self-test timeout pc=%h state=%h irq=%b",dut.cpu.reg_pc,dut.cpu.cpu_state,irq);
 end
endmodule
