@echo off
rem Rebuild the DE10-Lite bitstream with Quartus Prime Lite (auto-detected).
cd /d "%~dp0"
python scripts\build.py %*
