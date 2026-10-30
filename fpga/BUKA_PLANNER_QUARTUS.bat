@echo off
setlocal
set "GARDA_QUARTUS=D:\Quartus-Program\quartus\bin64\quartus.exe"
if defined QUARTUS_ROOTDIR set "GARDA_QUARTUS=%QUARTUS_ROOTDIR%\bin64\quartus.exe"
if not exist "%GARDA_QUARTUS%" (
  echo Quartus tidak ditemukan. Set QUARTUS_ROOTDIR atau buka QPF secara manual.
  echo Proyek: %~dp0fpga_de10_nano\quartus\garda.qpf
  exit /b 1
)
start "" "%GARDA_QUARTUS%" "%~dp0fpga_de10_nano\quartus\garda.qpf"
