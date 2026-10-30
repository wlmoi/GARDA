@echo off
setlocal
set "IGOR_QUARTUS=D:\Quartus-Program\quartus\bin64\quartus.exe"
if defined QUARTUS_ROOTDIR set "IGOR_QUARTUS=%QUARTUS_ROOTDIR%\bin64\quartus.exe"
if not exist "%IGOR_QUARTUS%" (
  echo Quartus tidak ditemukan. Set QUARTUS_ROOTDIR atau buka QPF secara manual.
  echo Proyek: %~dp0fpga_de10_nano\src_policy\igor_src_policy.qpf
  exit /b 1
)
start "" "%IGOR_QUARTUS%" "%~dp0fpga_de10_nano\src_policy\igor_src_policy.qpf"
