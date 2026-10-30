@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -File "..\scripts\program_fpga.ps1" -Project source_policy_parallel8 -AutoSelect -Program %*
set "program_result=%errorlevel%"
if not "%program_result%"=="0" echo Programming did not complete. Read the error and evidence path above.
pause
exit /b %program_result%
