# Uji numerik Parallel8 pada board

Klik shortcut Desktop **IGOR - Uji Numerik FPGA 256 Pola**. Launcher berada di `fpga/bitstreams/TEST_MOCK_INFERENCE_COM12.bat` dan menjalankan `fpga/scripts/verify_board_jtag.py --port COM12 --program`.

## Sambungan dan alur pengujian

- USB-Blaster tetap terpasang untuk programming dan pembacaan hasil JTAG.
- TX adapter COM12 → JP1 pin 1 (RX FPGA / V12).
- RX adapter COM12 ← JP1 pin 2 (TX FPGA / E8), GND → JP1 pin 12. Level 3,3 V; tanpa VCC adapter. Jetson dilepas dari kedua pin UART ini.
- Tutup terminal JTAG lain. Lepaskan KEY1; tekan-lepas KEY0 bila reset diperlukan.
- COM12 beroperasi pada 921600 baud, 8N1, tanpa flow control.

Input adalah data sintetis; output yang dibandingkan harus berasal dari FPGA fisik. Host mengirim 74 nilai Q8.8 melalui UART. Core menjalankan jaringan 74→128→64→3 dengan delapan lane MAC. Observer menangkap tiga action 16-bit saat `response_valid`, lalu menaikkan penghitung `seq`. Host membaca snapshot melalui JTAG dan mensyaratkan `seq` naik tepat satu, `accepted` naik satu, latency 6916 siklus, serta ketiga output identik dengan oracle integer.

Observer hanya menambahkan telemetry di luar core. Source core dan delapan bank weights/bias diperiksa identik dengan Parallel8 yang diterima sebelumnya. Image observer berbeda dari SOF asli; SHA-256 image aktif dicatat terpisah bersama receipt programming. `program_uart_monitor.ps1` memeriksa kompilasi, timing, pad, simulasi observer, dan identitas core sebelum programming.

**Jalur input COM12 dan jalur baca JTAG adalah dua jalur berbeda. Kelulusan suite ini tidak membuktikan RX adapter COM12 menerima balasan UART.** Diagnostik sebelumnya mendeteksi frame UART masuk dan inferensi selesai, sementara balasan COM12 masih kosong. Pengujian ini memungkinkan pemeriksaan perhitungan tanpa menganggap jalur balik itu sudah pulih.

## Kriteria dan cakupan

256 pola terdiri dari 8 pola batas/baseline, 84 impulse full-scale, 84 impulse 1 LSB, 64 random dengan seed tetap, dan 16 pengulangan. Setiap pola memeriksa 3 output: total 768 perbandingan exact. Rentang LiDAR adalah 0..256; sepuluh input bertanda berada pada -256..256.

Oracle memulai accumulator dari bias × 256, menjumlahkan input × weights, melakukan floor division 256, ReLU dan clamp pada hidden layer, serta clamp -256..256 pada output. Quantization sumber dibandingkan dengan enam export layer, delapan bank ROM dan oracle referensi kedua. Target error adalah **0 LSB terhadap model integer Q8.8 yang sama**; ini bukan klaim error nol terhadap model floating point.

Pada 50 MHz, 6916 siklus = **138,32 µs = 0,13832 ms**, memenuhi target <0,16 ms untuk core. Waktu host/UART/JTAG bukan latency core dan tidak boleh dipakai sebagai penggantinya.

Hasil disimpan lokal di `fpga/evidence/mock_board_jtag/<timestamp>/`: `identity.json`, `transactions.jsonl`, `summary.json`. Status PASS memerlukan 256 transaksi lengkap tanpa mismatch. Setiap transaksi menyimpan input, expected, actual, snapshot sebelum/sesudah dan sequence; snapshot lama tidak diterima sebagai hasil baru. Kegagalan menghentikan suite dan menghasilkan exit code gagal. Data perangkat tidak otomatis dipublikasikan.

Simulasi terpisah: `python fpga/scripts/verify_mock_inference.py --rtl-sim`. Testbench `fpga/verification/tb_mock_parallel8.sv` menguji Verilog core yang sama dengan 256 pola/768 output dan memeriksa done, fault dan latency. Suite UART asli (`verify_mock_inference.py --port COM12`) tetap tersedia untuk memeriksa jalur balik UART dan penolakan frame invalid; keberhasilannya merupakan pengujian terpisah.

Ini merupakan pengujian terarah dan random yang dapat diulang, bukan pembuktian seluruh kombinasi input, validasi motor, atau sign-off ASIC.
