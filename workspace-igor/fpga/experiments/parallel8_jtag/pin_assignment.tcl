# Terasic DE10-Nano manual, clock Table3-5, KEY Table3-7,
# LEDs Table3-8, GPIO Figure3-20/Table3-10. All external signals 3.3V.
set_location_assignment PIN_V11 -to FPGA_CLK1_50
set_location_assignment PIN_AH17 -to {KEY[0]}
set_location_assignment PIN_AH16 -to {KEY[1]}
set_location_assignment PIN_E8 -to UART_TX
set_location_assignment PIN_W15 -to {LED[0]}
set_location_assignment PIN_AA24 -to {LED[1]}
set_location_assignment PIN_V16 -to {LED[2]}
set_location_assignment PIN_V15 -to {LED[3]}
set_location_assignment PIN_AF26 -to {LED[4]}
set_location_assignment PIN_AE26 -to {LED[5]}
set_location_assignment PIN_Y16 -to {LED[6]}
set_location_assignment PIN_AA23 -to {LED[7]}
foreach port {FPGA_CLK1_50 KEY[0] KEY[1] UART_TX LED[0] LED[1] LED[2] LED[3] LED[4] LED[5] LED[6] LED[7]} {
 set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to $port
}
# Make output electrical settings explicit (Cyclone V 3.3-V LVTTL).
foreach port {UART_TX LED[0] LED[1] LED[2] LED[3] LED[4] LED[5] LED[6] LED[7]} {
 set_instance_assignment -name CURRENT_STRENGTH_NEW 16MA -to $port
 set_instance_assignment -name SLEW_RATE 1 -to $port
}
