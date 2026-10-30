# Program FPGA lalu test — satu double-click

Shortcut Desktop: **IGOR - Program FPGA dan Test**.

Target: `fpga/bitstreams/PROGRAM_AND_TEST.bat`, menjalankan `fpga/scripts/program_and_test.py`.

1. Deteksi adapter FPGA berdasarkan VID/PID, bukan nomor COM tetap.
2. Program image Parallel8 monitor yang sudah tersedia melalui USB-Blaster. Helper lama memeriksa compile, timing, pin planning dan kesamaan source core sebelum programming. Bila programming gagal, suite tidak dimulai.
3. Jalankan full scenario runner dengan sensor Express Scan selama 30 detik, unit test, oracle, RTL 256 pola, numerik FPGA fisik, balasan UART dan datalogger. Tidak ada programming kedua di tengah suite.
4. Tampilkan hasil dan simpan `programming.log`, `testing.log`, inventaris port serta `summary.json` di `fpga/evidence/program_and_test/<UTC>/`. Log tahap suite berada di `scenario/`; capture mendetail dari verifier lama tetap berada di folder bukti masing-masing yang ditunjuk log.

Koneksi: TX adapter → JP1 pin 1 (RX FPGA), RX adapter ← JP1 pin 2 (TX FPGA), GND → pin 12. Gunakan level 3,3 V; tanpa VCC adapter. USB-Blaster digunakan untuk programming dan pembacaan JTAG. LiDAR langsung ke laptop, memakai konfigurasi Express dan driver CH340 3.4 yang sudah disetujui. STM32 dan adapter FPGA juga harus terhubung. Tutup aplikasi lain yang memiliki serial/JTAG.

Script tidak membangun ulang RTL, tidak mengubah pin, tidak memasang driver otomatis dan tidak mengirim perintah motor. Perpindahan konektor USB dapat membuat Windows memilih driver CH340 lain; bila perlu gunakan helper driver yang sudah tersedia dan periksa versi aktif.

Exit 0 = seluruh pemeriksaan PASS; 1 = ada kegagalan; 2 = belum lengkap. Tidak adanya IMU, test security-auth yang belum tersedia, atau acceptance robot A/B/C yang belum dijalankan tetap dilaporkan. Fixture rute bukan bukti robot bergerak 5×4 m; logger pasif bukan stream inferensi baru. Lihat `testing_scenario.md` dan `TESTING_SCENARIO_RUNNER.md` untuk batas cakupan.

CLI:

```powershell
& "$env:LOCALAPPDATA/Programs/Python/Python311/python.exe" fpga/scripts/program_and_test.py
pwsh -NoProfile -File fpga/scripts/install_lidar_abc_shortcuts.ps1
```

Opsi `--sensor-seconds 1..30` mengganti durasi capture. Default launcher gabungan adalah 30 detik. Durasi default runner lama tetap lima detik jika dijalankan langsung.
