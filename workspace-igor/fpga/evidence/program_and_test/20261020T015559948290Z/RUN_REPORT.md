# Program FPGA dan test — hasil 20 Oktober 2026

Launcher Desktop **IGOR - Program FPGA dan Test** berhasil dijalankan melalui target batch yang sama.

- Programming: sukses, Quartus 0 error/0 warning; programming dilakukan sebelum tes, tidak diulang di tengah suite.
- Software: **53 test PASS**; oracle dan **256 pola RTL PASS**.
- FPGA fisik: **256 pola PASS**, 768 output cocok; UART return dan datalogger juga PASS.
- LiDAR: identitas/health/Express Scan PASS, **392 rotasi**, 55 memenuhi gate kualitas, nol byte resinkronisasi.
- STM32 tidak ada pada inventaris preflight. Setelah muncul kembali sebagai COM9, capture tambahan 10 detik menerima **210 frame CRC-valid**, tetapi **0 frame IMU**. Bukti: `late_stm_check/summary.json`.
- Hasil suite asli: **13 PASS, 1 FAIL, 6 unresolved**. Status tidak diubah menjadi PASS oleh pengujian tambahan.
- Test security-auth belum tersedia; physical route, lengkapnya sensor/control trace, dan physical disconnect-stop acceptance belum dilakukan. Tidak ada perintah motor.

File utama: `summary.json`, `programming.log`, `testing.log`, `ports.json`; rincian tahap di `scenario/`. Folder capture FPGA/serial tambahan ditunjuk dari masing-masing log tahap.
