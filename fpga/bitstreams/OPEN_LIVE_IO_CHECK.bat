@echo off
title IGOR - LIVE Input Output Auto Check
cd /d "%~dp0..\.."
echo LIVE INPUT OUTPUT - automatic checks every 1 second
echo Close other FPGA UART and JTAG tools. The COM port is detected automatically.
echo Synthetic test input only. No STM32 or motor commands. Ctrl+C to stop.
python -u "%~dp0..\scripts\fpga_live_check.py" --port auto --interval 1 %*
echo Exit code: %errorlevel%
pause
