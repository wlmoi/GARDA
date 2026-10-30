create_clock -name FPGA_CLK1_50 -period 20.000 [get_ports FPGA_CLK1_50]
derive_clock_uncertainty
# KEY signals are asynchronous reset inputs; deassertion is synchronized.
set_false_path -from [get_ports {KEY[*]}]
# LED indicators have no clocked external receiver; their pads are observable.
set_false_path -to [get_ports {LED[*]}]
