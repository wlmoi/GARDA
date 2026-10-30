// No SRAM: activation storage is flip-flops.
module igor_activation_logic(input wire clk,rst_n,enable,write_enable,
 input wire [7:0] address,input wire [15:0] write_data,
 output wire signed [15:0] read_even,read_odd);
reg [15:0] even_words[0:75],odd_words[0:75];
reg [15:0] even_q,odd_q;
reg read_valid;
always @(posedge clk) begin
 if(rst_n && enable && address<152 && write_enable) begin
  if(address[0]) odd_words[address[7:1]]<=write_data;
  else even_words[address[7:1]]<=write_data;
 end
 if(rst_n && enable && address<152 && !write_enable) begin
  even_q<=even_words[address[7:1]];
  odd_q<=odd_words[address[7:1]];
 end
end
always @(posedge clk or negedge rst_n) begin
 if(!rst_n)read_valid<=0;
 else if(enable && !write_enable)read_valid<=address<152;
end
assign read_even=read_valid ? even_q:16'd0;
assign read_odd=read_valid ? odd_q:16'd0;
endmodule
