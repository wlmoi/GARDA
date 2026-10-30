@echo off
title IGOR - FPGA Datalogger
cd /d "%~dp0..\.."
echo FPGA to Laptop Datalogger - USB-Blaster JTAG
echo Board harus sudah diprogram image JP1 pins 1/2 monitor.
echo Tidak memprogram ulang board dan tidak mengirim input inferensi.
echo Tutup JTAG terminal lain. Tekan Ctrl+C untuk berhenti dan menyimpan log.
python "%~dp0..\scripts\fpga_datalogger.py" --prompt-location %*
echo Logger exit code: %errorlevel%
pause
