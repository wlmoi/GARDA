@echo off
setlocal
cd /d "%~dp0"
echo IGOR RTL Explorer - iSeeDesignITB
echo Buka http://127.0.0.1:8765
echo Tekan Ctrl+C untuk menghentikan server.
where py >nul 2>nul
if %errorlevel% equ 0 (
  start "" "http://127.0.0.1:8765"
  py -3 -m http.server 8765 --directory dist --bind 127.0.0.1
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 belum tersedia. Instal Python 3, lalu jalankan file ini lagi.
    pause
    exit /b 1
  )
  start "" "http://127.0.0.1:8765"
  python -m http.server 8765 --directory dist --bind 127.0.0.1
)
pause

