`timescale 1ns/1ps
module tb;
reg clk=1,rst_n=1,en=1,we=0;
reg [7:0] address=0;
reg [15:0] data=0;
wire signed [15:0] even_data,odd_data;
garda_activation_sram dut(clk,rst_n,en,we,address,data,even_data,odd_data);
task tick;begin #5;clk=0;#5;clk=1;#1;end endtask
integer i;
reg [15:0] saved_even,saved_odd;
initial begin
 rst_n=0;tick;rst_n=1;we=1;
 for(i=0;i<152;i=i+1)begin address=i;data=(i*941)^16'h1234;tick;end
 we=0;
 for(i=0;i<152;i=i+2)begin
  address=i;tick;
  if(even_data!==(((i*941)^16'h1234)&65535) ||
     odd_data!==((((i+1)*941)^16'h1234)&65535))$fatal(1,"activation pair %0d",i);
 end
 saved_even=even_data;saved_odd=odd_data;
 // Neuron stores must preserve BOTH prefetched operands until the next read.
 we=1;address=23;data=16'hc123;tick;
 if(even_data!==saved_even || odd_data!==saved_odd)$fatal(1,"odd write output hold");
 address=24;data=16'h8123;tick;
 if(even_data!==saved_even || odd_data!==saved_odd)$fatal(1,"even write output hold");
 we=0;address=22;tick;if(odd_data!==16'hc123)$fatal(1,"input boundary write");
 address=24;tick;if(even_data!==16'h8123)$fatal(1,"h1 boundary write");
 en=0;we=1;data=0;tick;en=1;we=0;tick;
 if(even_data!==16'h8123)$fatal(1,"disabled activation write");
 rst_n=0;we=1;tick;rst_n=1;we=0;tick;
 if(even_data!==16'h8123)$fatal(1,"activation reset retention");
 we=1;data=0;
 for(i=152;i<256;i=i+1)begin address=i;tick;end
 we=0;address=24;tick;if(even_data!==16'h8123)$fatal(1,"invalid write alias");
 for(i=152;i<256;i=i+1)begin address=i;tick;
  if(even_data!==0 || odd_data!==0)$fatal(1,"invalid activation read");
 end
 $display("PASS activation SRAM: 152 words, paired reads, write hold, bounds, enable, reset");
 $finish;
end
endmodule
