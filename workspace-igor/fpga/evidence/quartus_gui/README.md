# Bukti asli GUI Quartus Parallel8

Ditangkap **19 Oktober 2026** menggunakan Computer Use `@oai/sky`, langsung dari jendela **Quartus Prime Standard 25.1**. Project yang terbuka: `fpga/experiments/parallel8/igor_src_policy.qpf`, device **5CSEBA6U23I7**. Screenshot JPEG disimpan dari byte asli yang dikembalikan API screenshot, tanpa penambahan angka, rekonstruksi tabel, overlay atau compositing.

Ini menggantikan screenshot browser `../parameter_screenshots/` sebagai **bukti GUI Quartus**. Folder browser lama tetap merupakan tampilan dokumen, bukan GUI Quartus.

## Parameter dan panel sumber

| Parameter yang dibuktikan | Nilai / cakupan | Screenshot asli |
|---|---|---|
| Full implementation berhasil | Flow Status Successful; identitas project Parallel8 terlihat pada title bar | [18_flow_summary_fullwidth.jpg](18_flow_summary_fullwidth.jpg) |
| Device / tool / top | Cyclone V 5CSEBA6U23I7; Quartus 25.1std; igor_src_policy_de10_nano | [02_fitter_summary.jpg](02_fitter_summary.jpg) |
| ALM core murni | **2.402,7 ALMs needed**, inclusive hierarchy core | [03_core_uart_alms.jpg](03_core_uart_alms.jpg) |
| ALM core + UART policy | **3.300,7 ALMs needed**, inclusive policy hierarchy | [04_core_uart_resources.jpg](04_core_uart_resources.jpg) |
| ALUT core / core+UART / board | **2.324 / 3.359 / 3.364** | [04_core_uart_resources.jpg](04_core_uart_resources.jpg) |
| Register core / core+UART / board | **4.747 / 6.272 / 6.277** | [04_core_uart_resources.jpg](04_core_uart_resources.jpg) |
| Block memory core dan core+UART | **524.288 bit, 64 M10K**, tidak bertambah dengan UART | [04_core_uart_resources.jpg](04_core_uart_resources.jpg) |
| DSP core dan core+UART | **8 DSP**, tidak bertambah dengan UART | [04_core_uart_resources.jpg](04_core_uart_resources.jpg) |
| UART RX / TX leaf | **38,3 / 21,5 ALM**; bukan seluruh biaya parser dan buffer policy | [03_core_uart_alms.jpg](03_core_uart_alms.jpg) |
| ALM top dan packing | **3.303 / 41.910 (8% dibulatkan)**; final placement 4.113, packing recovery 823, unavailable 13 | [05_resource_usage_logic.jpg](05_resource_usage_logic.jpg) |
| RAM capacity dan implementation bits | **64/553 M10K; 524.288 bit data; 655.360 bit implementation** | [06_memory_dsp_capacity.jpg](06_memory_dsp_capacity.jpg) |
| Bentuk parameter memory | **8 logical ROM banks**, masing-masing depth 4.096 × width 16, single clock | [07_ram_summary.jpg](07_ram_summary.jpg) |
| DSP mapping | **8 fixed-point signed multipliers / 8 DSP blocks** | [08_dsp_summary.jpg](08_dsp_summary.jpg) |
| Pin / PLL / HPS resource | **13/314 pins**, **0/6 PLL**, HPS peripherals yang dilaporkan tidak dipakai oleh top ini | [02_fitter_summary.jpg](02_fitter_summary.jpg), [06_memory_dsp_capacity.jpg](06_memory_dsp_capacity.jpg) |
| Clock operasi | **50 MHz**, period **20 ns** | [10_clock_50mhz.jpg](10_clock_50mhz.jpg) |
| Worst setup / hold dan TNS | **+5,647 / +0,119 ns**, design-wide TNS nol | [09_multicorner_timing.jpg](09_multicorner_timing.jpg) |
| Fmax slow 1100mV 100°C | **69,67 MHz**, bukan frekuensi clock operasi | [11_fmax_slow100c.jpg](11_fmax_slow100c.jpg) |
| Power Maximum total / dynamic / static / IO | **937,55 / 50,36 / 865,80 / 21,40 mW** | [12_power_summary_maximum.jpg](12_power_summary_maximum.jpg) |
| Kondisi power yang dimuat | **Maximum device characteristics, Tj 100°C** | [13_power_operating_conditions.jpg](13_power_operating_conditions.jpg) |
| Power hierarchy core / UART | Panel asli dan footnote tool terlihat; global static leakage tidak dialokasikan seluruhnya ke hierarchy | [14_power_hierarchy.jpg](14_power_hierarchy.jpg) |
| Power confidence | **Low**, vectorless estimation; simulation toggle input tidak tersedia pada run ini | [15_power_confidence.jpg](15_power_confidence.jpg), [12_power_summary_maximum.jpg](12_power_summary_maximum.jpg) |
| Pin planning / fitted location | Seluruh **13 nodes**, clock, KEY0/1, UART, LED; 3.3-V LVTTL | [16_pin_planner.jpg](16_pin_planner.jpg) |
| Archived Typical power | **476,18 total / 50,36 dynamic / 413,27 static / 12,55 IO mW** | [17_typical_power_original_report.jpg](17_typical_power_original_report.jpg) |

Screenshot **17** berasal dari **Text Editor bawaan Quartus**, membuka file laporan asli `experiments/parallel8/artifacts/power/typical/igor_src_policy.pow.summary`. Ini bukan panel Power Analyzer aktif: database report yang saat ini dimuat berisi run Maximum/Tj100. Isi file Typical tidak diketik ulang atau diubah.

Angka pecahan ALM adalah atribusi packing/hierarchy tool. Nilai luar tanda kurung mencakup sub-entity, sedangkan angka dalam kurung hanya entity itu sendiri; catatan asli Quartus terlihat di bawah tabel. Karena itu core murni memakai 2.402,7, bukan angka exclusive 2.293,1 yang mengecualikan submodul aktivasi.

## Batas bukti

- Screenshot memperlihatkan **laporan kompilasi yang sudah tersimpan**, bertanggal 17 Oktober 2026. Membuka GUI dan menangkap screenshot tidak berarti kompilasi baru pada 19 Oktober.
- Core-only adalah atribusi hierarchy dalam full board build, bukan hasil fitting standalone yang baru.
- **Persentase presisi** 5,7330% dan 7,8757%, overhead 898 ALM, serta pembagian persentase area adalah hitungan dari angka laporan. Jangan melabeli tabel perhitungan sebagai panel GUI Quartus. Quartus menampilkan beberapa persentase yang dibulatkan.
- **Latensi 6.916 siklus / 0,13832 ms** berasal dari pengujian RTL dan jadwal core; tidak ada panel laporan Quartus yang membuktikan angka siklus itu dalam capture ini. Clock 50 MHz dan timing closure didukung screenshot 09–11.
- **Area ASIC Tiny Tapeout dalam mm²** bukan keluaran Quartus. Bukti fisiknya berasal dari laporan flow ASIC, sehingga tidak dimasukkan sebagai screenshot GUI Quartus. Design ASIC impor dan PPO Parallel8 tetap berbeda cakupan.
- Power adalah estimasi tool dengan confidence yang terlihat pada GUI; bukan pengukuran arus board.

RTL, QSF dan SOF tidak diubah. Pemeriksaan `check_parallel8()` dan hash handoff SOF harus tetap cocok dengan acceptance setelah inspeksi GUI. Tidak ada tindakan programming ulang, gerak motor, atau rebuild selama sesi pengambilan screenshot ini.

## Traceability

- `capture_session.json`: judul jendela, panel, waktu UTC, screenshot ID dan metode capture.
- `*.uia.txt`: accessibility tree asli dari observasi jendela yang sama; dapat membantu mencari nilai tanpa mengetik ulang gambar.
- `manifest.json`: SHA256 screenshot, accessibility text dan laporan sumber.
- `QUARTUS_GUI_EVIDENCE.zip`: screenshot asli, metadata dan indeks ini.

Analisis angka lengkap: [AREA_CORE_UART_ASIC.md](../../docs/AREA_CORE_UART_ASIC.md).
