@echo off
cd /d "%~dp0"
python -m pip install pyserial >nul 2>nul
start "" http://127.0.0.1:8780
python explorer.py --port 8780
