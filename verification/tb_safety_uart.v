`timescale 1ns/1ps
`default_nettype none
module tb_safety_uart;
reg clk=0;always #10 clk=~clk;
reg [1:0] key=0;reg [3:0] sw=0;reg rx=1;wire tx;wire [7:0] led;
igor_uart_top #(.CLKS_PER_BIT(8),.RX_TIMEOUT_CYCLES(128)) dut(clk,key,sw,rx,tx,led);
defparam dut.inspection_rom.FILE="assets/neural_24_64_64_4/bram_unified_weights_padded.mem";
defparam dut.neural.weights.FILE="assets/neural_24_64_64_4/bram_unified_weights_padded.mem";
integer fd,i,accepted_count=0;reg [7:0] c;reg [63:0] captured_frame;
always @(posedge clk)if(!key[0])accepted_count<=0;else if(dut.accepted_command)accepted_count<=accepted_count+1;
function [7:0] crc8;input [7:0] previous,value;integer j;reg [7:0] x;begin x=previous^value;for(j=0;j<8;j=j+1)x=x[7]?(x<<1)^8'h07:x<<1;crc8=x;end endfunction
task tick;begin @(posedge clk);#1;end endtask
task reset_all;begin @(negedge clk);key=0;rx=1;sw=0;repeat(5)tick;@(negedge clk);key=3;repeat(10)tick;end endtask
task byte_tx;input [7:0] value;integer k;begin
 @(negedge clk);rx=0;repeat(8)@(negedge clk);
 for(k=0;k<8;k=k+1)begin rx=value[k];repeat(8)@(negedge clk);end
 rx=1;repeat(16)@(negedge clk);
end endtask
task send_frame;input [7:0] op;input [31:0] value;input bad_crc,bad_tail;begin
 c=crc8(0,8'ha5);c=crc8(c,op);c=crc8(c,value[7:0]);c=crc8(c,value[15:8]);c=crc8(c,value[23:16]);c=crc8(c,value[31:24]);
 byte_tx(8'ha5);byte_tx(op);byte_tx(value[7:0]);byte_tx(value[15:8]);byte_tx(value[23:16]);byte_tx(value[31:24]);byte_tx(c^bad_crc);byte_tx(bad_tail?8'h00:8'h5a);
 // Serial response runs independently of the safety command acceptance.
 repeat(800)tick;
end endtask
task checkpoint;input [8*80-1:0] name;begin
 $fdisplay(fd,"%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",name,$time,accepted_count,dut.invalid_command,dut.protocol_fault,dut.enable,dut.vc,$signed(dut.wc),dut.fault,dut.events,dut.last);
end endtask
task rejects;input [8*80-1:0] name;input [7:0] op;input [31:0] value;begin
 reset_all;send_frame(op,value,0,0);
 if(!dut.invalid_command || accepted_count!=0 || dut.enable || dut.vc!=0 || dut.wc!=0 || dut.cfg_wr || dut.mw || dut.run || dut.neural.core.loaded!=0 || dut.core.maps.loading || dut.core.cfg.valid) $fatal(1,"malformed command had side effects: %0s",name);
 if(dut.last!=4)$fatal(1,"malformed command not logged: %0s",name);checkpoint(name);
end endtask
initial begin
 $dumpfile("uart.vcd");$dumpvars(1,tb_safety_uart);$dumpvars(1,dut);$dumpvars(1,dut.serial);$dumpvars(1,dut.core.logger);
 fd=$fopen("uart_checkpoints.csv","w");$fdisplay(fd,"case,time_ns,accepted_commands,invalid_command,protocol_fault,motor_enable,v_command,omega_command,fault_code,event_count,last_fault");
 rejects("unknown_opcode_zero",0,0);rejects("unknown_opcode_17",17,0);rejects("unknown_opcode_255",255,0);
 rejects("map_write_upper_reserved",2,32'h01000000);rejects("map_write_address_reserved",2,32'h00008000);
 rejects("commit_nonzero_payload",3,1);rejects("config_reserved",4,32'h10143d0f);rejects("config_bad_version",4,32'h00243d0f);
 rejects("config_omega_gt_16",4,32'h00143d1f);rejects("config_delta_gt_32",4,32'h00187d0f);
 rejects("lock_nonzero_payload",5,1);rejects("run_nonzero_payload",6,1);rejects("status_nonzero_payload",7,1);
 rejects("rom_address_6020",8,6020);rejects("latency_nonzero_payload",9,1);
 rejects("neural_input_index_24",10,24);rejects("neural_input_reserved_low",10,32'h00000020);rejects("neural_input_reserved_high",10,32'h01000000);
 rejects("neural_start_nonzero_payload",11,1);rejects("neural_read_index_4",12,4);
 rejects("neural_cycles_nonzero_payload",13,1);rejects("command_read_nonzero_payload",14,1);
 rejects("event_count_nonzero_payload",15,1);rejects("last_fault_nonzero_payload",16,1);
 reset_all;send_frame(4,32'h00143d0f,0,0);if(accepted_count!=1 || !dut.core.cfg.valid || dut.invalid_command)$fatal(1,"valid config");checkpoint("valid_config_accepted");
 send_frame(5,0,0,0);if(!dut.core.cfg.locked || accepted_count!=2)$fatal(1,"valid lock");checkpoint("valid_lock_accepted");
 send_frame(7,0,0,0);if(dut.serial.response_sample[7:0]!=={3'd0,dut.invalid_command,dut.protocol_fault,dut.done,dut.busy,dut.enable})$fatal(1,"status mapping");checkpoint("status_response_gate_and_fault");
 send_frame(14,0,0,0);if(dut.serial.response_sample!=={20'd0,dut.wc,dut.vc})$fatal(1,"command response");checkpoint("command_response_output");
 send_frame(15,0,0,0);if(dut.serial.response_sample!==dut.events)$fatal(1,"event response");checkpoint("event_count_response");
 send_frame(16,0,0,0);if(dut.serial.response_sample!=={24'd0,dut.last})$fatal(1,"last fault response");checkpoint("last_fault_response");
 reset_all;send_frame(7,0,1,0);if(!dut.protocol_fault || accepted_count!=0 || dut.enable || dut.last!=4)$fatal(1,"bad crc");checkpoint("crc_corruption_zero_and_logged");
 send_frame(4,32'h00143d0f,0,0);if(accepted_count!=0 || dut.core.cfg.valid)$fatal(1,"protocol sticky bypass");checkpoint("good_command_after_crc_fault_rejected");
 reset_all;send_frame(7,0,0,1);if(!dut.protocol_fault || accepted_count!=0)$fatal(1,"bad terminator");checkpoint("wrong_terminator_rejected");
 reset_all;byte_tx(8'ha5);repeat(200)tick;if(!dut.protocol_fault || accepted_count!=0 || dut.serial.pos!=0)$fatal(1,"truncated timeout");checkpoint("truncated_frame_timeout");
 reset_all;@(negedge clk);rx=0;repeat(100)tick;rx=1;repeat(20)tick;if(!dut.protocol_fault || accepted_count!=0)$fatal(1,"stop bit framing");checkpoint("uart_stop_bit_error");
 reset_all;send_frame(8,6019,0,0);if(dut.invalid_command || accepted_count!=1)$fatal(1,"last legal ROM address");checkpoint("rom_address_6019_accepted");
 reset_all;send_frame(10,32'h00ffff17,0,0);if(dut.invalid_command || accepted_count!=1 || dut.neural.core.loaded!=24'h800000 || dut.neural.core.inputs[23]!=16'hffff)$fatal(1,"last neural input");checkpoint("neural_index_23_signed_minus_one_accepted");
 reset_all;send_frame(12,3,0,0);if(dut.invalid_command || accepted_count!=1)$fatal(1,"output index3");checkpoint("neural_output_index_3_accepted");
 reset_all;send_frame(7,0,0,0);if(dut.invalid_command || dut.protocol_fault || accepted_count!=1)$fatal(1,"reset recovery");checkpoint("reset_recovers_uart_faults");
 $fclose(fd);$display("PASS uart: physical serial framing and full command validation");$finish;
end
initial begin #20000000;$fatal(1,"uart watchdog");end
endmodule
`default_nettype wire
