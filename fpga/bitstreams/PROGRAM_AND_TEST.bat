@echo off
title IGOR - Program FPGA dan Test
cd /d "%~dp0..\.."
echo Close other serial and JTAG tools before starting.
echo Programs Parallel8 JP1 pins 1/2, then runs tests. No motor commands.
set "IGOR_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%IGOR_PYTHON%" set "IGOR_PYTHON=python"
"%IGOR_PYTHON%" -u "%~dp0..\scripts\program_and_test.py" %*
set "IGOR_COMBINED_EXIT=%errorlevel%"
echo Result: %IGOR_COMBINED_EXIT% [0=PASS, 1=FAIL, 2=INCOMPLETE]
pause
exit /b %IGOR_COMBINED_EXIT%
