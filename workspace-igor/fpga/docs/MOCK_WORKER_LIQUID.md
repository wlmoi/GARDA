# Mock worker steps in close + corrupted wiring frames

Double-click Desktop **IGOR - Mock Worker dan Liquid**. Satu script Python `fpga/scripts/mock_worker_and_corrupt_frames.py` menjalankan kedua skenario, menampilkan expected/actual dan membuat log bertimestamp. Target batch: `fpga/bitstreams/MOCK_WORKER_LIQUID.bat`.

**Tidak memerlukan FPGA, STM32 atau LiDAR terhubung. Tidak membuka port COM/JTAG dan tidak mengirim perintah motor fisik.**

## 1. Worker steps in close

Menjalankan `_control_loop` dari controller aktual pada `fpga/software_integration/src/igor_controller/igor_controller/controller_node.py`, menggunakan fixture ROS/MCU/FPGA yang sudah tersedia di `run_host_regression.py`. Bukan implementasi ulang aturan STOP.

- Command awal nonzero: `vx=0,30 m/s`, `vy=0,20 m/s`, `omega=0,40 rad/s`.
- Policy mock sengaja memberi `[+1,+1,+1]` agar test membuktikan guard tetap menang terhadap action nonzero.
- Simulasi objek di sektor depan LiDAR, background 3,50 m. Jarak: **1,50; 0,40; 0,23; 0,2201; 0,22; 0,2199; 0,21; 0,15; 0,15 m**.
- Empat langkah pertama harus tetap menghasilkan command gerak. Pada lima langkah dengan jarak **≤0,22 m**, ketiga sumbu safe twist dan seluruh empat wheel RPS harus **nol**.
- Test berhenti ketika objek masih dekat; tidak mengklaim latch/reset atau kebijakan restart setelah objek pergi.

Ini mock obstacle proximity, bukan pengenalan manusia. Nol pada command tidak mengukur inersia, stopping distance, stopping time atau keadaan roda fisik. Frekuensi eksekusi script bukan pengukuran deadline loop robot.

## 2. Liquid on the wiring — proxy korupsi digital

Menjalankan testbench RTL existing `fpga/verification/tb_safety_uart.v` pada Icarus, menggunakan RTL planner UART, protocol parser, safety gate dan logger. Tidak mengubah RTL atau menambahkan command ke perangkat.

| Injeksi | Expected |
|---|---|
| CRC byte di-XOR 1 | Accepted commands=0, protocol_fault=1, permit/command nol. |
| Frame sah setelah CRC fault tanpa reset | Tetap ditolak karena protocol fault sticky. |
| Trailer 0x5A menjadi 0x00 | Ditolak. |
| Hanya header 0xA5 lalu berhenti | Timeout dan ditolak. |
| RX low sehingga stop bit invalid | Framing error dan ditolak. |

Kontrol positif memeriksa frame konfigurasi sah sebelum fault dan frame sah kembali setelah reset. Parser yang selalu menolak semua frame tidak dapat meluluskan test ini. Seluruh **39 checkpoint** testbench juga harus lulus; lima kasus fault di atas ditampilkan khusus pada konsol dan JSONL.

`protocol_fault=1` adalah bukti korupsi protokol. `last_fault=4` dalam checkpoint ini adalah fault gate readiness pada setup planner; **bukan** kode CRC=6 milik UART neural yang berbeda. Kedua code map tidak disamakan.

“Liquid” di sini hanya memodelkan byte/bit/frame rusak. Tidak ada cairan, korsleting, overvoltage atau uji ketahanan lingkungan. Worker mock host dan planner RTL adalah dua komponen terpisah; ini bukan acceptance robot/chip end-to-end.

## Hasil dan berkas bukti

Sesi validasi **20 Oktober 2026**, UTC `20261020T021649510056Z`: **9/9 worker steps PASS**, **5/5 corruption cases PASS**, kedua kontrol positif PASS, **39 checkpoint UART PASS**.

Setiap double-click membuat folder `fpga/evidence/mock_disturbances/<UTC>/`:

- `worker_steps.csv` dan `.jsonl`: jarak input, command awal, mock action, output safe twist, empat wheel RPS, expected/actual STOP dan PASS.
- `corrupt_frames.jsonl`: injeksi, expected rejection, checkpoint RTL aktual dan hasil.
- `liquid_rtl/uart_checkpoints.csv`, `uart.vcd`, `compile.log`, `simulation.log`: bukti RTL untuk GTKWave dan inspeksi.
- `liquid_rtl/*_command.json`: command tool dan exit code.
- `summary.json`: hasil kedua test, scope mock dan SHA-256 source.
- `REPORT.md`: ringkasan sesi.

Exit **0=PASS**, **1=FAIL**; jendela terminal tetap terbuka sampai tombol ditekan. Python 3.11, numpy dan Icarus sudah tersedia di laptop ini. Masalah awal Windows Icarus ketika mewarisi stdin `NUL` diselesaikan dengan input pipe kosong pada subprocess; exit code nonzero tetap menghasilkan FAIL, tidak diabaikan. Run gagal awal tetap tersimpan dalam sesi terpisah.

CLI:

```powershell
& "$env:LOCALAPPDATA/Programs/Python/Python311/python.exe" fpga/scripts/mock_worker_and_corrupt_frames.py
pwsh -NoProfile -File fpga/scripts/install_lidar_abc_shortcuts.ps1
```

## Physical FPGA Desktop mode (updated)
The Desktop launcher now requires `--hardware`. Worker observations go through real FPGA inference and exact integer-oracle comparison before the host stop check. `physical_fpga_transactions.jsonl` records the exchanges. The runner also invokes verify_mock_inference.py on physical hardware: 256 numeric vectors plus bad CRC, negative LiDAR, out-of-range tail and truncated frame rejection, each followed by a valid recovery transaction. Results and the detailed evidence directory appear in physical_corrupt_frames.log. Missing hardware or failed exchange prevents overall PASS. The original five planner safety/fault-code tests remain explicitly separate RTL simulation. No water or motor hardware is used. Historical offline results above are not hardware evidence.
