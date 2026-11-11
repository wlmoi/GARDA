// GARDA DE10-Lite core clock: 45 MHz from the MAX 10 PLL (50 MHz x 9 / 10).
//
// Why: the unmodified GARDA core's longest path (rollout best_score -> candidate
// selector -> safety gate -> fault logger / UART response snapshot) needs ~20.4 ns
// at the Slow 1200 mV 85 C corner of a MAX 10 C7 device, so 50 MHz fails sign-off by
// ~0.4 ns. 45 MHz (22.2 ns) closes timing at every corner without touching the core.
// All time-based constants are rescaled in garda_de10_lite_top so their real-time
// values (20 ms lease, 100 ms UART gap, baud rate, watchdog ms) are unchanged.
//
// Simulation: define GARDA_SIM_PLL to pass the input clock straight through.
`timescale 1ns/1ps
`default_nettype none
module garda_clock(input wire clk50,output wire clk,output wire locked);
`ifdef GARDA_SIM_PLL
assign clk=clk50;assign locked=1'b1;
`else
wire [4:0] clks;
altpll #(
 .bandwidth_type("AUTO"),.clk0_divide_by(10),.clk0_duty_cycle(50),.clk0_multiply_by(9),.clk0_phase_shift("0"),
 .compensate_clock("CLK0"),.inclk0_input_frequency(20000),.intended_device_family("MAX 10"),
 .lpm_hint("CBX_MODULE_PREFIX=garda_pll"),.lpm_type("altpll"),.operation_mode("NORMAL"),.pll_type("AUTO"),
 .port_activeclock("PORT_UNUSED"),.port_areset("PORT_UNUSED"),.port_clkbad0("PORT_UNUSED"),.port_clkbad1("PORT_UNUSED"),
 .port_clkloss("PORT_UNUSED"),.port_clkswitch("PORT_UNUSED"),.port_configupdate("PORT_UNUSED"),.port_fbin("PORT_UNUSED"),
 .port_inclk0("PORT_USED"),.port_inclk1("PORT_UNUSED"),.port_locked("PORT_USED"),.port_pfdena("PORT_UNUSED"),
 .port_phasecounterselect("PORT_UNUSED"),.port_phasedone("PORT_UNUSED"),.port_phasestep("PORT_UNUSED"),
 .port_phaseupdown("PORT_UNUSED"),.port_pllena("PORT_UNUSED"),.port_scanaclr("PORT_UNUSED"),.port_scanclk("PORT_UNUSED"),
 .port_scanclkena("PORT_UNUSED"),.port_scandata("PORT_UNUSED"),.port_scandataout("PORT_UNUSED"),.port_scandone("PORT_UNUSED"),
 .port_scanread("PORT_UNUSED"),.port_scanwrite("PORT_UNUSED"),.port_clk0("PORT_USED"),.port_clk1("PORT_UNUSED"),
 .port_clk2("PORT_UNUSED"),.port_clk3("PORT_UNUSED"),.port_clk4("PORT_UNUSED"),.port_clk5("PORT_UNUSED"),
 .port_clkena0("PORT_UNUSED"),.port_clkena1("PORT_UNUSED"),.port_clkena2("PORT_UNUSED"),.port_clkena3("PORT_UNUSED"),
 .port_clkena4("PORT_UNUSED"),.port_clkena5("PORT_UNUSED"),.port_extclk0("PORT_UNUSED"),.port_extclk1("PORT_UNUSED"),
 .port_extclk2("PORT_UNUSED"),.port_extclk3("PORT_UNUSED"),.self_reset_on_loss_lock("OFF"),.width_clock(5)
) pll(.inclk({1'b0,clk50}),.clk(clks),.locked(locked),
 .activeclock(),.areset(1'b0),.clkbad(),.clkena({6{1'b1}}),.clkloss(),.clkswitch(1'b0),.configupdate(1'b0),
 .enable0(),.enable1(),.extclk(),.extclkena({4{1'b1}}),.fbin(1'b1),.fbmimicbidir(),.fbout(),.fref(),.icdrclk(),
 .pfdena(1'b1),.phasecounterselect({3{1'b1}}),.phasedone(),.phasestep(1'b1),.phaseupdown(1'b1),.pllena(1'b1),
 .scanaclr(1'b0),.scanclk(1'b0),.scanclkena(1'b1),.scandata(1'b0),.scandataout(),.scandone(),.scanread(1'b0),
 .scanwrite(1'b0),.sclkout0(),.sclkout1(),.vcooverrange(),.vcounderrange());
assign clk=clks[0];
`endif
endmodule
`default_nettype wire
