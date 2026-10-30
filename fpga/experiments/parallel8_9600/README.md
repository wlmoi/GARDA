# Parallel8 UART 9600 baud

Varian terpisah dari Parallel8; clock tetap 50 MHz, baud UART 9600 8N1.
Core/model, format paket, pin JP1 RX/TX dan pengamanan tetap sama.
Perubahan RTL hanya parameter BAUD pada board wrapper.

Divider: round(50,000,000/9600) = 5208 siklus per bit.
Baud aktual = 9600.6144 (sekitar +0.0064%).
Request 153 byte sekitar 159.375 ms; response 11 byte sekitar 11.458 ms.
RX timeout 20 ms dihitung antar-byte, bukan durasi seluruh paket.
Result timeout 20 ms lebih panjang daripada pengiriman response 11.458 ms.
Timeout host tetap 1 detik setelah TX selesai.

## Jetson

Salin `tools/install_igor_uart_9600.py` ke Jetson:

```bash
python3 install_igor_uart_9600.py ~/igor_ws
cd ~/igor_ws
python3 src/igor_pipeline/scripts/uart_test.py --baud 9600 --iter 50
```

Installer membackup script lama dan memasang varian default 9600.
Lepas KEY1 dan tekan/lepas KEY0 sebelum pengujian.

Expected residual: `[-0.1796875, 0.234375, 0.1328125]`.
Expected RX: `5a a5 02 06 d2 ff 3c 00 22 00 61`.
Expected summary: sent 50, received 50, dropped 0.
50 transaksi memerlukan minimal sekitar 8.55 detik, ditambah overhead.

## Build dan programming dari root workspace

```powershell
Set-Location fpga/experiments/parallel8_9600
& 'D:/Quartus-Program/quartus/bin64/quartus_sh.exe' --flow compile igor_src_policy_9600
```

Project: `igor_src_policy_9600.qpf`; SOF: `output_files/igor_src_policy_9600.sof`.
Hasil uji RTL: `verification/simulation.log`.
`tools/program_uart9600.py --program` memeriksa hasil build, timing,
simulasi dan chain aktual sebelum konfigurasi, lalu menyimpan receipt/log
di `fpga/evidence/current_programming/uart9600_<UTC>`.
SOF ini mengganti konfigurasi SRAM saat ini dan hilang setelah power-off.
Programming sukses tidak dengan sendirinya membuktikan UART Jetson berhasil.
