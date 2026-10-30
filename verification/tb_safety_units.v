`timescale 1ns/1ps
`default_nettype none
module tb_safety_units;
reg clk=0; always #10 clk=~clk;
reg rst_n=0,begin_frame=0,write_byte=0,commit_frame=0,busy=0;
reg [31:0] frame_sequence=1; reg [14:0] frame_addr=0; reg [7:0] frame_data=0;
wire bank,valid,map_fault,fresh,ram_wr; wire [14:0] ram_addr; wire [7:0] ram_data;
wire [31:0] sequence_out,age;
igor_costmap_manager #(.FRESH_CYCLES(8)) maps(clk,rst_n,begin_frame,write_byte,commit_frame,busy,frame_sequence,frame_addr,frame_data,bank,valid,map_fault,fresh,ram_wr,ram_addr,ram_data,sequence_out,age);
reg wr=0,lock_request=0; reg [31:0] data=32'h00143d0f;
wire locked,cfg_valid,cfg_fault; wire [4:0] max_v,max_dv; wire [6:0] max_w,max_dw;
igor_config_registers cfg(clk,rst_n,wr,lock_request,busy,data,locked,cfg_valid,cfg_fault,max_v,max_dv,max_w,max_dw);
reg [7:0] fault_code=0; wire [31:0] event_count; wire [7:0] last_fault;
igor_status_logger logger(clk,rst_n,fault_code,event_count,last_fault);
integer fd,i; reg saved_bank;
task tick; begin @(posedge clk); #1; end endtask
task reset_all; begin
 @(negedge clk); rst_n=0;begin_frame=0;write_byte=0;commit_frame=0;busy=0;wr=0;lock_request=0;data=32'h00143d0f;frame_sequence=1;frame_addr=0;fault_code=0;
 tick; @(negedge clk);rst_n=1;tick;
end endtask
task checkpoint; input [8*80-1:0] name; begin
 $fdisplay(fd,"%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",name,$time,valid,map_fault,fresh,cfg_valid,cfg_fault,event_count,last_fault);
end endtask
task start_map; begin @(negedge clk);begin_frame=1;tick;@(negedge clk);begin_frame=0; end endtask
task fill_map; begin
 start_map;
 for(i=0;i<16384;i=i+1) begin frame_addr=i;frame_data=i;write_byte=1;tick;@(negedge clk);end
 write_byte=0;
end endtask
task config_write; input [31:0] value;begin @(negedge clk);data=value;wr=1;tick;@(negedge clk);wr=0;end endtask
initial begin
 $dumpfile("units.vcd");$dumpvars(0,tb_safety_units);
 fd=$fopen("units_checkpoints.csv","w");$fdisplay(fd,"case,time_ns,map_valid,map_fault,map_fresh,cfg_valid,cfg_fault,event_count,last_fault");
 reset_all; if(valid || fresh || locked || cfg_valid || map_fault || cfg_fault) $fatal(1,"reset defaults");checkpoint("reset_defaults");
 config_write(32'h00143d0f);@(negedge clk);lock_request=1;tick;@(negedge clk);lock_request=0;
 if(!locked || !cfg_valid || max_v!=15 || max_w!=16 || max_dv!=15 || max_dw!=16) $fatal(1,"valid config decode");checkpoint("config_lock_decode");
 config_write(32'h00143d0f);if(!cfg_fault || cfg_valid) $fatal(1,"write locked");checkpoint("config_write_after_lock");
 reset_all;lock_request=1;tick;if(!cfg_fault || cfg_valid) $fatal(1,"lock missing config");checkpoint("config_lock_without_write");
 reset_all;busy=1;config_write(32'h00143d0f);if(!cfg_fault || cfg_valid) $fatal(1,"busy write");checkpoint("config_write_while_busy");
 reset_all;lock_request=1;config_write(32'h00143d0f);if(!cfg_fault || cfg_valid) $fatal(1,"write lock conflict");checkpoint("config_write_lock_conflict");
 reset_all;config_write(32'h10143d0f);if(!cfg_fault) $fatal(1,"config reserved bits");checkpoint("config_reserved_bits");
 reset_all;config_write(32'h00243d0f);if(!cfg_fault) $fatal(1,"config version");checkpoint("config_wrong_version");
 reset_all;config_write(32'h00143d1f);if(!cfg_fault) $fatal(1,"omega max 17");checkpoint("config_omega_out_of_range");
 reset_all;config_write(32'h00187d0f);if(!cfg_fault) $fatal(1,"delta omega max 33");checkpoint("config_delta_omega_out_of_range");
 reset_all;frame_sequence=0;start_map;if(!map_fault || ram_wr) $fatal(1,"sequence zero");checkpoint("map_sequence_zero");
 reset_all;commit_frame=1;tick;if(!map_fault || valid) $fatal(1,"commit no begin");checkpoint("map_commit_without_begin");
 reset_all;write_byte=1;tick;if(!map_fault || ram_wr) $fatal(1,"write no begin");checkpoint("map_write_without_begin");
 reset_all;start_map;frame_addr=1;write_byte=1;tick;if(!map_fault || ram_wr) $fatal(1,"nonsequential map");checkpoint("map_nonsequential");
 reset_all;start_map;commit_frame=1;tick;if(!map_fault || valid) $fatal(1,"truncated map");checkpoint("map_truncated");
 reset_all;begin_frame=1;write_byte=1;tick;if(!map_fault || ram_wr) $fatal(1,"begin write conflict");checkpoint("map_begin_write_conflict");
 reset_all;begin_frame=1;commit_frame=1;tick;if(!map_fault || valid) $fatal(1,"begin commit conflict");checkpoint("map_begin_commit_conflict");
 reset_all;start_map;begin_frame=1;tick;if(!map_fault) $fatal(1,"duplicate begin");checkpoint("map_nested_begin");
 reset_all;fill_map;commit_frame=1;tick;@(negedge clk);commit_frame=0;
 if(!valid || !fresh || map_fault || sequence_out!=1 || age!=0 || bank!=1) $fatal(1,"complete map commit");checkpoint("map_complete_atomic_commit");
 repeat(7)tick;if(!fresh || age!=7) $fatal(1,"fresh just before threshold");checkpoint("map_fresh_boundary_minus_one");
 tick;if(fresh || age!=8) $fatal(1,"stale threshold");checkpoint("map_stale_exact_boundary");
 frame_sequence=2;saved_bank=bank;start_map;frame_addr=0;write_byte=1;#1;
 if(ram_addr[14]!==!saved_bank || bank!==saved_bank || !valid) $fatal(1,"inactive map bank");tick;@(negedge clk);write_byte=0;checkpoint("map_upload_preserves_active_bank");
 commit_frame=1;tick;if(!map_fault || bank!==saved_bank || sequence_out!=1) $fatal(1,"truncated update corrupted active map");checkpoint("map_failed_commit_preserves_sequence_and_bank");
 reset_all;fill_map;write_byte=1;frame_addr=16384;#1;if(ram_wr) $fatal(1,"overflow write permitted");tick;if(!map_fault) $fatal(1,"overflow fault");checkpoint("map_address_count_overflow");
 reset_all;fill_map;busy=1;commit_frame=1;tick;if(!map_fault || valid) $fatal(1,"busy commit");checkpoint("map_commit_while_busy");
 reset_all;fill_map;write_byte=1;commit_frame=1;tick;if(!map_fault || valid || ram_wr) $fatal(1,"write commit conflict");checkpoint("map_write_commit_conflict");
 reset_all;fill_map;commit_frame=1;tick;@(negedge clk);commit_frame=0;frame_sequence=1;start_map;
 if(!map_fault || sequence_out!=1 || bank!=1) $fatal(1,"sequence replay");checkpoint("map_sequence_replay");
 @(negedge clk);frame_sequence=2;begin_frame=1;tick; if(!map_fault || maps.loading || ram_wr) $fatal(1,"sticky map fault");checkpoint("map_fault_sticky_until_reset");
 reset_all;fault_code=2;tick;if(event_count!=1 || last_fault!=2) $fatal(1,"logger first fault");
 repeat(5)tick;if(event_count!=1) $fatal(1,"logger repeated fault");checkpoint("logger_deduplicates_held_fault");
 @(negedge clk);fault_code=5;tick;if(event_count!=2 || last_fault!=5) $fatal(1,"logger fault transition");checkpoint("logger_records_new_code");
 @(negedge clk);fault_code=0;tick;if(event_count!=2 || last_fault!=5) $fatal(1,"logger retains last fault");
 @(negedge clk);fault_code=5;tick;if(event_count!=3 || last_fault!=5) $fatal(1,"logger recurrence");checkpoint("logger_counts_recurrence_after_clear");
 $fclose(fd);$display("PASS units: 30 directed boundary and mutation checks");$finish;
end
initial begin #20000000;$fatal(1,"units watchdog");end
endmodule
`default_nettype wire
