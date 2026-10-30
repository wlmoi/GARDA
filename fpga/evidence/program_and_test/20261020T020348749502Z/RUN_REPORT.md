# Pengulangan setelah hub siap — 20 Oktober 2026

FPGA berhasil diprogram kembali; Quartus melaporkan **0 error dan 0 warning**. Launcher Desktop gabungan dijalankan sampai selesai. Tidak ada perintah motor.

Suite: **13 PASS, 1 FAIL, 6 unresolved**; **53 test software PASS**.

- RTL 256 pola PASS.
- FPGA fisik 256 pola / 768 output PASS, 0 LSB error.
- UART numerik dan empat rejection/recovery test PASS; datalogger PASS. Rincian hasil ada di log tahap.
- STM32 COM9 melalui hub: **7.433 byte, 629 frame CRC-valid, nol bad CRC**; 600 type-8 length-7 dan 29 type-0 length-3; **0 frame IMU type-7** selama 30 detik. Koneksi USB/data STM berfungsi, tetapi kebutuhan telemetry IMU belum terpenuhi.
- LiDAR COM17: identitas dan health OK, Express Scan menerima **394 rotasi**, nol byte resinkronisasi. Hanya **16–23 titik jarak valid/rotasi**, sehingga tidak ada rotasi yang memenuhi heuristik kualitas proyek ≥80 titik dan span >300 derajat; scan_ok=false. Komunikasi berhasil tidak sama dengan kualitas pengukuran yang cukup. Penyebab kualitas optik/fisik tidak ditetapkan oleh tes ini.
- Pemantauan read-only USB merekam **35 snapshot** dengan **2 variasi inventaris**. Inventaris awal COM9/17/18; snapshot terakhir pada 09:07:14 WIB kembali hanya COM17, setelah summary run selesai pada 09:07:10 WIB. Tahap FPGA/UART/logger telah melaporkan PASS sebelum wrapper selesai. Periksa timestamp usb_presence.jsonl untuk urutan yang tepat; interval polling lima detik tidak membuktikan kestabilan kontinu.
- Test security-auth yang disebut dokumen belum tersedia, serta acceptance robot fisik A/B/C tetap unresolved.

Bukti: `summary.json`, `programming.log`, `testing.log`, `usb_presence.jsonl`, `scenario/summary.json`, `scenario/sensors/summary.json`, dan log masing-masing tahap. Hasil preflight tidak diubah menjadi PASS.
