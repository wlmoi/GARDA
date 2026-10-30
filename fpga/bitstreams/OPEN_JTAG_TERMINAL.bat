@echo off
setlocal
title IGOR - JTAG UART Terminal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\open_jtag_terminal.ps1" -ProgramJtagImage %*
set "jtag_result=%errorlevel%"
echo.
echo JTAG terminal exited with code %jtag_result%.
echo Press any key to close this window.
pause >nul
exit /b %jtag_result%
