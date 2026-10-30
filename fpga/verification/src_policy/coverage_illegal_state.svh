// Supplemental fault injection for the Parallel8 FSM default recovery path.
// Included by the coverage runner in its copied bench, before closing CSV.
// No production RTL is modified. Register upset is intentional test stimulus.
test_id=1300;
reset_core();
@(negedge clk);
force dut.state=4'hf;
tick();
release dut.state;
expect_fault(4'd6);
checkpoint("illegal_state_15_fail_closed");
reset_core();
load_frame(1);launch();wait(done);#1;
if(fault || latency_cycles!==6916)
    $fatal(1,"Illegal-state reset recovery failed");
checks=checks+1;
checkpoint("illegal_state_reset_recovery");
