# GARDA DE10-Lite timing constraints.
# MAX10_CLK1_50 (PIN_P11): 50 MHz board oscillator, the only clock in the design.
create_clock -name clk50 -period 20.000 [get_ports {MAX10_CLK1_50}]
# Core clock: PLL output, 45 MHz (50 x 9 / 10). VGA stays on clk50.
derive_pll_clocks
derive_clock_uncertainty
# The only core -> VGA transfer is the 2-flop synchronised observation bus.
set_clock_groups -asynchronous -group [get_clocks {clk50}] -group [get_clocks {*pll*clk[0]}]

# Asynchronous human/serial inputs. Each is synchronised in RTL (reset_sync,
# sw_meta/sw_sync, UART meta/sync) or is the deliberately unsynchronised
# combinational E-stop path (KEY[1]) that removes motor permission immediately.
set_false_path -from [get_ports {KEY[*]}]
set_false_path -from [get_ports {SW[*]}]
set_false_path -from [get_ports {JP1_RX[*]}]

# Slow board outputs (LEDs, 7-segment) and the UART TX line (8.68 us bit time at
# 115200 baud). No external timing relationship exists for these pins.
set_false_path -to [get_ports {LEDR[*] HEX0[*] HEX1[*] HEX2[*] HEX3[*] HEX4[*] HEX5[*] JP1_TX[*] VGA_R[*] VGA_G[*] VGA_B[*] VGA_HS VGA_VS}]
