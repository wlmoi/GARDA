`timescale 1ns/1ps
module tb;
reg clk=1,rst_n=1,en=1,we=0;
reg [12:0] a=0;
reg [15:0] d=0,mask=16'hffff;
wire signed [15:0] q,qe,qo;
garda_parameter_sram dut(clk,rst_n,en,we,a,d,mask,q,qe,qo);
task tick;begin #5;clk=0;#5;clk=1;#1;end endtask
integer i;
reg [15:0] saved;
initial begin
 rst_n=0;tick;rst_n=1;
 // Distinct contents in every location catch bank aliases, including even/odd parity and row boundaries.
 we=1;
 for(i=0;i<6020;i=i+1)begin a=i;d=(i*17)^16'ha55a;tick;end
 we=0;
 for(i=0;i<6020;i=i+1)begin
  a=i;tick;if(q!==(((i*17)^16'ha55a)&65535))$fatal(1,"address %0d",i);
   if(qe!==((((i & ~1)*17)^16'ha55a)&65535) ||
     qo!==(((((i & ~1)+1)*17)^16'ha55a)&65535))$fatal(1,"parallel pair %0d",i);
 end
 a=254;tick;saved=q;a=255;#1;
 if(q!==saved)$fatal(1,"bank mux changed before read edge");
 tick;if(q!==(((255*17)^16'ha55a)&65535))$fatal(1,"bank boundary");
 a=2047;tick;saved=q;a=2048;#1;
 if(q!==saved)$fatal(1,"row/parity selection changed before read edge");
 tick;if(q!==(((2048*17)^16'ha55a)&65535))$fatal(1,"row boundary");
 a=6019;we=1;d=16'ha55a;tick;
 we=0;tick;if(q!==16'ha55a)$fatal(1,"last word");
 we=1;mask=16'h00ff;d=16'h003c;tick;
 if(q!==16'ha55a)$fatal(1,"write must hold output");
 we=0;tick;if(q!==16'ha53c)$fatal(1,"low byte mask");
 we=1;mask=16'hff00;d=16'h8100;tick;
 we=0;tick;if(q!==16'h813c)$fatal(1,"high byte mask");
 we=1;mask=16'h00f0;d=16'h00a0;tick;
 we=0;tick;if(q!==16'h81ac)$fatal(1,"partial bit mask");
 // The three adjacent quarters of this physical row must remain untouched.
 for(i=6016;i<6019;i=i+1)begin
  a=i;tick;if(q!==(((i*17)^16'ha55a)&65535))$fatal(1,"masked write changed neighbor %0d",i);
 end
 a=6019;tick;
 en=0;we=1;d=0;mask=16'hffff;tick;
 if(q!==16'h81ac)$fatal(1,"disabled hold");
 en=1;we=0;tick;if(q!==16'h81ac)$fatal(1,"disabled write");
 rst_n=0;we=1;d=0;tick;rst_n=1;we=0;tick;
 if(q!==16'h81ac)$fatal(1,"reset retention");
 // Tail words and unused physical rows cannot write or alias valid memory.
 we=1;d=0;
 for(i=6020;i<8192;i=i+1)begin a=i;tick;end
 we=0;a=6019;tick;if(q!==16'h81ac)$fatal(1,"invalid write alias");
 for(i=6020;i<8192;i=i+1)begin a=i;tick;if(q!==0)$fatal(1,"invalid read");end
 $display("PASS SRAM: 6020 addresses, bank edges, masks, enable, invalid range, reset");
 $finish;
end
endmodule
