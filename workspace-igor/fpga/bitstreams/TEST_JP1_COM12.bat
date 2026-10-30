@echo off
setlocal
title IGOR - Uji UART COM12 JP1 Pin 1-2
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\test_jp1_com12.ps1" %*
set "uart_result=%errorlevel%"
echo.
echo Test exited with code %uart_result%.
echo Press any key to close.
pause >nul
exit /b %uart_result%
