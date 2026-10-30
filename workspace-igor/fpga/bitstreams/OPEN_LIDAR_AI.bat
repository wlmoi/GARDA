@echo off
title IGOR - LiDAR AI Live
cd /d "%~dp0..\.."
echo Real LiDAR input logger. Close other programs using the LiDAR COM port.
echo Auto-detect COM; repeat 30-second captures; Ctrl+C to stop.
set "IGOR_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%IGOR_PYTHON%" set "IGOR_PYTHON=python"
"%IGOR_PYTHON%" -u "%~dp0..\scripts\lidar_ai_reader.py" --scan-mode express --repeat --location "Robot - operator location unspecified" %*
pause
