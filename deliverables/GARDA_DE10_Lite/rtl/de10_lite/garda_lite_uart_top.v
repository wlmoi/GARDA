// GARDA DE10-Lite UART top.
//
// Derived from rtl/garda_core/garda_uart_top.v (SHA-256 in rtl/CORE_SHA256SUMS.txt).
// Every legacy statement of garda_uart_top is kept unchanged below; the only
// modifications are ADDITIONS, each marked "DE10-Lite extension":
//
//   1. New opcodes 0x20..0x29 (legacy opcodes 1..16 keep their exact payload
//      contracts, responses and side effects; everything else is still an
//      invalid command and still sets the sticky invalid_command flag).
//   2. Two extra stop sources that can only REMOVE motor permission:
//        estop           = !KEY[1] || host_estop        (host E-stop latch)
//        protective_stop = SW[3]   || watchdog_trip     (host-link watchdog)
//      Both latch until reset, matching the existing latching E-stop behaviour
//      of garda_top (FAULT state is sticky until KEY0 / reset).
//   3. Read-only observation registers (E-stop capture, counters, build ID).
//
// The safety gate, planner, neural datapath, protocol framing and CRC are the
// unmodified garda_core modules. sim/tb_lockstep.v runs this module and the
// original garda_uart_top side by side on identical random legacy traffic and
// requires bit-identical UART TX and LED outputs on every clock cycle.
`timescale 1ns/1ps
`default_nettype none
module garda_lite_uart_top #(parameter [15:0] CLKS_PER_BIT=16'd434,
 parameter [31:0] RX_TIMEOUT_CYCLES=32'd5000000,
 parameter [15:0] CYCLES_PER_MS=16'd50000,           // DE10-Lite extension
 parameter [31:0] BUILD_ID=32'h00000000,             // DE10-Lite extension
 // DE10-Lite extension: garda_top's lease/freshness in cycles, so the board top can keep
 // them at 20 ms when the core clock is not 50 MHz. Defaults = garda_top defaults.
 parameter [31:0] DEADLINE_CYCLES=32'd1000000,FRESH_CYCLES=32'd1000000)(
 input wire FPGA_CLK1_50,input wire [1:0] KEY,input wire [3:0] SW,
 input wire UART_RX,output wire UART_TX,output wire [7:0] LED,
 // DE10-Lite extension: observation ports for the board top (HEX, LEDR).
 output wire [7:0] obs_fault,output wire [7:0] obs_last_fault,
 output wire obs_host_estop,output wire obs_watchdog_trip,
 output wire obs_frame,output wire [15:0] obs_accepted_count,
 // {2'b0, frame_count[15:0], last_op[7:0], nn_fault, nn_done, nn_busy, watchdog_armed,
 //  key_estop_sync, protocol_fault, invalid_command, busy, done, enable, wc[6:0], vc[4:0]}
 output reg [47:0] obs_status,    // registered: observers never extend core timing paths
 // DE10-Lite extension: two-host arbiter statistics {collisions, grants_b, grants_a} and current owner.
 input wire [47:0] port_stats,input wire port_owner,
 // DE10-Lite extension: board I/O snapshot {pll_locked, LEDR[9:0], KEY[1:0], SW[9:0]} (read-only).
 input wire [22:0] board_io,
 // DE10-Lite extension: out-of-band host E-stop pulse (garda_estop_sniffer on each raw RX pin).
 input wire oob_estop);
reg [1:0] reset_sync;reg [3:0] sw_meta,sw_sync;
always @(posedge FPGA_CLK1_50 or negedge KEY[0])begin if(!KEY[0])reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};end
wire rst_n=reset_sync[1];
always @(posedge FPGA_CLK1_50 or negedge rst_n)begin if(!rst_n)begin sw_meta<=0;sw_sync<=0;end else begin sw_meta<=SW;sw_sync<=sw_meta;end end
wire command,protocol_fault;wire [7:0] op;wire [31:0] data;reg [31:0] response;reg invalid_command;
garda_uart_protocol #(.CLKS_PER_BIT(CLKS_PER_BIT),.RX_TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES)) serial(FPGA_CLK1_50,rst_n,UART_RX,UART_TX,command,op,data,response,protocol_fault);
wire enable,busy,done;wire [4:0] vc;wire signed [6:0] wc;wire [7:0] fault,last;
wire [8:0] index;wire [31:0] latency,score,cost,goal,velocity,events;

// DE10-Lite extension: opcode numbers (all outside the legacy 1..16 range).
localparam [7:0] OP_IDENT=8'h20,OP_HOST_ESTOP=8'h21,OP_SAFE_RESET=8'h22,OP_WATCHDOG=8'h23,
 OP_EXT_STATUS=8'h24,OP_ESTOP_TEST=8'h25,OP_ESTOP_CAPTURE=8'h26,OP_COUNTERS=8'h27,
 OP_BUILD_ID=8'h28,OP_LINK_INFO=8'h29,OP_PORT_STATS=8'h2A,OP_PORT_INFO=8'h2B,OP_BOARD_IO=8'h2C,OP_NN_CMD=8'h2D;
localparam [31:0] IDENT_VALUE=32'h47444C02;      // "GDL" + interface version 2 (v2 adds 0x2A..0x2C)
localparam [31:0] SAFE_RESET_MAGIC=32'h52534554; // "RSET"

// Enforce the complete command contract before any architectural side effect.
// Reserved bits must be zero; a correct CRC is not permission to reinterpret a
// malformed payload. An invalid command is sticky until external reset.
reg payload_ok;
always @(*) begin
 payload_ok=1'b0;
 case(op)
  1:payload_ok=1'b1; // Sequence validation belongs to the map manager.
  2:payload_ok=data[31:24]==0 && data[15]==0;
  4:payload_ok=data[31:28]==0 && data[27:20]==8'd1 && data[9:4]<=6'd16 && data[19:14]<=6'd32;
  8:payload_ok=data<32'd6020;
  10:payload_ok=data[7:5]==0 && data[31:24]==0 && data[4:0]<24;
  12:payload_ok=data[31:2]==0;
  3,5,6,7,9,11,13,14,15,16:payload_ok=data==0;
  // DE10-Lite extension contracts.
  OP_IDENT,OP_HOST_ESTOP,OP_EXT_STATUS,OP_ESTOP_CAPTURE,OP_COUNTERS,OP_BUILD_ID,OP_LINK_INFO,OP_PORT_STATS,OP_PORT_INFO,OP_BOARD_IO:payload_ok=data==0;
  OP_SAFE_RESET:payload_ok=data==SAFE_RESET_MAGIC; // reset itself is issued by garda_safe_reset_sniffer
  OP_WATCHDOG:payload_ok=data[31:16]==0;           // timeout in ms, 0 = disarm
  OP_ESTOP_TEST:payload_ok=data[31:24]==0 && data[23:0]!=0; // delay in clock cycles after the next result
  OP_NN_CMD:payload_ok=data[31:2]==0;                       // neural output index 0..3
  default:payload_ok=1'b0;
 endcase
end
wire accepted_command=command && payload_ok && !invalid_command && !protocol_fault;
wire cfg_wr=accepted_command && op==4,cfg_lock=accepted_command && op==5,run=accepted_command && op==6;
wire mb=accepted_command && op==1,mw=accepted_command && op==2,mc=accepted_command && op==3;

// DE10-Lite extension: additional latching stop sources (can only remove permission).
reg host_estop,watchdog_trip;
wire key_estop=!KEY[1];
wire estop_any=key_estop || host_estop;
wire protective_any=sw_sync[3] || watchdog_trip;

// Begin command payload is visible during its command pulse. No stale sequence register.
garda_top #(.DEADLINE_CYCLES(DEADLINE_CYCLES),.FRESH_CYCLES(FRESH_CYCLES)) core(FPGA_CLK1_50,rst_n,!protocol_fault && !invalid_command && !(command && !payload_ok) && !sw_sync[2],estop_any,protective_any,run,cfg_wr,cfg_lock,data,
 mb,mw,mc,data,data[14:0],data[23:16],enable,vc,wc,fault,busy,done,latency,index,score,cost,goal,velocity,events,last);
wire signed [15:0] rom_data,nn_value;wire nn_busy,nn_done,nn_fault;wire [31:0] nn_cycles;
garda_neural_rom inspection_rom(FPGA_CLK1_50,data[12:0],rom_data);
garda_neural_core neural(FPGA_CLK1_50,rst_n,accepted_command && op==10,accepted_command && op==11,data[4:0],data[23:8],data[1:0],nn_value,nn_busy,nn_done,nn_fault,nn_cycles);
always @(posedge FPGA_CLK1_50 or negedge rst_n)begin
 if(!rst_n)begin invalid_command<=0;end
 else if(command)begin
  if(!payload_ok)invalid_command<=1;
 end
end

// ---------------------------------------------------------------------------
// DE10-Lite extension: host E-stop, link watchdog, E-stop response capture.
// ---------------------------------------------------------------------------
reg [1:0] key_estop_meta;            // synchronised copy, observation only
reg watchdog_armed;reg [15:0] watchdog_timeout_ms,watchdog_ms,watchdog_tick;
reg estop_test_armed,estop_test_waiting;reg [23:0] estop_test_delay,estop_test_count;
reg done_q;reg [3:0] enable_hist;reg [4:0] vc_q;reg signed [6:0] wc_q;
reg estop_seen_q;
reg cap_valid,cap_measuring,cap_enable_before,cap_source_host,cap_source_key;
reg [4:0] cap_v;reg signed [6:0] cap_w;reg [7:0] cap_latency;
reg [15:0] frame_count,accepted_count;
wire key_estop_sync=key_estop_meta[1];
wire estop_seen=key_estop_sync || host_estop;
always @(posedge FPGA_CLK1_50 or negedge rst_n)begin
 if(!rst_n)begin
  host_estop<=0;watchdog_trip<=0;key_estop_meta<=0;
  watchdog_armed<=0;watchdog_timeout_ms<=0;watchdog_ms<=0;watchdog_tick<=0;
  estop_test_armed<=0;estop_test_waiting<=0;estop_test_delay<=0;estop_test_count<=0;
  done_q<=0;enable_hist<=0;vc_q<=0;wc_q<=0;estop_seen_q<=0;
  cap_valid<=0;cap_measuring<=0;cap_enable_before<=0;cap_source_host<=0;cap_source_key<=0;
  cap_v<=0;cap_w<=0;cap_latency<=0;frame_count<=0;accepted_count<=0;
 end else begin
  key_estop_meta<={key_estop_meta[0],key_estop};
  done_q<=done;enable_hist<={enable_hist[2:0],enable};vc_q<=vc;wc_q<=wc;
  if(command && frame_count!=16'hffff)frame_count<=frame_count+1'b1;
  if(accepted_command && accepted_count!=16'hffff)accepted_count<=accepted_count+1'b1;
  // Host E-stop: immediate, latched until reset.
  if((accepted_command && op==OP_HOST_ESTOP) || oob_estop)host_estop<=1;   // OOB path cannot be blocked by the arbiter
  // Controlled E-stop test: assert the host E-stop a fixed number of cycles
  // after the next planner result, so the capture does not depend on USB latency.
  if(accepted_command && op==OP_ESTOP_TEST)begin estop_test_armed<=1;estop_test_waiting<=0;estop_test_delay<=data[23:0];end
  else if(estop_test_armed && done && !done_q)begin estop_test_armed<=0;estop_test_waiting<=1;estop_test_count<=24'd1;end
  else if(estop_test_waiting)begin
   if(estop_test_count>=estop_test_delay)begin estop_test_waiting<=0;host_estop<=1;end
   else estop_test_count<=estop_test_count+1'b1;
  end
  // Host-link watchdog: once armed, any accepted command restarts it; expiry latches a protective stop.
  if(accepted_command && op==OP_WATCHDOG)begin
   watchdog_armed<=data[15:0]!=0;watchdog_timeout_ms<=data[15:0];watchdog_ms<=0;watchdog_tick<=0;
  end else if(accepted_command)begin watchdog_ms<=0;watchdog_tick<=0;end
  else if(watchdog_armed && !watchdog_trip)begin
   if(watchdog_tick>=CYCLES_PER_MS-1'b1)begin
    watchdog_tick<=0;
    if(watchdog_ms+1'b1>=watchdog_timeout_ms)watchdog_trip<=1;else watchdog_ms<=watchdog_ms+1'b1;
   end else watchdog_tick<=watchdog_tick+1'b1;
  end
  // E-stop capture: motor permission just before the stop and the number of
  // clock edges until motor_enable was observed low (0 = already low at the
  // first edge after the stop reached the gate).
  estop_seen_q<=estop_seen;
  if(estop_seen && !estop_seen_q)begin
   cap_source_host<=host_estop;cap_source_key<=key_estop_sync;
   // The synchronised key copy lags the raw key (which reaches the gate
   // directly) by up to 3 edges, so look further back for that source.
   cap_enable_before<=host_estop && !key_estop_sync ? enable_hist[0] : enable_hist[3];
   cap_v<=vc_q;cap_w<=wc_q;cap_latency<=0;
   if(!enable)begin cap_valid<=1;cap_measuring<=0;end else begin cap_valid<=0;cap_measuring<=1;end
  end else if(cap_measuring)begin
   if(!enable)begin cap_valid<=1;cap_measuring<=0;end
   else if(cap_latency!=8'hff)cap_latency<=cap_latency+1'b1;
  end
 end
end

// ---------------------------------------------------------------------------
// DE10-Lite extension: neural command gate. The neural core's outputs are only a
// proposal. Before a host may use them as a motion command (demo mapping: outputs
// 0,1,2 = Vx, Vy, omega in Q8.8) they are clamped to [-1.00, +0.99] (-256..+253)
// and forced to 0 unless every condition below holds. E-stop latches until reset.
// ---------------------------------------------------------------------------
reg nn_estop_latch;
always @(posedge FPGA_CLK1_50 or negedge rst_n)begin
 if(!rst_n)nn_estop_latch<=0;else if(estop_seen)nn_estop_latch<=1;
end
wire nn_permit=!nn_estop_latch && !estop_seen && !sw_sync[3] && !watchdog_trip && !sw_sync[2] &&
 !protocol_fault && !invalid_command && nn_done && !nn_fault;
wire signed [15:0] nn_clamped=nn_value>16'sd253 ? 16'sd253 : (nn_value< -16'sd256 ? -16'sd256 : nn_value);
wire signed [15:0] nn_gated=nn_permit ? nn_clamped : 16'sd0;

always @(*)begin
 response={7'd0,index,fault,3'd0,invalid_command,protocol_fault,done,busy,enable};
 case(op)
 8:response={16'd0,rom_data};
 9:response=latency;
 12:response={13'd0,nn_fault,nn_busy,nn_done,nn_value};
 13:response=nn_cycles;
 14:response={20'd0,wc,vc};
 15:response=events;
 16:response={24'd0,last};
 // DE10-Lite extension responses.
 OP_IDENT:response=IDENT_VALUE;
 OP_EXT_STATUS:response={last,fault,2'd0,invalid_command,protocol_fault,busy,done,enable,sw_sync[3],
  sw_sync[2],cap_valid,estop_test_waiting,estop_test_armed,watchdog_trip,watchdog_armed,key_estop_sync,host_estop};
 OP_ESTOP_CAPTURE:response={cap_latency,4'd0,cap_w,cap_v,3'd0,cap_source_key,cap_source_host,cap_enable_before,cap_measuring,cap_valid};
 OP_COUNTERS:response={frame_count,accepted_count};
 OP_BUILD_ID:response=BUILD_ID;
 OP_LINK_INFO:response={CLKS_PER_BIT,CYCLES_PER_MS};
 OP_PORT_STATS:response=port_stats[31:0];                       // {grants_b, grants_a}
 OP_PORT_INFO:response={port_stats[47:32],15'd0,port_owner};     // {collisions, requesting port: 0=A 1=B}
 OP_NN_CMD:response={nn_fault,nn_busy,nn_done,nn_permit,12'd0,nn_gated};   // gated, clamped neural command
 OP_BOARD_IO:response={9'd0,board_io};                           // [9:0] SW [11:10] KEY (1=released) [21:12] LEDR [22] PLL locked
 default:response={7'd0,index,fault,3'd0,invalid_command,protocol_fault,done,busy,enable};
 endcase
end
assign LED={fault[3:0],done,busy,rst_n,enable};
// DE10-Lite extension observation ports.
assign obs_fault=fault;assign obs_last_fault=last;assign obs_host_estop=host_estop;
assign obs_watchdog_trip=watchdog_trip;assign obs_frame=command;assign obs_accepted_count=accepted_count;
always @(posedge FPGA_CLK1_50 or negedge rst_n)begin
 if(!rst_n)obs_status<=48'd0;
 else obs_status<={2'b00,frame_count,op,nn_fault,nn_done,nn_busy,watchdog_armed,key_estop_sync,protocol_fault,
  invalid_command,busy,done,enable,wc,vc};
end
endmodule
`default_nettype wire
