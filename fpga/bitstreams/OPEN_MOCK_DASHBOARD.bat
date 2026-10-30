@echo off
title IGOR - FPGA Test Dashboard
cd /d "%~dp0..\.."
set "IGOR_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%IGOR_PYTHON%" set "IGOR_PYTHON=python"
"%IGOR_PYTHON%" -u "%~dp0..\scripts\mock_dashboard.py"
pause
