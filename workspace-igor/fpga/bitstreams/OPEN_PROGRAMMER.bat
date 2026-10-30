@echo off
setlocal
cd /d "%~dp0"
set "quartus_gui=D:\Quartus-Program\quartus\bin64\quartus_pgmw.exe"
if not exist "%quartus_gui%" (
  echo Quartus Programmer was not found at "%quartus_gui%".
  echo Open igor_src_policy_parallel8.cdf from your Quartus Programmer instead.
  pause
  exit /b 1
)
start "" "%quartus_gui%" "%~dp0igor_src_policy_parallel8.cdf"
