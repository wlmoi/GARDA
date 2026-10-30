# Live input/output dan repeat timer

Klik Desktop **IGOR - LIVE Input Output Auto Check**. Terminal langsung mengirim input, menampilkan hasil dan mengulang setiap 1 detik tanpa prompt. Board harus sudah diprogram dengan image observer JP1 pin 1/2. Tutup terminal/logger lain yang menggunakan COM12 atau JTAG; satu aplikasi saja memiliki setiap jalur. Ctrl+C menghentikan loop dan menyimpan ringkasan.

Mode ini **aktif mengirim input sintetis ke FPGA**; berbeda dari logger pasif `fpga_datalogger.py` yang hanya membaca snapshot. Tidak ada input LiDAR atau perintah STM32/motor. Script tidak memprogram ulang atau mengganti mode FPGA. Ini adalah pemeriksaan bench yang diulang, bukan logger robot yang sedang memiliki UART yang sama.

Setiap iterasi menampilkan:

- Waktu lokal dengan zona, lokasi manual jika diberikan, nomor tes dan nama pola.
- Seluruh 74 input signed Q8.8 beserta rentang indeksnya.
- `EXPECTED`: tiga hasil oracle integer dari weights/bias yang sama.
- `OUTPUT`: tiga hasil FPGA yang baru selesai; `None` jika hasil baru tidak terkonfirmasi.
- `ERROR_LSB`: selisih output terhadap oracle; `[0,0,0]` berarti cocok persis pada Q8.8.
- `COMMUNICATION: OK_UART_INPUT_JTAG_OUTPUT`: UART input diterima FPGA dan seq hasil naik tepat satu, dibaca lewat JTAG, mode inferensi dan E-stop tidak aktif.
- `CALCULATION: PASS`: komunikasi tersebut benar, output cocok, dan core melaporkan 6916 siklus.
- `UART_RETURN`: pemeriksaan terpisah atas data balasan yang sudah tersedia di adapter; `NO_REPLY` tidak diubah menjadi klaim UART dua arah lulus. `CRC_AND_VALUE_OK` hanya muncul jika frame balasan valid dan cocok dengan output baru. Data rusak/mismatch menyebabkan gagal.
- Siklus, waktu core dari siklus/50 MHz, dan waktu transaksi host yang terpisah.
- Timer menuju iterasi berikutnya dan ringkasan pada akhir sesi.

Observer menyimpan hasil saat `response_valid`; hasil lama tidak diterima sebagai transaksi baru. Kode FPGA 11 menunjukkan freshness timeout setelah hasil selesai; karena pembacaan JTAG lebih lambat dari lease tersebut, hasil yang sudah dilatch masih dapat dibandingkan tetapi tidak dianggap izin aktuator yang berlaku sekarang.

Input berputar melalui 256 pola tetap/seeded yang sama dengan suite verifikasi, lalu mengulang dari awal. Data ini mencakup zero, baseline, batas domain, impulse dan random; label sintetis tetap tercatat. Komunikasi OK hanya berlaku untuk jalur yang disebutkan dan pola yang diuji.

Log berada pada `fpga/evidence/live_io/<timestamp UTC>/`: `session.json`, `input_output.csv`, `input_output.jsonl`, dan `summary.json`. CSV/JSONL memuat input lengkap, expected, output, selisih, sequence, timestamp, lokasi dan status; JSONL juga menyimpan snapshot mentah dan byte TX/RX. Setiap baris di-flush. Shortcut **IGOR - LIVE Input Output Logs** membuka foldernya. Log perangkat tetap lokal.

Pengaturan alternatif:

```powershell
python fpga/scripts/fpga_live_check.py --interval 2 --location "Lab - meja A"
python fpga/scripts/fpga_live_check.py --count 10 --interval 1
```

Interval adalah target periode dari awal iterasi ke awal berikutnya; transaksi yang lebih lama menunda iterasi berikutnya, tidak dipalsukan menjadi tepat 1 Hz. Tiga kegagalan berurutan menghentikan loop agar masalah koneksi terlihat. Tidak ada fallback ke output software seolah hasil FPGA.
