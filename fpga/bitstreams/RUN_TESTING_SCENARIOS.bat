@echo off
title IGOR - Testing Scenarios
cd /d "%~dp0..\.."
echo IGOR software, RTL and real FPGA scenario checks
echo Requires COM12 wiring and USB-Blaster. Close other JTAG/serial tools.
echo Programs the observer image. Does not open STM COM9 or command robot motion.
echo Physical A/B/C remain incomplete until supervised Jetson trials supply evidence.
python "%~dp0..\scripts\run_testing_scenarios.py" %*
set "IGOR_TEST_EXIT=%errorlevel%"
echo.
echo Result exit code: %IGOR_TEST_EXIT%  [0=PASS, 1=FAIL, 2=INCOMPLETE]
pause
exit /b %IGOR_TEST_EXIT%
