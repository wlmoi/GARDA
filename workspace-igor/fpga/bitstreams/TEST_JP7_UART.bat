@echo off
setlocal
title IGOR - Physical JP7 UART Test
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\test_jp7_uart.ps1" %*
set "test_result=%errorlevel%"
echo.
pause
exit /b %test_result%
