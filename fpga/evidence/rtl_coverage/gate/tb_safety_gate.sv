`timescale 1ns/1ps
`default_nettype none
module tb_safety_gate;
reg [9:0] ctrl;reg [4:0] cv,pv,mv,mdv;reg signed [6:0] cw,pw;reg [6:0] mw,mdw;
wire motor_enable;wire [4:0] v_command;wire signed [6:0] omega_command;wire [7:0] fault_code;
igor_safety_security_gate gate(ctrl[0],ctrl[1],ctrl[2],ctrl[3],ctrl[4],ctrl[5],ctrl[6],ctrl[7],ctrl[8],ctrl[9],cv,pv,mv,mdv,cw,pw,mw,mdw,motor_enable,v_command,omega_command,fault_code);
reg [9:0] scanned_ctrl; reg [4:0] scv,spv,smv,smdv; reg signed [6:0] scw,spw; reg [6:0] smw,smdw;
integer fd,rows,scan,n=0,expected;integer outcome_counts[0:11];integer j;
initial begin
  begin end  begin end for(j=0;j<12;j=j+1)outcome_counts[j]=0;
 fd=$fopen("gate_vectors.hex","r");if(!fd)$fatal(1,"missing vectors");
 rows=$fopen("gate_checkpoints.csv","w");$fdisplay(rows,"case,time_ns,motor_enable,v_command,omega_command,fault_code");
 while(!$feof(fd))begin
  scan=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h\n",scanned_ctrl,scv,spv,smv,smdv,scw,spw,smw,smdw,expected);
  if(scan!=10)$fatal(1,"vector format at %0d",n);
  ctrl=scanned_ctrl; cv=scv; pv=spv; mv=smv; mdv=smdv; cw=scw; pw=spw; mw=smw; mdw=smdw;
  #1;
  if(fault_code!==expected || motor_enable!==(expected==0) || v_command!==(expected==0?cv:5'd0) || omega_command!==(expected==0?cw:7'sd0))$fatal(1,"gate oracle vector=%0d expected=%0d actual=%0d",n,expected,fault_code);
  outcome_counts[expected]=outcome_counts[expected]+1;
  if(n<12)$fdisplay(rows,"gate_fault_%0d,%0d,%0d,%0d,%0d,%0d",expected,$time,motor_enable,v_command,$signed(omega_command),fault_code);
  if(n==11) begin end 
  n=n+1;
 end
 for(j=0;j<12;j=j+1)if(outcome_counts[j]==0)$fatal(1,"uncovered gate outcome %0d",j);
 $fclose(fd);$fclose(rows);$display("PASS gate: %0d oracle comparisons across all 12 outcomes",n);$finish;
end
endmodule
`default_nettype wire

