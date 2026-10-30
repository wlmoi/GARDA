`timescale 1ns/1ps
`default_nettype none
module tb_safety_top;
reg clk=0;always #10 clk=~clk;
reg rst_n=0,ready=1,estop=0,protective_stop=0,start=0,cfg_write=0,cfg_lock=0,map_begin=0,map_write=0,map_commit=0;
reg [31:0] cfg_data=32'h00143d0f,map_sequence=1;reg [14:0] map_address=0;reg [7:0] map_byte=0;
wire motor_enable,busy,done;wire [4:0] v_command;wire signed [6:0] omega_command;
wire [7:0] fault_code,last_fault;wire [8:0] selected_index;
wire [31:0] latency_cycles,selected_score,selected_cost,selected_goal,selected_velocity,event_count;
igor_top #(.DEADLINE_CYCLES(10000),.FRESH_CYCLES(60000)) core(clk,rst_n,ready,estop,protective_stop,start,cfg_write,cfg_lock,cfg_data,map_begin,map_write,map_commit,map_sequence,map_address,map_byte,motor_enable,v_command,omega_command,fault_code,busy,done,latency_cycles,selected_index,selected_score,selected_cost,selected_goal,selected_velocity,event_count,last_fault);
// These parameter variants isolate deadline and map freshness independently.
wire stale_enable,stale_done;wire [7:0] stale_fault,stale_last;wire [31:0] stale_events;
igor_top #(.DEADLINE_CYCLES(100000),.FRESH_CYCLES(10000)) freshness_core(.clk(clk),.rst_n(rst_n),.ready(ready),.estop(estop),.protective_stop(protective_stop),.start(start),.cfg_write(cfg_write),.cfg_lock(cfg_lock),.cfg_data(cfg_data),.map_begin(map_begin),.map_write(map_write),.map_commit(map_commit),.map_sequence(map_sequence),.map_address(map_address),.map_byte(map_byte),.motor_enable(stale_enable),.done(stale_done),.fault_code(stale_fault),.last_fault(stale_last),.event_count(stale_events));
wire deadline_enable,deadline_busy;wire [7:0] deadline_fault,deadline_last;wire [31:0] deadline_events;
igor_top #(.DEADLINE_CYCLES(100),.FRESH_CYCLES(12000)) deadline_core(.clk(clk),.rst_n(rst_n),.ready(ready),.estop(estop),.protective_stop(protective_stop),.start(start),.cfg_write(cfg_write),.cfg_lock(cfg_lock),.cfg_data(cfg_data),.map_begin(map_begin),.map_write(map_write),.map_commit(map_commit),.map_sequence(map_sequence),.map_address(map_address),.map_byte(map_byte),.motor_enable(deadline_enable),.busy(deadline_busy),.fault_code(deadline_fault),.last_fault(deadline_last),.event_count(deadline_events));
integer fd,i,checkpoint_source=0;reg [31:0] events_before;
task tick;begin @(posedge clk);#1;end endtask
task checkpoint;input [8*80-1:0] name;begin
 case(checkpoint_source)
  1:$fdisplay(fd,"%0s,%0d,deadline_core,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",name,$time,deadline_enable,deadline_core.v_command,$signed(deadline_core.omega_command),deadline_fault,deadline_events,deadline_last,deadline_busy,deadline_core.done,deadline_core.maps.age,deadline_core.elapsed);
  2:$fdisplay(fd,"%0s,%0d,freshness_core,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",name,$time,stale_enable,freshness_core.v_command,$signed(freshness_core.omega_command),stale_fault,stale_events,stale_last,freshness_core.busy,stale_done,freshness_core.maps.age,freshness_core.elapsed);
  default:$fdisplay(fd,"%0s,%0d,core,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",name,$time,motor_enable,v_command,$signed(omega_command),fault_code,event_count,last_fault,busy,done,core.maps.age,core.elapsed);
 endcase
end endtask
task zero_outputs;input [7:0] expected;begin
 #1;if(motor_enable!==0 || v_command!==0 || omega_command!==0 || fault_code!==expected) $fatal(1,"safety mismatch expected fault=%0d actual=%0d enable=%b v=%0d w=%0d",expected,fault_code,motor_enable,v_command,$signed(omega_command));
end endtask
task reset_all;begin
 @(negedge clk);rst_n=0;ready=1;estop=0;protective_stop=0;start=0;cfg_write=0;cfg_lock=0;map_begin=0;map_write=0;map_commit=0;map_sequence=1;
 tick;@(negedge clk);rst_n=1;tick;
end endtask
task prepare;begin
 reset_all;
 @(negedge clk);cfg_write=1;tick;@(negedge clk);cfg_write=0;cfg_lock=1;tick;@(negedge clk);cfg_lock=0;map_begin=1;tick;@(negedge clk);map_begin=0;
 for(i=0;i<16384;i=i+1)begin map_write=1;map_address=i;map_byte=0;tick;@(negedge clk);end
 map_write=0;map_commit=1;tick;@(negedge clk);map_commit=0;tick;
 if(!core.map_ok || !core.cfg_ok) $fatal(1,"prepare prerequisites");
end endtask
task launch;begin @(negedge clk);start=1;tick;@(negedge clk);start=0;tick;end endtask
task result_ready;begin
 prepare;launch;wait(done===1);#1;
 if(!motor_enable || v_command==0 || fault_code!=0 || latency_cycles!=7938) $fatal(1,"valid rollout result");
 checkpoint("valid_nonzero_result_7938_cycles");
end endtask
// Checked every falling clock throughout upload, run, result, and faults.
always @(negedge clk) begin #1;if(rst_n)begin
 if(!motor_enable && (v_command!==0 || omega_command!==0))$fatal(1,"zero-output invariant");
 if(motor_enable && (!ready || estop || protective_stop || !core.map_ok || !core.cfg_ok || !core.best_valid || !core.result_map_matches || !done || start || core.tile_done!=15 || core.tile_fault!=0 || core.lease_expired || core.control_fault))$fatal(1,"permit prerequisite invariant");
end
end
initial begin
 $dumpfile("top.vcd");
 // Deliberately omit four replicated map RAM arrays from the viewing artifact.
 $dumpvars(1,tb_safety_top);$dumpvars(1,core);$dumpvars(1,core.maps);$dumpvars(1,core.cfg);$dumpvars(1,core.gate);$dumpvars(1,core.logger);
 $dumpvars(1,deadline_core);$dumpvars(1,freshness_core);$dumpvars(1,freshness_core.maps);
 fd=$fopen("top_checkpoints.csv","w");$fdisplay(fd,"case,time_ns,instance,motor_enable,v_command,omega_command,fault_code,event_count,last_fault,busy,done,map_age,elapsed");
 reset_all;@(negedge clk);start=1;zero_outputs(5);tick;start=0;zero_outputs(5);checkpoint("start_without_map_rejected_and_latched");
 prepare;@(negedge clk);cfg_write=1;tick;@(negedge clk);cfg_write=0;zero_outputs(6);tick;if(last_fault!=6)$fatal(1,"config fault log");checkpoint("locked_config_mutation_zero_and_logged");
 result_ready;events_before=event_count;#3;estop=1;zero_outputs(2);checkpoint("estop_asserted_between_clocks_immediate_zero");
 tick;if(last_fault!=2 || event_count!=events_before+1)$fatal(1,"estop log");checkpoint("estop_registered_error_log");
 @(negedge clk);estop=0;tick;zero_outputs(2);checkpoint("estop_release_requires_reset");
 @(negedge clk);start=1;tick;start=0;zero_outputs(2);checkpoint("restart_without_reset_rejected");
 result_ready;#3;protective_stop=1;zero_outputs(3);tick;if(last_fault!=3)$fatal(1,"protective log");checkpoint("protective_stop_result_zero_and_logged");
 prepare;launch;repeat(20)tick;@(negedge clk);estop=1;zero_outputs(2);tick;if(last_fault!=2)$fatal(1,"run estop log");checkpoint("estop_during_run_aborts");
 prepare;launch;repeat(20)tick;@(negedge clk);protective_stop=1;zero_outputs(3);tick;if(last_fault!=3)$fatal(1,"run protective log");checkpoint("protective_stop_during_run_aborts");
 result_ready;#3;ready=0;zero_outputs(4);tick;if(last_fault!=4)$fatal(1,"ready log");checkpoint("ready_drop_result_zero_and_logged");
 result_ready;@(negedge clk);map_write=1;map_address=0;tick;@(negedge clk);map_write=0;zero_outputs(5);tick;if(last_fault!=5)$fatal(1,"invalid map log");checkpoint("write_without_map_begin_zero_and_logged");
 result_ready;@(negedge clk);start=1;zero_outputs(9);checkpoint("new_start_retracts_old_command_immediately");tick;@(negedge clk);start=0;tick;if(!busy || motor_enable)$fatal(1,"rerun old result not removed");checkpoint("rerun_busy_no_old_command");
 result_ready;
 wait(deadline_core.timed_out===1);#1;if(deadline_enable || deadline_fault!=8)$fatal(1,"compute deadline");tick;if(deadline_last!=8)$fatal(1,"compute timeout log");checkpoint_source=1;checkpoint("compute_deadline_variant_zero_and_logged");checkpoint_source=0;
 wait(freshness_core.maps.age==10000);#1;if(stale_enable || stale_fault!=5)$fatal(1,"stale map exact cutoff");checkpoint_source=2;checkpoint("map_freshness_exact_boundary_zero");tick;if(stale_last!=5)$fatal(1,"stale map log");checkpoint("map_freshness_zero_and_logged");checkpoint_source=0;
 wait(core.lease_expired===1);zero_outputs(8);checkpoint("result_command_lease_exact_boundary_zero");tick;if(last_fault!=8)$fatal(1,"result lease log");checkpoint("result_command_lease_zero_and_logged");
 reset_all;zero_outputs(5);checkpoint("external_reset_recovers_sticky_faults");
 // Stage the next complete map before RUN, then commit in RESULT. The old
 // result must never be authorized against a new map, even if all bytes match.
 prepare;@(negedge clk);map_sequence=2;map_begin=1;tick;@(negedge clk);map_begin=0;
 for(i=0;i<16384;i=i+1)begin map_write=1;map_address=i;map_byte=0;tick;@(negedge clk);end
 map_write=0;launch;wait(done===1);#1;
 if(!motor_enable || core.run_map_sequence!=1 || core.seq!=1)$fatal(1,"original map result before swap");checkpoint("map_sequence_1_result_before_valid_swap");
 @(negedge clk);map_commit=1;tick;@(negedge clk);map_commit=0;zero_outputs(9);
 if(!core.map_ok || core.seq!=2 || core.run_map_sequence!=1 || core.result_map_matches)$fatal(1,"valid map swap provenance");checkpoint("valid_map_swap_retracts_previous_result");
 tick;if(last_fault!=9)$fatal(1,"map swap invalid result log");checkpoint("map_swap_requires_fresh_result_logged");
 launch;wait(done===1);#1;
 if(!motor_enable || core.run_map_sequence!=2 || core.seq!=2 || !core.result_map_matches)$fatal(1,"fresh plan did not bind new map");checkpoint("fresh_run_binds_map_sequence_2_and_recovers");
 $fclose(fd);$display("PASS top: asynchronous stop, mutation, reset, deadline, freshness, and invariants");$finish;
end
initial begin #20000000;$fatal(1,"top watchdog");end
endmodule
`default_nettype wire
