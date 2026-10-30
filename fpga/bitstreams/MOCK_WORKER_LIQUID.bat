@echo off
title IGOR - Mock Worker dan Liquid
cd /d "%~dp0..\.."
set "IGOR_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%IGOR_PYTHON%" set "IGOR_PYTHON=python"
"%IGOR_PYTHON%" -u "%~dp0..\scripts\mock_worker_and_corrupt_frames.py" --hardware
set "IGOR_MOCK_EXIT=%errorlevel%"
echo Result: %IGOR_MOCK_EXIT% [0=PASS, nonzero=FAIL]. Physical FPGA required; motors mocked.
pause
exit /b %IGOR_MOCK_EXIT%
