@echo off
title IGOR - Testing ABC
cd /d "%~dp0..\.."
echo Close LiDAR live logger before starting. Every run creates timestamped logs.
set "IGOR_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%IGOR_PYTHON%" set "IGOR_PYTHON=python"
"%IGOR_PYTHON%" "%~dp0..\scripts\run_laptop_abc.py" %*
set "IGOR_ABC_EXIT=%errorlevel%"
echo.
echo Result: %IGOR_ABC_EXIT% [0=PASS, 1=FAIL, 2=INCOMPLETE hardware or physical evidence]
pause
exit /b %IGOR_ABC_EXIT%
