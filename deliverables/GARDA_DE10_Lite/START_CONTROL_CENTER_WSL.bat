@echo off
rem GARDA FPGA Control Center / Physical AI simulator (desktop shortcut target).
rem Usage: START_CONTROL_CENTER_WSL.bat [page]     page = "" (Control Center) or "sim.html" (Physical AI)
rem For USB-TTL adapters Windows cannot drive (e.g. clone PL2303), the adapter is passed to WSL.
rem One-time, as Administrator:  usbipd bind --hardware-id 067b:2303
rem The USB-Blaster stays on Windows; only the UART adapter is attached to WSL.
setlocal
set HERE=%~dp0
set PAGE=%~1
title GARDA Control Center
rem Already running? Just open the page.
powershell -NoProfile -Command "try{(Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8770/api/state)|Out-Null;exit 0}catch{exit 1}"
if %errorlevel%==0 ( start "" "http://127.0.0.1:8770/%PAGE%" & exit /b 0 )
echo Starting WSL...
start "GARDA WSL keep-alive" /min wsl -e bash -c "exec sleep infinity"
timeout /t 3 /nobreak >nul
echo Attaching the USB-UART adapter to WSL (if plugged in)...
usbipd attach --wsl --hardware-id 067b:2303 2>nul
timeout /t 3 /nobreak >nul
wsl -u root -e bash -c "chmod 666 /dev/ttyUSB* 2>/dev/null; ls /dev/ttyUSB* 2>/dev/null || echo 'No /dev/ttyUSB* yet: plug in the adapter, then use Connect in the page.'"
for /f "usebackq delims=" %%P in (`wsl wslpath -a "%HERE:~0,-1%"`) do set WSLHERE=%%P
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8770/%PAGE%"
echo Control Center: http://127.0.0.1:8770/   Physical AI: http://127.0.0.1:8770/sim.html   (close this window to stop)
wsl -e bash -c "cd '%WSLHERE%' && P=''; [ -e /dev/ttyUSB0 ] && P='--serial /dev/ttyUSB0'; exec python3 -u host/garda_service.py --port 8770 $P"
