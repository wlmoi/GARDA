@echo off
rem GARDA Control Center - native Windows (FTDI / CP210x / CH340 / genuine PL2303 adapters).
rem Requires Python 3 with pyserial:  python -m pip install pyserial
cd /d "%~dp0"
start "" "http://127.0.0.1:8770/"
python host\garda_service.py --port 8770
