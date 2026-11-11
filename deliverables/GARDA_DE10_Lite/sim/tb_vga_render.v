// Renders one frame of garda_vga_status to a text pixel dump (scripts/vga_png.py -> PNG).
`timescale 1ns/1ps
`default_nettype none
module tb_vga_render;
reg clk=0;always #10 clk=~clk;reg rst_n=0;
wire [3:0] r,g,b;wire hs,vs;
garda_vga_status dut(.clk(clk),.rst_n(rst_n),.motor_enable(`EN),.busy(1'b0),.done(1'b1),.protocol_fault(1'b0),.invalid_command(1'b0),
 .host_estop(`HE),.key_estop(1'b0),.watchdog_armed(1'b1),.watchdog_trip(1'b0),.nn_busy(1'b0),.nn_done(1'b1),.nn_fault(1'b0),.uart_activity(1'b1),
 .fault(`FAULT),.last_fault(8'd2),.last_op(8'h07),.v_cmd(`EN ? 5'd12 : 5'd0),.w_cmd(`EN ? -7'sd3 : 7'sd0),   // gated outputs: zero unless permitted
 .frames(16'h4012),.port_a(16'h0123),.port_b(16'h0042),.sw(`SW),
 .vga_r(r),.vga_g(g),.vga_b(b),.vga_hs(hs),.vga_vs(vs));
integer fd,x,y;reg [9:0] h1,h2,h3,v1,v2,v3;
initial begin
 fd=$fopen(`OUT,"w");#100 rst_n=1;
 // skip to the start of the second frame, then dump; coordinates are delayed by the 2-stage pipeline
 wait(dut.vc==10'd524);wait(dut.vc==10'd0);
 forever begin
  @(posedge clk);
  if(dut.pe)begin
   h3=h2;v3=v2;h2=h1;v2=v1;h1=dut.hc;v1=dut.vc;
   #1 if(h3<640 && v3<480)$fdisplay(fd,"%0d %0d %h%h%h",h3,v3,r,g,b);
   if(v3==479 && h3==639)begin $fclose(fd);$finish;end
  end
 end
end
endmodule
