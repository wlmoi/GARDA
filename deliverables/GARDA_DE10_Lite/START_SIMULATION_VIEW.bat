@echo off
rem Opens the Control Center in SOFTWARE SIMULATION replay (no hardware needed).
cd /d "%~dp0"
title GARDA Simulation View
powershell -NoProfile -Command "try{(Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8770/api/state)|Out-Null;exit 0}catch{exit 1}"
if %errorlevel%==0 ( start "" "http://127.0.0.1:8770/?source=sim" & exit /b 0 )
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8770/?source=sim"
python host\garda_service.py --port 8770
