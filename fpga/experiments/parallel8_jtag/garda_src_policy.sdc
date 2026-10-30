create_clock -name FPGA_CLK1_50 -period 20.000 [get_ports FPGA_CLK1_50]
derive_clock_uncertainty
# KEY0 reset assertion async; release passes two registers.
set_false_path -from [get_ports {KEY[0]}]
# KEY1 asserts stop asynchronously. Human input is not clock-related.
set_false_path -from [get_ports {KEY[1]}]
# Board LEDs and asynchronous UART have no source-synchronous receiver.
set_false_path -to [get_ports {LED[*] UART_TX}]
