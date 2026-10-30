@echo off
 title IGOR - Real FPGA Mock Numerical Test
 echo FPGA adapter TX to JP1 pin 1, adapter RX to pin 2, GND pin 12. Jetson disconnected.
 echo Auto-detects FPGA UART port; reads physical results via USB-Blaster JTAG.
 echo Close other JTAG terminals. Board will be programmed with the verified observer image.
 python "%~dp0..\scripts\verify_board_jtag.py" --port auto --program
 echo Test exit code: %errorlevel%
 pause
