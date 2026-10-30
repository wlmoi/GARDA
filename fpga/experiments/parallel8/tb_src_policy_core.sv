`timescale 1ns/1ps
module tb_src_policy_core;
    localparam N=`VECTOR_COUNT, A=`ACTIVATION_COUNT;
    reg clk=0; always #10 clk=~clk;
    reg rst_n=0,load_input=0,start=0,abort=0;
    reg [6:0] input_index=0;
    reg signed [15:0] input_value=0;
    reg [1:0] output_index=0;
    wire signed [15:0] output_value;
    wire busy,done,fault,saturated;
    wire [3:0] error_code;
    wire [31:0] latency_cycles;
    igor_src_policy_core dut(clk,rst_n,load_input,input_index,input_value,
        start,abort,output_index,output_value,busy,done,fault,error_code,
        latency_cycles,saturated);
    reg signed [15:0] observations[0:N*74-1];
    reg signed [15:0] expected[0:N*3-1];
    reg signed [15:0] expected_h1[0:N*128-1],expected_h2[0:N*64-1];
    reg expected_sat[0:N-1];
    reg [43:0] activation_inputs[0:A-1];
    reg [19:0] activation_expected[0:A-1];
    reg signed [39:0] activation_accumulator;
    reg activation_output;
    wire signed [15:0] activation_value;
    wire activation_saturated;
    igor_src_policy_activation activation(activation_accumulator,activation_output,
        activation_value,activation_saturated);
    integer test_id=0,cycle=0,checkpoints,checks=0,vector_id,i,j,phase;
    always @(posedge clk) cycle<=cycle+1;
    always @(posedge clk) begin
        #2;
        if (rst_n && (busy || fault || abort) && output_value!==0)
            $fatal(1,"Output was not masked while busy/fault/abort");
    end
    task checkpoint;
        input [255:0] name;
        begin
            $fdisplay(checkpoints,"%0d,%0t,%0d,%0s,%0d,%0d,%0d,%0d,%0d,%0d",
                cycle,$time,test_id,name,busy,done,fault,error_code,$signed(output_value),latency_cycles);
        end
    endtask
    task tick; begin @(posedge clk); #1; end endtask
    task reset_core;
        begin
            @(negedge clk);rst_n=0;load_input=0;start=0;abort=0;
            repeat(3) tick();
            @(negedge clk);rst_n=1;tick();
            if(busy||done||fault||output_value!==0) $fatal(1,"Reset did not clear core");
        end
    endtask
    task load_frame;
        input integer vector_number;
        begin
            for(j=0;j<74;j=j+1)begin
                @(negedge clk);load_input=1;input_index=j;
                input_value=observations[vector_number*74+j];tick();
            end
            @(negedge clk);load_input=0;
        end
    endtask
    task launch;
        begin @(negedge clk);start=1;tick();@(negedge clk);start=0;end
    endtask
    task expect_fault;
        input [3:0] code;
        begin
            tick();
            if(!fault||busy||done||error_code!==code||output_value!==0)
                $fatal(1,"Expected fault %0d, got fault=%0d code=%0d",code,fault,error_code);
            checks=checks+1;checkpoint("rejected");
        end
    endtask
    initial begin
        #500000000;
        $fatal(1,"Global core regression timeout");
    end
    initial begin
        $dumpfile("core.vcd");
        $dumpvars(1,tb_src_policy_core);$dumpvars(1,dut);
        checkpoints=$fopen("core_checkpoints.csv","w");
        $fdisplay(checkpoints,"cycle,time_ps,test_id,event,busy,done,fault,error_code,output_q8_8,latency_cycles");
        $readmemh("../../verification/src_policy/artifacts/observations.hex",observations);
        $readmemh("../../verification/src_policy/artifacts/expected.hex",expected);
        $readmemh("../../verification/src_policy/artifacts/hidden1.hex",expected_h1);
        $readmemh("../../verification/src_policy/artifacts/hidden2.hex",expected_h2);
        $readmemh("../../verification/src_policy/artifacts/saturated.hex",expected_sat);
        $readmemh("../../verification/src_policy/artifacts/activation_inputs.hex",activation_inputs);
        $readmemh("../../verification/src_policy/artifacts/activation_expected.hex",activation_expected);
        for(i=0;i<A;i=i+1)begin
            {activation_accumulator,activation_output}=activation_inputs[i][40:0];#1;
            if({activation_saturated,activation_value}!==activation_expected[i][16:0])
                $fatal(1,"Activation case %0d mismatch: acc=%0d output=%0d",i,activation_accumulator,activation_output);
            checks=checks+1;
        end
        for(vector_id=0;vector_id<N;vector_id=vector_id+1)begin
            test_id=vector_id;
            if(vector_id==2)$dumpoff;
            if(vector_id==0)reset_core();
            load_frame(vector_id);launch();
            if(vector_id<2)checkpoint("inference_started");
            wait(done||fault);#1;
            if(fault||busy||latency_cycles!==6916)
                $fatal(1,"Vector %0d: bad completion fault=%0d latency=%0d",vector_id,fault,latency_cycles);
            if(saturated!==expected_sat[vector_id])$fatal(1,"Vector %0d saturation diagnostic mismatch",vector_id);
            for(i=0;i<128;i=i+1)begin
                if(dut.hidden1[i]!==expected_h1[vector_id*128+i])
                    $fatal(1,"Vector %0d h1[%0d]=%0d expected=%0d",vector_id,i,dut.hidden1[i],expected_h1[vector_id*128+i]);
                checks=checks+1;
            end
            for(i=0;i<64;i=i+1)begin
                if(dut.hidden2[i]!==expected_h2[vector_id*64+i])
                    $fatal(1,"Vector %0d h2[%0d] mismatch",vector_id,i);
                checks=checks+1;
            end
            for(i=0;i<3;i=i+1)begin
                output_index=i;#1;
                if(output_value!==expected[vector_id*3+i])
                    $fatal(1,"Vector %0d output[%0d]=%0d expected=%0d",vector_id,i,output_value,expected[vector_id*3+i]);
                checks=checks+1;
            end
            output_index=3;#1;
            if(output_value!==0)$fatal(1,"Invalid output index exposed data");
            if(vector_id<2)checkpoint("bit_exact_complete");
        end
        $dumpon;
        test_id=1000;reset_core();launch();expect_fault(4);
        // Fault is reset-only, including after cancellation.
        @(negedge clk);abort=1;tick();@(negedge clk);abort=0;tick();
        if(!fault)$fatal(1,"Abort cleared a sticky control fault");
        test_id=1001;reset_core();
        @(negedge clk);load_input=1;input_index=74;tick();
        @(negedge clk);load_input=0;expect_fault(1);
        test_id=1002;reset_core();load_frame(0);launch();
        @(negedge clk);load_input=1;input_index=0;tick();
        @(negedge clk);load_input=0;expect_fault(2);
        test_id=1003;reset_core();load_frame(0);launch();launch();expect_fault(3);
        test_id=1004;reset_core();load_frame(0);
        @(negedge clk);start=1;load_input=1;input_index=0;tick();
        @(negedge clk);start=0;load_input=0;expect_fault(5);
        test_id=1005;reset_core();load_frame(0);launch();wait(done);#1;launch();expect_fault(4);
        // Repeating an address cannot fake a complete fresh observation.
        test_id=1006;reset_core();
        for(i=0;i<74;i=i+1)begin
            @(negedge clk);load_input=1;input_index=i==73 ? 0 : i;input_value=0;tick();
        end
        @(negedge clk);load_input=0;launch();expect_fault(4);
        // Cancel separately in every active state; no partial result can survive.
        for(phase=1;phase<=7;phase=phase+1)begin
            test_id=1100+phase;reset_core();load_frame(1);launch();
            wait(dut.state==phase);@(negedge clk);abort=1;#1;
            if(output_value!==0)$fatal(1,"Abort combinational output guard failed");
            tick();@(negedge clk);abort=0;tick();
            if(busy||done||fault||dut.loaded!==0)$fatal(1,"Abort state %0d failed",phase);
            checks=checks+1;checkpoint("aborted_state");
        end
        test_id=1200;reset_core();load_frame(1);launch();repeat(30)tick();reset_core();
        load_frame(1);launch();wait(done);#1;
        if(fault||latency_cycles!==6916)$fatal(1,"Reset recovery failed");
        checkpoint("reset_recovery");checks=checks+1;
        $fclose(checkpoints);
        $display("PASS core: %0d network vectors, %0d activation cases, %0d assertions; all 192 hidden activations and 3 outputs checked per vector",N,A,checks);
        $finish;
    end
endmodule
