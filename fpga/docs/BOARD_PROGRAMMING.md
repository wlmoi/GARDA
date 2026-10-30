# DE10-Nano: project, programming dan bukti fisik

Jalankan seluruh perintah halaman ini dari **root `igor_ws`**. Source RTL,
project, pin planning, `.sof`, dan bukti berada di **`fpga/`**. `src/` dan
`peruri-iseedesign/` tetap referensi. Pertahankan struktur lengkap `fpga/`
karena QSF dan ROM memakai path relatif.

## Pilih project dan protokol yang sama

Untuk core cepat **6.916 siklus / 138,32 us**, gunakan paket
[programming Parallel8](../bitstreams/README.md) dan
[PROGRAM_PARALLEL8.bat](../bitstreams/PROGRAM_PARALLEL8.bat).
Launcher memilih `igor_src_policy_parallel8.sof`, memeriksa checksum/build,
dan mendeteksi posisi FPGA secara otomatis tanpa mengasumsikan urutan HPS.
Perintah ekuivalen: `powershell -NoProfile -File fpga/scripts/program_fpga.ps1 -Project source_policy_parallel8 -AutoSelect -Program`.
CDF siap dibuka ada di `fpga/bitstreams/igor_src_policy_parallel8.cdf`;
CDF chain aktual disimpan sebagai `detected_board.cdf` setelah identifikasi.

**Update 18 Oktober 2026, 12:58 WIB: programming Parallel8 berhasil.**
Chain `DE-SoC [USB-1]`: `SOCVHPS` @1 bypass dan `5CSEBA6` @2 dikonfigurasi.
Quartus melaporkan `Configuration succeeded -- 1 device(s) configured`,
0 error / 0 warning. Bukti: [log programming](../evidence/current_programming/20261018T0558125221956Z/programming.log)
dan [receipt](../evidence/current_programming/20261018T0558125221956Z/inspection.json).
Ini bukti konfigurasi FPGA, belum pengujian fungsi UART atau robot fisik.

| Tujuan | Project | SOF di bawah `fpga/` | UART |
|---|---|---|---|
| PPO mengikuti software 74→128→64→3 | [igor_src_policy.qpf](../fpga_de10_nano/src_policy/igor_src_policy.qpf) | `fpga_de10_nano/src_policy/output_files/igor_src_policy.sof` | 921600 8N1, observasi 74 nilai, CRC8 Maxim |
| Planner peta + gate + event logger | [igor.qpf](../fpga_de10_nano/quartus/igor.qpf) | `fpga_de10_nano/quartus/output_files/igor.sof` | 115200 8N1, frame 8 byte, CRC8 polinomial 0x07 |

Keduanya menargetkan **Cyclone V SE `5CSEBA6U23I7`**, clock **50 MHz**.
Satu image mengganti konfigurasi sebelumnya. Residual source-policy masih
memerlukan host blending/kinematika; image itu belum menyatukan costmap planner
dan izin motor. Alat `capture_hardware_safety.py` khusus image **planner**.
Arsitektur, batas klaim dan seluruh pin dijelaskan di
[README source-policy](../fpga_de10_nano/src_policy/README.md) dan
[README planner](../fpga_de10_nano/README.md).

## Inspeksi JTAG

Riwayat pemeriksaan lokal 16 Oktober 2026 mendeteksi **Quartus Prime Standard
25.1std.0 Build 1129** dan mengembalikan **No JTAG hardware available** untuk
kedua project. Log historis ada pada
[current_programming](../evidence/current_programming/). Belum ada programming,
readback atau pengujian robot fisik yang dibuktikan pada pemeriksaan tanggal itu.
Status terbaru adalah programming Parallel8 berhasil sebagaimana receipt di atas.

Nyalakan board, sambungkan USB berlabel **USB-Blaster/JTAG**, lalu jalankan:

```powershell
powershell -NoProfile -File .\fpga\scripts\program_fpga.ps1
powershell -NoProfile -File .\fpga\scripts\program_fpga.ps1 -Project planner
```

Default script hanya menginventarisasi kabel/JTAG. Setiap run membuat folder
baru `fpga/evidence/current_programming/<UTC>/` dengan `jtag_inventory.log`,
`jtag_chain.log`, dan `inspection.json`. Tanpa kabel hasilnya
`hardware_available=false`, `hardware_programmed=false`. Instalasi lain dapat
dipilih dengan `-QuartusBin 'C:\...\quartus\bin64'`.

Periksa nomor kabel, IDCODE dan urutan device pada `jtag_chain.log`. Chain
SoC dapat memuat FPGA dan **SOCVHPS**; jangan mengasumsikan posisi FPGA 1.
`-DeviceIndex` adalah **satu-based**, sesuai help lokal
`quartus_pgm --help=operation`. `-Cable` adalah nomor atau nama lengkap kabel.

Setelah membaca chain, ganti `N` dan `K` dengan nomor kabel dan posisi FPGA:

```powershell
# TEMPLATE: ganti N dan K dengan angka dari chain aktual.
powershell -NoProfile -File .\fpga\scripts\program_fpga.ps1 -Project source_policy -Cable N -DeviceIndex K
```

Script menjalankan Auto Detect pada kabel terpilih dan menolak posisi yang
tidak teridentifikasi sebagai `5CSEBA6`. Nama bypass ambigu menyebabkan
penolakan; gunakan GUI/CDF setelah memeriksa chain.

## Programming CLI atau GUI

Manifest pada [current_release/manifest.json](../evidence/current_release/manifest.json)
harus memuat project/SOF yang tepat, SHA256 dan ukuran SOF. Ikuti freeze
release pada README `fpga/` jika source/build berubah. Manifest mengikat file
lokal ke paket; ia tidak membuktikan FPGA sedang menjalankan file itu.

Tambahkan `-Program -WhatIf` untuk meninjau operasi konfigurasi. Untuk benar-benar
mengisi SRAM setelah seleksi diinspeksi, jalankan template dengan angka aktual:

```powershell
powershell -NoProfile -File .\fpga\scripts\program_fpga.ps1 -Project source_policy -Cable N -DeviceIndex K -Program
# Untuk image planner, ganti -Project menjadi planner.
```

Script memeriksa device QSF `5CSEBA6U23I7`, project/SOF manifest, SHA256,
ukuran file, kabel dan posisi FPGA. Sebelum operasi `P`, script juga menjalankan
`python fpga/scripts/freeze_release.py --check` untuk memeriksa seluruh source
dan build pada release. Pilih interpreter lain dengan `-Python` bila perlu.
Hanya `-Program` menerbitkan operasi `P`;
device lain mendapat `S` (skip/bypass). Hasil sukses disimpan pada
`programming.log` dan `hardware_programmed=true`. Field
`uart_function_verified=false` tetap memerlukan pengujian UART terpisah.

Alternatif GUI Quartus 25:

1. **File → Open Project**, pilih QPF pada tabel.
2. **Assignments → Device**, cocokkan `5CSEBA6U23I7`.
   **Assignments → Pin Planner** membaca assignment bawaan; cocokkan report
   `.pin` dari Fitter.
3. Jika source berubah, **Processing → Start Compilation**. Review Fitter,
   Assembler dan Timing Analyzer build tersebut sebelum memakai SOF-nya.
4. **Tools → Programmer → Hardware Setup**, pilih kabel dan mode **JTAG**.
5. **Auto Detect**, pilih baris FPGA Cyclone V. Biarkan HPS/device lain bypass.
   Gunakan **Change File** pada baris FPGA untuk memilih SOF project terkait.
6. Centang **Program/Configure**, klik **Start**. Simpan log dan screenshot
   hasil **100% Successful** beserta SHA256 SOF.
7. Tekan-lepas **KEY0** untuk reset, lalu periksa UART project yang sama.

SOF adalah konfigurasi **SRAM sementara** dan hilang setelah power-off.
Prosedur ini tidak memprogram flash boot, HPS image atau SD card. Untuk GUI,
simpan CDF hasil Auto Detect board aktual. Paket tidak mengasumsikan urutan
JTAG tertentu melalui CDF statis.

Jika kebijakan PowerShell mesin menolak file `.ps1`, gunakan GUI Quartus di
atas atau shell yang sudah diizinkan oleh administrator. Prosedur programming
tidak memerlukan perubahan kebijakan PowerShell sistem.

## Wiring fabric UART

| Sambungan | Pin header/ball |
|---|---|
| TX adapter → UART_RX FPGA | JP1 pin 1, V12 |
| RX adapter ← UART_TX FPGA | JP1 pin 2, E8 |
| Common GND | JP1 pin 12 atau 30 |
| KEY0 reset aktif rendah | AH17 |
| KEY1 E-stop demo aktif rendah | AH16 |

Gunakan **TTL 3,3 V**, 8N1, tanpa flow control. Cocokkan penanda pin 1, silang
TX/RX dan sambungkan GND; VCC adapter tidak diperlukan. Sumber pin/manual dan
seluruh LED tersedia pada README project. Fabric UART ini berbeda dari UART
USB HPS; USB-Blaster hanya menyediakan JTAG.

Planner: **SW2=0**, **SW3=0**, lepas KEY1 lalu reset KEY0. LED0=gate enable,
LED1=reset dilepas, LED2=busy, LED3=done, LED7:4=fault. Arti LED source-policy
berbeda; gunakan tabel README-nya.

Pilih port adapter FPGA yang benar:

```powershell
python -m pip install pyserial
python -m serial.tools.list_ports -v
```

## Akuisisi safety khusus image planner

Ganti `COM5` dengan port fabric UART aktual. Perintah awal berikut memeriksa
status serta ROM dan jaringan neural **legacy**, bukan source-policy:

```powershell
python .\fpga\fpga_de10_nano\host\igor_uart.py --port COM5 status
python .\fpga\fpga_de10_nano\host\igor_uart.py --port COM5 rom-check
python .\fpga\fpga_de10_nano\host\igor_uart.py --port COM5 nn-test
```

Simpan command line, output dan kode exit. Gunakan satu pemilik port UART
per waktu agar frame tidak tersisip. Alat capture mencatat frame respons
mentah, output `v/omega`, gate, fault aktif, event count, retained cause, UTC
dan waktu monotonik. Bracket status/logger mendeteksi perubahan saat membaca.
Ini **sampling UART, bukan snapshot atomik per siklus**. Latensi E-stop
asinkron memerlukan logic analyzer/oscilloscope atau SignalTap ber-clock.

| Kasus | Persiapan | Assertion/bukti |
|---|---|---|
| H01 E-stop ditahan | Reset, tekan-tahan KEY1 | enable=0, v=omega=0, fault=retained=2, event>0; foto tombol |
| H02 write peta di luar transaksi | Reset, jangan begin map | Inject opcode 2; zero, fault=retained=5; bandingkan baseline |
| H03 payload RUN tidak valid | Reset, KEY1 lepas, SW2/3=0 | Inject RUN payload=1; zero, fault=retained=4, invalid_command=1, event bertambah |
| H04 kandidat blocked/unknown | Upload dan RUN scene terkait | Zero; log scene/hash/upload, status dan fault aktual |
| H05 hasil/peta kedaluwarsa | RUN valid, hentikan refresh | Zero setelah lease/freshness; analyzer sebelum/sesudah batas |
| H06 E-stop saat RUN/RESULT | Fixture mengulang scene valid | Baseline enabled-nonzero, lalu zero/fault2; analyzer KEY1+enable+output |

H01: tahan KEY1 selama capture. Gunakan nama file baru; capture menolak
menimpa bukti yang sudah ada:

```powershell
python .\fpga\verification\capture_hardware_safety.py --project planner --port COM5 --case H01_estop_held --output .\fpga\evidence\hardware\H01.jsonl --seconds 3 --expect-zero --expected-fault 2 --bitstream .\fpga\fpga_de10_nano\quartus\output_files\igor.sof
```

H02/H03 mengirim fault injection hanya ketika `--inject` ditulis eksplisit.
Reset sebelum setiap kasus:

```powershell
python .\fpga\verification\capture_hardware_safety.py --project planner --port COM5 --case H02_invalid_map_write --output .\fpga\evidence\hardware\H02.jsonl --inject invalid-map-write --expect-zero --expected-fault 5 --bitstream .\fpga\fpga_de10_nano\quartus\output_files\igor.sof
python .\fpga\verification\capture_hardware_safety.py --project planner --port COM5 --case H03_invalid_run_payload --output .\fpga\evidence\hardware\H03.jsonl --inject invalid-run-payload --expect-zero --expected-fault 4 --require-event-advance --bitstream .\fpga\fpga_de10_nano\quartus\output_files\igor.sof
```

Tambahkan `--jtag-evidence <path-inspection.json>` untuk merekam hash log
programming. SOF/log yang diberikan operator merupakan provenance, bukan
configuration readback. PASS tanpa `--expect-zero`/`--expected-fault` hanya
menyatakan frame berhasil diperoleh. H02 setelah reset sudah dapat memiliki
fault5 karena belum ada peta; itu belum membuktikan transisi dari gerak aman.

Peta 128×128 membutuhkan 16.384 write. UART per transaksi tidak dapat menjaga
map freshness **20 ms** dengan upload ulang penuh; demo host bersifat one-shot.
Jangan menjalankan host kedua untuk refresh pada port sama. H05/H06 memerlukan
fixture/transport yang memenuhi freshness dan baseline aktif; sebelum tersedia,
status fisiknya tetap terbuka. E-stop yang ditahan sebelum query membuktikan
keadaan aman tersampling, bukan waktu berhenti dari kondisi bergerak.

## Berkas acceptance

Satu folder baru per uji menyimpan board/revisi/wiring, project dan SOF SHA256,
manifest, log programmer, raw JSONL UART, input/scene dan hash, analyzer trace,
foto/video fixture, command line, exit code dan observasi operator. Bedakan
output FPGA, RPS STM32 dan gerak roda. Gunakan
[checklist lengkap](IMPLEMENTATION_READINESS.md) untuk penerimaan.

Keandalan alat capture dapat diuji tanpa hardware:

```powershell
python .\fpga\verification\test_capture_hardware_safety.py
powershell -NoProfile -File .\fpga\verification\test_program_fpga.ps1
```

Sepuluh tes fixture memeriksa CRC/request, short write, frame rusak/truncated,
salah opcode/marker, output nonnol, enable, signed omega, fault/retained cause,
counter dan bracket berubah. Delapan kasus wrapper memakai executable palsu
terisolasi di `.runtime/`: FPGA pada posisi 2/HPS posisi 1, inspection, WhatIf,
penolakan HPS, kabel/index hilang, hash salah, full release check gagal, dan
argumen programming eksplisit. Executable Quartus asli tidak dipanggil oleh
tes wrapper. Hasil fixture bukan bukti board fisik.

