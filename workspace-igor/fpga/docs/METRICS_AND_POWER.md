# Resource, area, latensi, kuantisasi, dan power — beserta sumber nilainya

Tanggal analisis: **17 Oktober 2026**. Desain utama mengikuti README workspace dan bobot `src`: **PPO 74→128→64→3**, target **DE10-Nano 5CSEBA6U23I7, 50 MHz**. Planner/gate dan neural 24-input legacy merupakan profil berbeda.

**Hasil power policy dalam analisis yang dijalankan berada pada ratusan mW:** 464,21 mW pada model Typical dengan ambient 25°C; 812,05 mW pada model Maximum/Tj 85°C; 925,69 mW pada model Maximum/Tj 100°C. Ini estimasi FPGA post-fit dengan confidence **Low**, bukan pengukuran daya board atau jaminan semua kondisi operasi. Angka tidak diturunkan secara manual agar memenuhi target.

## Ringkasan yang boleh dipakai

| Besaran | Policy utama 74-input | Jenis bukti / batas |
|---|---:|---|
| ALM | **3.249 / 41.910 = 7,7523%** | Fitter post-fit; tampilan Quartus membulatkan menjadi 8%. |
| Register | **5.996** | Register hasil fitting, bukan jumlah neuron. |
| M10K | **64 / 553 = 11,5732%** | Blok memori FPGA; resource area tersendiri. |
| DSP | **1 / 112 = 0,8929%** | Blok DSP FPGA; bukan area satu multiplier ASIC dalam mm². |
| Block-memory bits | **524.288 bit = 64 KiB** | Nilai data-memory pada Fitter; 18.051 word parameter aktif = 36.102 byte; ROM dipad menjadi 32.768×16 bit. |
| FPGA area | **Resource utilization di atas** | Tidak menjumlahkan persen ALM, RAM dan DSP menjadi satu persen area. |
| ASIC area, mm² | **BELUM TERSEDIA** | Belum ada pemetaan current PPO ke library/PDK dan implementasi fisik ASIC. |
| Latensi inferensi | **54.348 siklus = 1,08696 ms** | Counter simulasi dan rumus jadwal FSM pada 50 MHz; hanya inferensi valid yang selesai. |
| Budget ideal core + UART | **2,85816 ms** | Hitungan komponen pada divider UART aktual 54; tidak termasuk parser/load/gap/USB/OS/ROS; bukan RTT fisik. |
| Mismatch RTL vs integer oracle | **0 teramati** | 236 vektor; 45.312 hidden values dan 708 output dibandingkan. Bukan kesamaan bit dengan representasi FP32. |
| Output error maksimum vs floating reference | **0,0145717638971 = 3,73037156 LSB** | 153 vektor normalisasi valid / 459 output; Python FP64 memakai koefisien sumber FP32 dan input Q8.8 yang sama. |
| MAE / RMSE output | **0,00362498421469 / 0,00426786892476** | Seluruh 459 output valid; bukan rata-rata error maksimum per vektor. |
| Power total Typical | **464,21 mW** | 38,51 dynamic + 413,17 static + 12,53 I/O; vectorless estimate, HPS tidak dimodelkan. |
| Power total Maximum/Tj 85°C | **812,05 mW** | 38,51 dynamic + 752,16 static + 21,38 I/O; model kondisi berbeda. |
| Power total Maximum/Tj 100°C | **925,69 mW** | 38,51 dynamic + 865,80 static + 21,38 I/O; bukan hasil ukur panas board. |

File angka terstruktur: [metrics.json](../evidence/current_metrics/metrics.json). **Setiap angka mempunyai sumber, nomor baris, satuan dan SHA256** pada [metric_evidence.csv](../evidence/current_metrics/metric_evidence.csv). Gambar ringkasan berlabel: [policy](../evidence/current_metrics/source_policy_metrics.png) dan [planner](../evidence/current_metrics/planner_metrics.png). Gambar ini adalah visualisasi data laporan, bukan screenshot GUI.

## 1. Resource dan area: nilai diambil dari mana?

Source utama: [igor_src_policy.fit.summary](../fpga_de10_nano/src_policy/output_files/igor_src_policy.fit.summary).

| Field persis pada report | Baris | Nilai mentah | Cara memakainya |
|---|---:|---|---|
| `Logic utilization (in ALMs)` | 8 | `3,249 / 41,910 ( 8 % )` | Area logic FPGA dalam satuan ALM. Persen presisi dihitung 3249/41910×100. |
| `Total registers` | 9 | `5996` | Register hasil implementation. |
| `Total block memory bits` | 12 | `524,288 / 5,662,720 ( 9 % )` | Pemakaian data-memory menurut report. |
| `Total RAM Blocks` | 13 | `64 / 553 ( 12 % )` | Pemakaian blok M10K; granularity berbeda dari bit memori. |
| `Total DSP Blocks` | 14 | `1 / 112 ( < 1 % )` | DSP yang benar-benar terpasang setelah fitting. |

Identitas build dan SHA SOF: [source_policy.json](../evidence/current_builds/source_policy.json). SHA SOF policy saat analisis: `fb9fcd28136b647492d2284fef82beca34b97f8300ce0579c25e0745fa88cf4a`. Script menolak laporan jika source, model, SOF atau laporan compile tidak cocok dengan receipt.

Untuk pembanding yang berbeda fungsi, [planner fit summary](../fpga_de10_nano/quartus/output_files/igor.fit.summary) memberikan **5.048 ALM, 1.650 register, 131 M10K, 10 DSP**. Angka ini tidak digabungkan dengan policy seolah sudah satu top terintegrasi. Menggabungkan kedua desain memerlukan build gabungan baru; jumlah resource tidak otomatis merupakan penjumlahan sederhana karena sharing/optimisasi/routing.

### Arti “area estimation” pada FPGA dan ASIC

ALM/M10K/DSP adalah **proxy area implementasi FPGA yang didukung tool**. “8% ALM” tidak berarti 8% luas die, tidak berarti 8% seluruh chip kosong, dan tidak dapat dikalikan dengan luas paket untuk memperoleh area logika dalam mm².

Untuk angka ASIC yang dapat dipertanggungjawabkan diperlukan setidaknya:

1. Target PDK/library proses dan versi corner yang dinyatakan.
2. Netlist **model current 74-input**, dipetakan ke standard cells; ROM/SRAM/multiplier juga harus mempunyai implementasi/macro yang dihitung.
3. Report cell area, memory macro area dan floorplan/utilization yang jelas; area core dan area die dibedakan.
4. Untuk estimasi fisik, placement/routing beserta timing/clock/power grid serta hash input dan tool.

Angka historis gate kecil 684 generic cells bukan area PPO saat ini. Tidak mengarang gate-equivalent atau mm² dari 3.249 ALM. `asic_area_mm2` pada JSON sengaja `null` dengan alasan, bukan nol.

## 2. Latensi: counter, clock, dan rumus independen

Source nilai: [results.json](../verification/src_policy/artifacts/results.json), field `latency_cycles=54348` dan `latency_ms_at_50mhz=1.08696`; [core_checkpoints.csv](../verification/src_policy/artifacts/core_checkpoints.csv) mencatat siklus start/done. Contoh test 1: cycle **54923 → 109271**, selisih **54348**. Gunakan kolom cycle; selisih timestamp CSV dapat menyertakan perbedaan fase `#1` pada testbench.

Clock target ditetapkan pada baris 1 [igor_src_policy.sdc](../fpga_de10_nano/src_policy/igor_src_policy.sdc): period **20 ns**, sehingga 50 MHz.

```text
T_core = cycles / clock_hz
       = 54348 / 50000000 s
       = 1.08696 ms
```

Rumus jadwal dari [FSM core](../rtl/igor_src_policy/igor_src_policy_core.v): setiap neuron mempunyai 3 siklus per weight (address/wait/MAC), 3 siklus bias dan 1 aktivasi. Dengan 17.856 produk dan 195 neuron:

```text
L1 = 128 × (3 × 74  + 4) = 28928 cycles
L2 =  64 × (3 × 128 + 4) = 24832 cycles
L3 =   3 × (3 × 64  + 4) =   588 cycles
Total                         54348 cycles
```

Rumus harus cocok dengan counter; collector menolak bila berbeda. Latensi tetap ini berlaku untuk transaksi inferensi sah yang selesai, bukan abort/fault yang memang dapat membatalkan lebih awal.

UART nominal 921600 baud memakai divider 54 pada 50 MHz, sehingga aktual sekitar 925925,926 baud. Request 153 byte + response 11 byte, 8N1, membutuhkan **164×10×54/50MHz = 1,7712 ms** serialisasi ideal. Menambahkan kernel memberi **2,85816 ms**, tetapi belum memasukkan load/parser, handshake, gap antarbeam/byte, USB/OS dan ROS. **RTT fisik masih belum diukur.** Budget loop README 50 Hz adalah 20 ms, bukan bukti deadline fisik sudah lulus.

Legacy berbeda: neural 24-input **18.192 siklus / 0,36384 ms** dari [neural_cocotb_results](../verification/neural_cocotb_results.json); DWA **7.938 siklus / 0,15876 ms** dari [scene_cocotb_results](../verification/scene_cocotb_results.json). Jangan menampilkan angka itu sebagai latency PPO 74-input.

## 3. Apa arti “error kuantisasi bit”?

Ada dua pertanyaan yang berbeda:

| Pertanyaan | Jawaban yang tepat | Bukti |
|---|---|---|
| Apakah RTL mengimplementasikan model integer yang ditetapkan dengan benar? | **Tidak ada mismatch teramati** pada 236 vektor, termasuk semua hidden/output yang diperiksa. | `core.log`, `results.json`, oracle integer dan testbench; bukan proof semua input. |
| Seberapa jauh model Q8.8 dari model floating reference? | Ada error kuantisasi numerik, diukur dalam unit aksi dan LSB. | `vectors.json`, per-output CSV dan per-parameter CSV di bawah. |

FP32 dan int16 mempunyai format bit yang berbeda. Membandingkan bit pattern keduanya sebagai Hamming distance tidak mengukur akurasi inferensi. **3,73 LSB bukan berarti “3,73 bit rusak”.** Error flag UART/CRC juga bukan error kuantisasi numerik.

### Resolusi dan error parameter

Q8.8 mempunyai satu LSB **2⁻⁸ = 0,00390625**. Rounding parameter ties-to-even, jika tidak clipping, memberi batas absolut **0,5 LSB = 0,001953125** per parameter. Floor pada requantization accumulator mempunyai error sebelum aktivasi pada interval **(-1, 0] LSB**; error beberapa layer dapat terpropagasi sehingga batas output bukan otomatis 0,5 LSB.

[quantization_parameters.csv](../evidence/current_metrics/quantization_parameters.csv) memuat seluruh **18.051 parameter**: nilai sumber, raw Q8.8, dequantized, signed/absolute error dan flag clipping. Hasil keenam tensor:

| Tensor | Jumlah | Error absolut maksimum | Parameter ter-clipping |
|---|---:|---:|---:|
| W1 | 9472 | 0,00195308029652 | 0 |
| b1 | 128 | 0,00191488862038 | 0 |
| W2 | 8192 | 0,00195287168026 | 0 |
| b2 | 64 | 0,00194790540263 | 0 |
| W3 | 192 | 0,00193862989545 | 0 |
| b3 | 3 | 0,000765766948462 | 0 |

Collector juga membandingkan semua raw parameter tersebut dengan ROM yang benar-benar dideploy, bukan sekadar membuat model kuantisasi lain. Sumber koefisien adalah `src/igor_navigation/igor_navigation/weights/model_weights.json`, dibaca tanpa diubah; [model_provenance.json](../verification/src_policy/artifacts/model_provenance.json) mengikat hash JSON/enam MEM dan ROM.

### Error output pada input valid

Sumber utama: [vectors.json](../verification/src_policy/artifacts/vectors.json), hanya entri `normalized_contract=true`: **153 vektor × 3 = 459 output**. Semua detail dan rumus dapat dihitung ulang dari [quantization_outputs.csv](../evidence/current_metrics/quantization_outputs.csv).

```text
error      = raw_action_Q8_8 / 256 - floating_reference
MAE        = mean(abs(error))
RMSE       = sqrt(mean(error^2))
error_LSB  = error × 256
```

| Besaran | Nilai |
|---|---:|
| Max absolute error keseluruhan | 0,014571763897103157 |
| Max absolute error dalam LSB | 3,730371557658408 |
| MAE seluruh 459 output | 0,0036249842146914963 |
| RMSE seluruh 459 output | 0,004267868924756324 |
| Max vx / vy / omega | 0,01048673606945 / 0,01457176389710 / 0,01194245529258 |
| Max error dibanding rentang penuh [-1,+1], lebar 2 | 0,728588194855% |

Contoh terburuk sampel adalah `normalized_random_18`, axis vy: raw Q8.8 **-23** → **-0,08984375**, floating reference **-0,07527198610289684**; selisih absolut **0,014571763897103157**. Jika menggunakan denominator satu unit, persentasenya 1,45717638971%; jangan mengubah denominator tanpa menyebutkannya.

Reference dihitung dengan **Python FP64 memakai koefisien sumber FP32 dan input yang sudah Q8.8 yang sama**. Ini bukan menjalankan ONNX, bukan total error dari sensor floating sebelum normalisasi/kuantisasi, dan bukan error lintasan robot. Sebanyak 83 vektor lain adalah input stress/arithmetic di luar kontrak normalisasi; tidak dimasukkan ke angka akurasi domain valid. Statistik sampel bukan batas formal semua input legal.

## 4. Power dalam mW: angka yang sah dan asalnya

Saya menjalankan **Quartus Prime Standard 25.1 Power Analyzer** pada hasil fitting yang sama dengan SOF rilis. Tidak menurunkan clock, tegangan atau aktivitas default secara tersembunyi untuk mencapai angka kecil. RTL dan bobot tidak diubah pada analisis metrik ini.

| Profil | Total mW | Core dynamic mW | Core static mW | I/O mW | Asumsi dan kualitas |
|---|---:|---:|---:|---:|---|
| Policy, vectorless Typical | **464,21** | 38,51 | 413,17 | 12,53 | Ambient 25°C; tool menghitung Tj sekitar 27,9°C; default toggle 12,5%; confidence Low. |
| Policy, board-fixture VCD + vectorless | **458,93** | 36,19 | 413,13 | 9,61 | VCD wrapper real 50MHz; hanya 256 node / 2,2% memperoleh toggle dari simulasi, pin 13/13; sisanya diperkirakan. Confidence tetap Low. Fixture memuat fault/reset; bukan workload produksi 50 Hz. |
| Policy, Maximum / Tj 85°C | **812,05** | 38,51 | 752,16 | 21,38 | Junction fixed 85°C, karakteristik Maximum, vectorless, confidence Low. |
| Policy, Maximum / Tj 100°C | **925,69** | 38,51 | 865,80 | 21,38 | Junction fixed 100°C, karakteristik Maximum, vectorless, confidence Low. |
| Planner, vectorless Typical | **504,77** | 71,12 | 414,16 | 19,49 | Desain planner berbeda, default toggle 12,5%, ambient 25°C, confidence Low. |

**Target estimasi total di bawah 1.000 mW terpenuhi pada semua profil yang benar-benar dijalankan di atas.** Maknanya terbatas pada model dan asumsi tersebut; ini bukan garansi board selalu <1 W. “Maximum” adalah pilihan karakteristik model tool pada tegangan/model aktivitas yang dinyatakan, bukan pembuktian seluruh kondisi supply, lingkungan, boot dan periferal. [Grafik komponen power](../evidence/current_metrics/power_estimates.png) menampilkan semua profil policy, termasuk static power yang tidak boleh disembunyikan.

`Core Dynamic` berarti dynamic power **fabric FPGA untuk top yang dikompilasi**, bukan daya neural MAC yang telah diisolasi. Tidak boleh menyebut hanya **38,51 mW** sebagai total power FPGA: pada profil Typical totalnya **464,21 mW**. Power static tetap ada walaupun inferensi sedang idle.

### File bukti mentah dan nomor baris

Setiap summary mempunyai total pada **baris 8**, dynamic **9**, static **10**, I/O **11**, confidence **12**:

- [Policy Typical .pow.summary](../evidence/current_metrics/power/source_policy_vectorless/igor_src_policy.pow.summary), [full .pow.rpt](../evidence/current_metrics/power/source_policy_vectorless/igor_src_policy.pow.rpt), [receipt/perintah/hash](../evidence/current_metrics/power/source_policy_vectorless/receipt.json).
- [Policy VCD .pow.summary](../evidence/current_metrics/power/source_policy_board_fixture_vcd/igor_src_policy.pow.summary), [coverage/assumsi .pow.rpt](../evidence/current_metrics/power/source_policy_board_fixture_vcd/igor_src_policy.pow.rpt), [receipt](../evidence/current_metrics/power/source_policy_board_fixture_vcd/receipt.json).
- [Maximum 85°C .pow.summary](../evidence/current_metrics/power/source_policy_maximum_tj85/igor_src_policy.pow.summary), [full .pow.rpt](../evidence/current_metrics/power/source_policy_maximum_tj85/igor_src_policy.pow.rpt), [receipt](../evidence/current_metrics/power/source_policy_maximum_tj85/receipt.json).
- [Maximum 100°C .pow.summary](../evidence/current_metrics/power/source_policy_maximum_tj100/igor_src_policy.pow.summary), [full .pow.rpt](../evidence/current_metrics/power/source_policy_maximum_tj100/igor_src_policy.pow.rpt), [receipt](../evidence/current_metrics/power/source_policy_maximum_tj100/receipt.json).
- [Planner Typical .pow.summary](../evidence/current_metrics/power/planner_vectorless/igor.pow.summary), [full .pow.rpt](../evidence/current_metrics/power/planner_vectorless/igor.pow.rpt), [receipt](../evidence/current_metrics/power/planner_vectorless/receipt.json).

Total harus sama dengan dynamic+static+I/O dalam toleransi pembulatan report; collector memeriksanya. Receipt juga memuat source/SOF/build identity, command, exit code, report SHA dan konfirmasi input rilis tidak berubah. Collector memeriksa bahwa suhu/model aktual pada report sesuai yang diminta; setting yang diabaikan tidak diterima sebagai pengukuran kondisi tersebut.

### Asumsi yang tidak boleh dihilangkan dari slide

1. **HPS Enable = Off** pada model. Tool memberi **Critical Warning 215050** karena device mempunyai HPS tetapi power HPS belum disediakan. Angka ini tidak mencakup konsumsi operasi ARM/Linux HPS.
2. Tegangan model VCC 1,10 V, I/O 3,3 V; untuk profil Typical digunakan ambient 25°C dan thermal solution default tool. Board thermal model tidak diberikan, sehingga tool memberi warning terkait model thermal pada profil auto-temperature.
3. Toggle default 12,5% dan/atau propagasi vectorless bukan aktivitas terukur hardware. VCD tambahan meningkatkan informasi pin namun coverage internal masih 2,2%; tidak mengubah confidence menjadi High.
4. Daya regulator, DDR/periferal board, sensor, Jetson dan motor bukan total FPGA thermal report. Efisiensi supply dan arus startup juga belum diukur.
5. Confidence **Low** harus ditulis bersama angka. Tidak ada klaim “power diukur 464,21 mW”, “seluruh board 38,51 mW”, atau “pasti beberapa mW”.

Angka historis ±0,51 W pada lampiran sekarang mempunyai pembanding actual tool untuk build current di atas; jangan memakai angka historis sebagai hasil ukur baru. Panduan resmi [Power Analysis Intel/Altera](https://www.intel.com/content/www/us/en/content-details/653116/power-analysis.html) membedakan estimasi static/dynamic; [pengaturan karakteristik power](https://www.intel.com/programmable/technical-pdfs/683296.pdf) menjelaskan Typical dan Maximum. Untuk konfigurasi Standard/Cyclone V ini, nilai yang digunakan dibuktikan langsung oleh full report dan help tool lokal.

## 5. Jika ingin menurunkan power lebih lanjut

Pada profil Typical, static **413,17 mW** sudah mendominasi total. Clock enable/data isolation dapat mengurangi switching/dynamic, tetapi tidak menghapus static power seluruh FPGA. Target total ≤100 mW, apalagi beberapa mW, **belum didukung oleh hasil desain/FPGA ini**.

Prioritas eksperimen berikutnya adalah workload normal/idle terdefinisi, VCD internal atau netlist dengan coverage lebih tinggi, kemudian clock enable pada ROM/MAC ketika idle atau pengurangan kapasitas ROM terpad bila tetap inferable. Setiap perubahan harus mempertahankan oracle integer, semua fault/E-stop, latency contract, fitting/timing dan power analysis dengan kondisi yang sama. Baru setelah lulus boleh dinyatakan sebagai penghematan terukur tool. Analisis ini sendiri tidak mengganti RTL yang sudah tervalidasi demi mengejar angka.

Untuk **daya fisik**, ukur rail yang disebutkan atau input board dengan alat terkalibrasi: catat V, I, workload/idle, HPS/periferal, suhu, SOF hash dan waktu sampling. `P_mW=V×I_A×1000` atau `V×I_mA`. Bandingkan scope yang sama; input-board power dan FPGA thermal estimate merupakan besaran berbeda. Uji hardware tetap menunggu perangkat sesuai arahan sebelumnya.

## Varian Parallel8: target core di bawah 0,16 ms

Varian [Parallel8](../experiments/parallel8/README.md) menggunakan bobot dan
kontrak Q8.8 yang sama, delapan neuron/MAC paralel serta delapan bank ROM dan
hidden storage. Regresi integer/safety, full compilation, 13 fitted pins dan
seluruh timing corner lulus. Core **6.916 siklus / 0,13832 ms pada 50 MHz**;
resource fitted **3.303 ALM, 6.277 register, 64 M10K, 8 DSP**.
Setup terburuk **+5,647 ns**, hold **+0,119 ns**. Tambahan terhadap baseline:
54 ALM, 281 register, 7 DSP, nol M10K. Kuantisasi tidak berubah; seluruh
hidden activation dan output tetap cocok dengan oracle yang sama.

Power estimasi Typical **476,18 mW** (dynamic 50,36; static 413,27; I/O 12,55),
Maximum/Tj100°C **937,55 mW** (50,36; 865,80; 21,40; pembulatan report).
Confidence Low, vectorless, HPS Off; bukan pengukuran hardware. Total masih
di bawah 1.000 mW untuk dua profil tersebut, belum di bawah 350 mW.
[CSV provenance kandidat](../experiments/parallel8/artifacts/metric_evidence.csv)
dan [acceptance/SHA](../experiments/parallel8/artifacts/acceptance.json)
memisahkan bukti ini dari baseline. UART tetap menambah 1,7712 ms serial ideal;
latensi core bukan latensi sistem dari host ke host.

## Klarifikasi clock dan interpretasi budget

Desain policy saat ini memakai `FPGA_CLK1_50` langsung pada **50 MHz**; Fitter melaporkan **0 PLL**. Pembagi UART `BIT_CYCLES=54` adalah penghitung waktu bit, bukan clock core 925 kHz. Bukti clock domain ada pada `power/source_policy_vectorless/igor_src_policy.pow.rpt`, bagian **Core Dynamic Thermal Power Dissipation by Clock Domain**: `FPGA_CLK1_50`, `50.00 MHz`, `38.51 mW`.

Kecepatan mekanik 0,1 RPS tidak menentukan frekuensi komputasi policy **74→128→64→3**. Dengan jadwal 54.348 siklus yang sama, inferensi pada 5 MHz memerlukan **10,8696 ms**, sedangkan pada 1 MHz **54,348 ms**, melewati periode kontrol 20 ms. Menurunkan clock memerlukan perhitungan ulang UART, timeout/watchdog, constraint timing dan seluruh regresi; angka ini hanya proyeksi latency, bukan hasil build clock baru.

Laporan ini sudah menggunakan hasil fitting dan **post-fitting delay annotation**. Confidence Low tidak berarti routing belum selesai: report menyatakan data toggle pengguna belum cukup; VCD tambahan baru mencakup 2,2% node internal. Simulasi netlist dengan workload representatif perlu memperbaiki cakupan dan pemetaan aktivitas, bukan sekadar menghasilkan file VCD.

Angka **925,69 mW bukan total board/HPS**: model HPS Off, dengan breakdown 38,51 mW dynamic + 865,80 mW static + 21,38 mW I/O. Budget total 350 mW belum tercapai, bahkan static Typical 413,17 mW sudah melampauinya. Tidak ada dasar dari hasil ini untuk menjanjikan static 150–200 mW. Cyclone V memakai proses **28 nm**, sesuai [Altera](https://www.altera.com/products/fpga/cyclone-v).

Untuk isolasi hierarchy pada profil Typical, tabel **Thermal Power Dissipation by Hierarchy** pada full report baris 185–186 memberi policy UART **32,45 mW** dan neural core **26,05 mW**, termasuk anak hierarchy dan routing masing-masing. Core: 12,85 mW block dynamic + 13,20 mW routing dynamic. Angka tersebut bukan total chip: static global tidak seluruhnya dialokasikan ke hierarchy ini. Jangan menjumlahkan parent dan child karena saling mencakup. Semua tetap estimasi confidence Low.

Total estimasi di bawah 1 W bukan bukti tidak akan overheating atau mengalami voltage drop. Validasi thermal, supply dan produksi memerlukan kondisi operasi serta pengukuran fisik yang belum dilakukan.

## 6. Cara mengulang dan audit perubahan report

Dari folder `fpga`:

```powershell
python scripts/run_power_analysis.py source_policy
python scripts/run_power_analysis.py planner
python scripts/run_power_analysis.py source_policy --profile board_fixture_vcd --vcd evidence/current_board_wrapper/board.vcd
python scripts/run_power_analysis.py source_policy --profile maximum_tj85 --characteristics MAXIMUM --junction-c 85
python scripts/run_power_analysis.py source_policy --profile maximum_tj100 --characteristics MAXIMUM --junction-c 100
python scripts/collect_design_metrics.py
```

Quartus `--write_settings_files=off` menjaga assignment; Power Analyzer tetap dapat memperbarui **flow summary**. Pada run awal, perubahan metadata flow dideteksi guard dan dicatat melalui `post_compile_flow_update` di kedua build receipt: source, bobot, SOF, Fitter, STA dan compile log tetap sama; receipt compile sebelum power serta flow sesudah power diarsipkan. Itu tambahan tahap analisis, bukan kompilasi source baru. Run berikutnya menyimpan flow tahap power terpisah dan mengembalikan flow compile yang terikat receipt, lalu memeriksa semua hash. Power reports tiap profil tidak saling menimpa di direktori evidence.

Satu percobaan awal parameter suhu ditolak karena tool mengabaikan nilai bertipe desimal; log disimpan sebagai `rejected_ignored_settings.log` dan `rejected_attempt.json` pada folder profil 85°C. Nilai dari percobaan itu tidak dipakai sebagai hasil 85°C. Run diterima menggunakan parameter integer dan report mengonfirmasi junction **85,0°C**; demikian juga **100,0°C**. Exit code sukses saja tidak cukup untuk menerima konfigurasi analisis.

Semua keluaran terikat pada manifest rilis setelah freeze; perubahan metrics/report perlu diregenerasi dan dibekukan ulang. `python scripts/freeze_release.py --check` hanya memeriksa integritas, tidak mengubah data atau mengklaim pengukuran hardware.
