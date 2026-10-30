@echo off
setlocal
title IGOR - Parallel8 JP7 UART Programming
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\program_jp7.ps1"
set "program_result=%errorlevel%"
echo.
pause
exit /b %program_result%
