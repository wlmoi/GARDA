`timescale 1ns/1ps
module tb_src_policy_uart;
    localparam N=`VECTOR_COUNT, BIT_CYCLES=8, BIT_NS=160;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,uart_rx=1,estop=0;
    wire uart_tx,safety_permit,response_valid;
    wire [3:0] debug_state;
    wire [7:0] error_code;
    wire [15:0] error_flags;
    wire [31:0] accepted_frames,rejected_frames,last_latency_cycles;
    wire signed [15:0] action0,action1,action2;
    igor_src_policy_uart #(.CLK_HZ(800000),.BAUD(100000),
        .RX_TIMEOUT_CYCLES(256),.RESULT_TIMEOUT_CYCLES(100000),
        .INFER_TIMEOUT_CYCLES(60000)) dut(
        clk,rst_n,uart_rx,estop,uart_tx,debug_state,error_code,error_flags,
        accepted_frames,rejected_frames,last_latency_cycles,safety_permit,
        response_valid,action0,action1,action2);
    reg signed [15:0] observations[0:N*74-1],expected[0:N*3-1];
    reg [7:0] received[0:4095];
    integer received_count=0,response_pulses=0,cycle=0,checkpoints;
    integer test_id=0,checks=0,field_id,boundary,case_count=0;
    reg [7:0] monitored_byte;
    integer monitor_bit;
    always @(posedge clk) begin
        cycle<=cycle+1;
        if(rst_n && response_valid)response_pulses<=response_pulses+1;
        #2;
        if(rst_n && !safety_permit && (action0!==0 || action1!==0 || action2!==0))
            $fatal(1,"Residual values escaped the validity gate");
        if(rst_n && estop && (safety_permit || action0!==0 || action1!==0 || action2!==0))
            $fatal(1,"E-stop failed output masking");
    end
    // Independent bit-level receiver: does not reuse the DUT UART RX implementation.
    initial forever begin
        @(negedge uart_tx);
        #(BIT_NS+BIT_NS/2);
        for(monitor_bit=0;monitor_bit<8;monitor_bit=monitor_bit+1)begin
            monitored_byte[monitor_bit]=uart_tx;#(BIT_NS);
        end
        if(uart_tx && rst_n)begin
            received[received_count]=monitored_byte;received_count=received_count+1;
        end
    end
    function [7:0] crc8;
        input [7:0] previous,value;
        integer bit_number;
        reg [7:0] c;
        begin
            c=previous^value;
            for(bit_number=0;bit_number<8;bit_number=bit_number+1)
                c=c[0] ? (c>>1)^8'h8c : c>>1;
            crc8=c;
        end
    endfunction
    task tick;begin @(posedge clk);#1;end endtask
    task checkpoint;
        input [255:0] event_name;
        begin
            $fdisplay(checkpoints,"%0d,%0t,%0d,%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                cycle,$time,test_id,event_name,estop,safety_permit,error_code,error_flags,
                $signed(action0),$signed(action1),$signed(action2),accepted_frames,rejected_frames);
        end
    endtask
    task reset_all;
        begin
            @(negedge clk);rst_n=0;uart_rx=1;estop=0;
            repeat(5)tick();
            @(negedge clk);rst_n=1;
            repeat(5)tick();received_count=0;response_pulses=0;
            if(error_code!==0||error_flags!==0||safety_permit||accepted_frames||rejected_frames)
                $fatal(1,"UART reset/boot created a false status error");
        end
    endtask
    task uart_byte;
        input [7:0] value;
        input stop_good;
        integer bit_number;
        begin
            @(negedge clk);uart_rx=0;repeat(BIT_CYCLES)tick();
            for(bit_number=0;bit_number<8;bit_number=bit_number+1)begin
                @(negedge clk);uart_rx=value[bit_number];repeat(BIT_CYCLES)tick();
            end
            @(negedge clk);uart_rx=stop_good;repeat(BIT_CYCLES)tick();
            @(negedge clk);uart_rx=1;
        end
    endtask
    task packet;
        input integer vector_number;
        input flip_crc;
        input integer invalid_index;
        input signed [15:0] invalid_value;
        integer element;
        reg [15:0] word_value;
        reg [7:0] check;
        begin
            uart_byte(8'h5a,1);uart_byte(8'ha5,1);
            uart_byte(8'h01,1);uart_byte(8'h94,1);
            check=crc8(crc8(0,8'h01),8'h94);
            for(element=0;element<74;element=element+1)begin
                word_value=element==invalid_index ? invalid_value : observations[vector_number*74+element];
                uart_byte(word_value[7:0],1);check=crc8(check,word_value[7:0]);
                uart_byte(word_value[15:8],1);check=crc8(check,word_value[15:8]);
            end
            uart_byte(check ^ (flip_crc ? 8'h01 : 8'h00),1);
        end
    endtask
    task expect_error;
        input [7:0] code;
        begin
            repeat(15)tick();
            if(error_code!==code||!error_flags[code]||safety_permit||
               action0!==0||action1!==0||action2!==0||response_valid)
                $fatal(1,"Test %0d expected safe error %0d, got %0d permit=%0d",test_id,code,error_code,safety_permit);
            checks=checks+1;case_count=case_count+1;checkpoint("rejected_zero_guard");
        end
    endtask
    task expect_response;
        input integer vector_number,first_byte;
        integer limit,byte_index;
        reg [7:0] check;
        reg signed [15:0] received_action;
        begin
            limit=0;
            while(received_count<first_byte+11 && limit<70000)begin tick();limit=limit+1;end
            if(received_count!=first_byte+11)$fatal(1,"Test %0d: missing response, received=%0d error=%0d",test_id,received_count,error_code);
            if(received[first_byte]!==8'h5a || received[first_byte+1]!==8'ha5 ||
               received[first_byte+2]!==2 || received[first_byte+3]!==6)
                $fatal(1,"Bad response header");
            check=0;
            for(byte_index=2;byte_index<10;byte_index=byte_index+1)check=crc8(check,received[first_byte+byte_index]);
            if(received[first_byte+10]!==check)$fatal(1,"Response Maxim CRC mismatch");
            for(byte_index=0;byte_index<3;byte_index=byte_index+1)begin
                received_action={received[first_byte+5+byte_index*2],received[first_byte+4+byte_index*2]};
                if(received_action!==expected[vector_number*3+byte_index])
                    $fatal(1,"Response %0d mismatch got=%0d expected=%0d",byte_index,received_action,expected[vector_number*3+byte_index]);
            end
            if(!safety_permit || last_latency_cycles!==6916 ||
               action0!==expected[vector_number*3] || action1!==expected[vector_number*3+1] || action2!==expected[vector_number*3+2])
                $fatal(1,"Response did not match guarded outputs/latency");
            // Wait for the final physical stop bit and serializer handoff.
            repeat(20)tick();
            checks=checks+7;case_count=case_count+1;checkpoint("valid_residual_response");
        end
    endtask
    task assert_estop;
        begin
            @(negedge clk);#3;estop=1;#1;
            if(safety_permit || action0!==0 || action1!==0 || action2!==0)
                $fatal(1,"Raw asynchronous E-stop did not immediately gate residual");
            repeat(5)tick();expect_error(1);
        end
    endtask
    initial begin #300000000;$fatal(1,"Global UART regression timeout");end
    initial begin
        
        
        checkpoints=$fopen("uart_checkpoints.csv","w");
        $fdisplay(checkpoints,"cycle,time_ps,test_id,event,estop,residual_valid,last_error,error_flags,action0_q8_8,action1_q8_8,action2_q8_8,accepted,rejected");
        $readmemh("D:/LinkedinProjects/igor_ws/igor_ws/fpga/verification/src_policy/artifacts/observations.hex",observations);
        $readmemh("D:/LinkedinProjects/igor_ws/igor_ws/fpga/verification/src_policy/artifacts/expected.hex",expected);
        // Dallas/Maxim published check value for ASCII '123456789'.
        begin: crc_selftest
            reg [7:0] check;integer ascii;
            check=0;for(ascii=49;ascii<=57;ascii=ascii+1)check=crc8(check,ascii);
            if(check!==8'ha1)$fatal(1,"Independent CRC check failed");
        end
        test_id=0;reset_all();packet(0,0,-1,0);expect_response(0,0);
        test_id=1;packet(1,0,-1,0);expect_response(1,11);
        test_id=2;reset_all();packet(1,1,-1,0);expect_error(6);
        if(accepted_frames||received_count||response_pulses)$fatal(1,"Bad CRC generated a success response");
        test_id=3;reset_all();uart_byte('h5a,1);uart_byte('ha5,1);uart_byte('h99,1);expect_error(4);
        test_id=4;reset_all();uart_byte('h5a,1);uart_byte('ha5,1);uart_byte(1,1);uart_byte('h93,1);expect_error(5);
        test_id=5;reset_all();uart_byte('h5a,1);uart_byte(0,1);expect_error(3);
        test_id=6;reset_all();uart_byte('h5a,1);uart_byte('ha5,1);uart_byte(1,1);uart_byte('h94,1);uart_byte(0,1);
        repeat(270)tick();expect_error(7);
        test_id=7;reset_all();uart_byte('h55,0);repeat(12)tick();expect_error(2);
        test_id=8;reset_all();assert_estop();packet(1,0,-1,0);
        if(accepted_frames||received_count||safety_permit)$fatal(1,"E-stop accepted a request");
        test_id=9;reset_all();uart_byte('h5a,1);uart_byte('ha5,1);uart_byte(1,1);assert_estop();
        test_id=10;reset_all();packet(1,0,-1,0);wait(dut.core_busy);repeat(20)tick();assert_estop();
        if(response_pulses||received_count)$fatal(1,"Aborted inference generated a response");
        @(negedge clk);estop=0;repeat(5)tick();packet(1,0,-1,0);expect_response(1,0);
        if(error_code!==1||!error_flags[1])$fatal(1,"Recovery erased error history");
        test_id=11;reset_all();packet(1,0,-1,0);wait(response_valid);#1;assert_estop();
        repeat(100)tick();if(received_count>=11)$fatal(1,"E-stop allowed a complete response");
        test_id=12;reset_all();packet(1,0,-1,0);wait(received_count==5);assert_estop();
        repeat(100)tick();if(received_count>=11)$fatal(1,"Mid-response E-stop left a CRC-valid success");
        test_id=13;reset_all();packet(1,0,-1,0);wait(dut.core_busy);uart_byte('h5a,1);expect_error(9);
        if(response_pulses||received_count)$fatal(1,"Busy collision generated a response");
        test_id=14;reset_all();packet(1,0,-1,0);wait(received_count==2);uart_byte('h5a,1);expect_error(9);
        test_id=15;reset_all();packet(1,0,-1,0);expect_response(1,0);
        wait(!safety_permit);#1;expect_error(11);
        test_id=16;reset_all();packet(1,0,-1,0);expect_response(1,0);
        uart_byte('h5a,1);if(safety_permit)$fatal(1,"New frame retained old residual permission");
        uart_byte(0,1);expect_error(3);
        test_id=17;reset_all();uart_byte('h5a,1);packet(1,0,-1,0);expect_response(1,0);
        test_id=18;reset_all();uart_byte('h00,1);uart_byte('hff,1);packet(2,0,-1,0);expect_response(2,0);
        test_id=19;packet(3,0,-1,0);expect_response(3,11);
        test_id=20;reset_all();packet(1,0,-1,0);wait(dut.core_busy);
        force dut.core_done=0;wait(error_code==12);#1;release dut.core_done;expect_error(12);
        test_id=21;reset_all();packet(1,0,-1,0);wait(dut.core_busy);
        force dut.core_fault=1;repeat(3)tick();release dut.core_fault;expect_error(10);
        test_id=22;reset_all();packet(1,0,-1,0);wait(dut.core_busy);repeat(30)tick();reset_all();
        packet(1,0,-1,0);expect_response(1,0);
        // Exhaustive field-address boundary rejection: both limits for all 74 inputs.
        // These are protocol-invalid vectors, whereas the core suite separately
        // exercises all int16 values as arithmetic stress inputs.
        $dumpoff;
        for(field_id=0;field_id<74;field_id=field_id+1)begin
            for(boundary=0;boundary<2;boundary=boundary+1)begin
                test_id=1000+field_id*2+boundary;reset_all();
                packet(1,0,field_id,boundary ? 16'sd257 : (field_id<64 ? -16'sd1 : -16'sd257));
                expect_error(8);
                if(accepted_frames||received_count||response_pulses)
                    $fatal(1,"Invalid normalized field %0d generated success",field_id);
            end
        end
        // Signed transport extrema must never wrap into a legal normalized input.
        test_id=1200;reset_all();packet(1,0,73,-16'sd32768);expect_error(8);
        test_id=1201;reset_all();packet(1,0,0,16'sd32767);expect_error(8);
        $dumpon;test_id=1300;reset_all();packet(1,0,-1,0);expect_response(1,0);
        checkpoint("final_recovery");
        // Boundary-state injection avoids billions of packets. The actual
        // increment paths still run through valid UART, bad CRC and raw E-stop.
        test_id=1400;reset_all();
        @(negedge clk);dut.accepted_frames=32'hfffffffe;
        packet(1,0,-1,0);expect_response(1,0);
        if(accepted_frames!==32'hffffffff)$fatal(1,"Accepted count did not reach MAX");
        checks=checks+1;checkpoint("accepted_counter_reaches_max");
        test_id=1401;packet(2,0,-1,0);expect_response(2,11);
        if(accepted_frames!==32'hffffffff)$fatal(1,"Accepted audit counter wrapped");
        checks=checks+1;checkpoint("accepted_counter_saturates");
        test_id=1402;reset_all();
        @(negedge clk);dut.rejected_frames=32'hfffffffe;
        packet(1,1,-1,0);expect_error(6);
        if(rejected_frames!==32'hffffffff)$fatal(1,"Rejected count did not reach MAX");
        checks=checks+1;checkpoint("rejected_counter_reaches_max");
        test_id=1403;packet(1,1,-1,0);expect_error(6);
        if(rejected_frames!==32'hffffffff)$fatal(1,"CRC reject audit counter wrapped");
        checks=checks+1;checkpoint("rejected_counter_crc_saturates");
        test_id=1404;assert_estop();
        if(rejected_frames!==32'hffffffff)$fatal(1,"E-stop audit counter wrapped");
        checks=checks+1;checkpoint("rejected_counter_estop_saturates");
        test_id=1405;reset_all();
        if(accepted_frames!==0||rejected_frames!==0||safety_permit)
            $fatal(1,"Reset did not clear saturated counters and residual permit");
        checks=checks+1;case_count=case_count+1;checkpoint("saturated_counters_reset_clear");
        test_id=1406;packet(1,0,-1,0);expect_response(1,0);
        if(accepted_frames!==1||rejected_frames!==0)
            $fatal(1,"Post-reset counting or recovery failed");
        checks=checks+1;checkpoint("post_saturation_reset_recovery");
        $fclose(checkpoints);
        $display("PASS uart: %0d directed transactions, %0d assertions, all 74 field range boundaries, independent wire decode, E-stop/parser/inference/TX/reset/stale/watchdog recovery",case_count,checks);
        $finish;
    end
endmodule
