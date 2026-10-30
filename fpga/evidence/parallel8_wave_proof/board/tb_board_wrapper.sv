`timescale 1ns/1ps
module tb_board_wrapper;
 localparam BIT_CYCLES=54, BIT_NS=1080;
 reg clk=0;always #10 clk=~clk;
 reg [1:0] key=2'b00;reg rx=1;wire tx;wire [7:0] led;
 igor_src_policy_de10_nano dut(clk,key,rx,tx,led);
 reg signed [15:0] observation[0:236*74-1],expected[0:236*3-1];
 reg [7:0] response[0:255],monitored_byte;
 reg [7:0] decoded_byte=0;
 integer received=0,bit_number,fd,checkpoints=0;
 integer accepted_before,rejected_before;
 initial forever begin
  @(negedge tx);#(BIT_NS+BIT_NS/2);
  for(bit_number=0;bit_number<8;bit_number=bit_number+1)begin monitored_byte[bit_number]=tx;#(BIT_NS);end
  if(tx && key[0])begin response[received]=monitored_byte;decoded_byte=monitored_byte;received=received+1;end
 end
 function [7:0] crc8;input [7:0] prior,value;integer j;reg [7:0] c;begin
  c=prior^value;for(j=0;j<8;j=j+1)c=c[0]?(c>>1)^8'h8c:c>>1;crc8=c;
 end endfunction
 task tick;begin @(posedge clk);#1;end endtask
 task checkpoint;input [8*96-1:0] name;begin
  $fdisplay(fd,"%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",name,$time,key[0],key[1],dut.rst_n,dut.stop_active,dut.stop_latched,dut.permit,dut.error_code,dut.error_flags,$signed(dut.a0),$signed(dut.a1),$signed(dut.a2),dut.accepted,dut.rejected,received);
  checkpoints=checkpoints+1;
 end endtask
 task assert_zero;begin #1;if(dut.permit || dut.a0!==0 || dut.a1!==0 || dut.a2!==0)$fatal(1,"board wrapper zero gate failed");end endtask
 task reset_board;begin
  @(negedge clk);key=2'b10;rx=1;repeat(5)tick;
  @(negedge clk);key=2'b11;#1;if(dut.rst_n!==0)$fatal(1,"reset deassert bypassed synchronizer");
  tick;if(dut.rst_n!==0)$fatal(1,"reset released before two clocks");
  tick;if(dut.rst_n!==1)$fatal(1,"reset did not release after two clocks");
  repeat(6)tick;received=0;assert_zero;
  if(dut.stop_active || dut.stop_latched || dut.error_code || dut.error_flags || dut.accepted || dut.rejected || tx!==1)$fatal(1,"clean boot had phantom E-stop or UART error");
  checkpoint("clean_boot_no_phantom_estop");
 end endtask
 task uart_byte;input [7:0] value;integer k;begin
  @(negedge clk);rx=0;repeat(BIT_CYCLES)tick;
  for(k=0;k<8;k=k+1)begin @(negedge clk);rx=value[k];repeat(BIT_CYCLES)tick;end
  @(negedge clk);rx=1;repeat(BIT_CYCLES)tick;@(negedge clk);
 end endtask
 task frame_without_crc;integer n;reg [15:0] value;begin
  uart_byte(8'h5a);uart_byte(8'ha5);uart_byte(8'h01);uart_byte(8'h94);
  for(n=0;n<74;n=n+1)begin value=observation[74+n];uart_byte(value[7:0]);uart_byte(value[15:8]);end
 end endtask
 function [7:0] frame_crc;integer n;reg [7:0] check;reg [15:0] value;begin
  check=crc8(crc8(0,1),8'h94);
  for(n=0;n<74;n=n+1)begin value=observation[74+n];check=crc8(check,value[7:0]);check=crc8(check,value[15:8]);end
  frame_crc=check;
 end endfunction
 task full_frame;begin frame_without_crc;uart_byte(frame_crc());end endtask
 task expect_response;integer n,limit;reg [7:0] check;reg signed [15:0] word_value;begin
  limit=0;while(received<11 && limit<80000)begin tick;limit=limit+1;end
  if(received!=11 || response[0]!=8'h5a || response[1]!=8'ha5 || response[2]!=2 || response[3]!=6)$fatal(1,"board response missing/header");
  check=0;for(n=2;n<10;n=n+1)check=crc8(check,response[n]);
  if(response[10]!==check)$fatal(1,"board response CRC");
  for(n=0;n<3;n=n+1)begin word_value={response[5+2*n],response[4+2*n]};if(word_value!==expected[3+n])$fatal(1,"board response numerical mismatch");end
  if(!dut.permit || dut.a0!==expected[3] || dut.a1!==expected[4] || dut.a2!==expected[5] || dut.cycles!=6916)$fatal(1,"board guarded result mismatch");
  repeat(120)tick;checkpoint("full_crc_valid_uart_response_matches_src_model");
 end endtask
 always @(negedge clk)begin #2;
  if(dut.rst_n && (!dut.permit || dut.stop_active) && (dut.a0!==0 || dut.a1!==0 || dut.a2!==0))$fatal(1,"continuous board output invariant");
  if(dut.stop_active && dut.permit)$fatal(1,"continuous raw stop invariant");
 end
 initial begin
  $dumpfile("artifacts/board.vcd");
  $dumpvars(1,tb_board_wrapper);$dumpvars(1,dut);$dumpvars(1,dut.policy);
$dumpvars(1,dut.policy.receiver);$dumpvars(1,dut.policy.transmitter);
$dumpvars(1,dut.policy.core);
$dumpvars(1,dut.policy.core.lane0);$dumpvars(1,dut.policy.core.lane0.activation);
$dumpvars(1,dut.policy.core.lane1);$dumpvars(1,dut.policy.core.lane1.activation);
$dumpvars(1,dut.policy.core.lane2);$dumpvars(1,dut.policy.core.lane2.activation);
$dumpvars(1,dut.policy.core.lane3);$dumpvars(1,dut.policy.core.lane3.activation);
$dumpvars(1,dut.policy.core.lane4);$dumpvars(1,dut.policy.core.lane4.activation);
$dumpvars(1,dut.policy.core.lane5);$dumpvars(1,dut.policy.core.lane5.activation);
$dumpvars(1,dut.policy.core.lane6);$dumpvars(1,dut.policy.core.lane6.activation);
$dumpvars(1,dut.policy.core.lane7);$dumpvars(1,dut.policy.core.lane7.activation);
  fd=$fopen("artifacts/checkpoints.csv","w");
  $fdisplay(fd,"case,time_ns,key_reset_n,key_estop_n,rst_n,stop_active,stop_latched,residual_permit,error_code,error_flags,action0,action1,action2,accepted,rejected,received_bytes");
  $readmemh("D:/LinkedinProjects/igor_ws/igor_ws/fpga/verification/src_policy/artifacts/observations.hex",observation);
  $readmemh("D:/LinkedinProjects/igor_ws/igor_ws/fpga/verification/src_policy/artifacts/expected.hex",expected);
  reset_board;
  uart_byte(8'h5a);uart_byte(8'ha5);uart_byte(1);assert_zero;
  if(dut.accepted!=0 || received!=0 || dut.policy.core_busy)$fatal(1,"partial header accepted");checkpoint("partial_header_never_accepted");
  reset_board;frame_without_crc;assert_zero;
  if(dut.accepted!=0 || dut.policy.core_busy || received!=0)$fatal(1,"CRC-less complete payload accepted");checkpoint("all_74_fields_without_crc_never_accepted");
  uart_byte(frame_crc());if(dut.accepted!=1)$fatal(1,"complete frame not accepted");checkpoint("crc_completes_single_frame_acceptance");
  expect_response;
  accepted_before=dut.accepted;rejected_before=dut.rejected;
  @(negedge clk);#3;key[1]=0;assert_zero;
  if(!dut.stop_active || led[0] || tx!==1)$fatal(1,"raw key immediate inhibition");checkpoint("raw_key1_between_clocks_immediate_zero");
  repeat(8)tick;if(!dut.stop_latched || dut.error_code!=1 || !dut.error_flags[1] || dut.rejected!=rejected_before+1)$fatal(1,"stop not latched/logged");checkpoint("key1_stop_latched_and_error_recorded");
  repeat(50)tick;if(dut.rejected!=rejected_before+1)$fatal(1,"held stop recounted each clock");checkpoint("held_estop_deduplicated");
  @(negedge clk);key[1]=1;repeat(10)tick;assert_zero;
  if(!dut.stop_active || !dut.stop_latched || dut.error_code!=1)$fatal(1,"release cleared safety latch");checkpoint("key1_release_still_stopped_until_reset");
  full_frame;repeat(20)tick;assert_zero;
  if(dut.accepted!=accepted_before || dut.rejected!=rejected_before+1)$fatal(1,"latched stop accepted new packet");checkpoint("valid_frame_while_latched_never_accepted");
  reset_board;full_frame;expect_response;checkpoint("key0_reset_restores_successful_inference");
  @(negedge clk);key[0]=0;#1;assert_zero;if(dut.rst_n || dut.stop_latched || dut.accepted || dut.error_code)$fatal(1,"raw reset did not asynchronously clear state");checkpoint("raw_key0_reset_immediately_clears_gate_and_history");
  // Held E-stop at startup is a real stop, never a clean-boot false positive.
  key=0;repeat(5)tick;@(negedge clk);key[0]=1;repeat(10)tick;assert_zero;
  if(!dut.stop_latched || dut.error_code!=1 || !dut.error_flags[1] || dut.rejected!=1)$fatal(1,"boot with stop held not recorded once");checkpoint("boot_with_key1_held_real_estop_recorded_once");
  @(negedge clk);key[1]=1;repeat(10)tick;assert_zero;if(!dut.stop_latched)$fatal(1,"boot stop latch released");checkpoint("boot_stop_release_requires_reset");
  reset_board;
  $fclose(fd);$display("PASS board_wrapper: %0d checkpoints, actual50MHz/921600 framing and KEY safety",checkpoints);$finish;
 end
 initial begin #30000000;$fatal(1,"board wrapper watchdog");end
endmodule
