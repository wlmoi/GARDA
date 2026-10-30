@echo off
setlocal
title IGOR - STM COM9 and FPGA COM12 Verification
python "%~dp0..\scripts\verify_serial_links.py" %*
set "verify_result=%errorlevel%"
echo.
pause
exit /b %verify_result%
