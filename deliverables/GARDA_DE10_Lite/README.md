# GARDA DE10-Lite deliverables

Your connected board is a **DE10-Lite (MAX 10 10M50DAF484C7G)**.

1. Install MAX 10 device support for Quartus Lite 23.1std (Tools > Install Devices).
2. `.\Build-DE10Lite.ps1` compiles `quartus_de10lite/` (same unmodified GARDA UART RTL + DE10-Lite top and pins) and prints resources, timing, power estimate.
3. `.\Program-FPGA.ps1` programs over JTAG (it picks the built DE10-Lite `.sof` automatically).
4. UART: 3.3 V USB-serial adapter -> Arduino header: adapter TX -> D0 (FPGA RX, PIN_AB5), adapter RX -> D1 (FPGA TX, PIN_AB6), GND -> GND. 115200 8N1.
   Then `uart_explorer\START_UART_EXPLORER.bat`, choose the adapter's COM port, Connect LIVE, enable auto-read, flip switches.

Board behaviour: SW2 = ready inhibit (fault 4), SW3 = protective stop (fault 3), KEY1 = E-stop (fault 2), KEY0 = reset.
LEDR[7:0] = {fault[3:0], done, busy, rst_n, enable}; LEDR8/LEDR9 = UART RX/TX activity.

Status: pin assignments verified against published DE10-Lite pin tables (clock, keys, switches, LEDs, Arduino D0/D1); the project has NOT yet been compiled or programmed, and nothing is confirmed on a physical board. Use a 3.3 V adapter only (the header is not 5 V safe).
`uart_explorer/` is the PC-side tool (see its README and TEST_REPORT).
