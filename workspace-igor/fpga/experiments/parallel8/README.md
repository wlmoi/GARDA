# PPO source-policy: delapan neuron paralel

**PASS simulasi, full compilation, fitted pins dan timing 50 MHz** pada
17 Oktober 2026. Ini adalah varian cepat untuk target **core <0,16 ms**;
programming/pengukuran hardware fisik belum dilakukan.

| Metrik | Baseline | Parallel8 tervalidasi |
|---|---:|---:|
| Latensi core | 54.348 siklus / 1,08696 ms | **6.916 siklus / 0,13832 ms** |
| ALM | 3.249 | **3.303 / 41.910 (7,88%)** |
| Register | 5.996 | **6.277** |
| M10K | 64 | **64 / 553** |
| DSP | 1 | **8 / 112** |
| Setup terburuk | +6,019 ns | **+5,647 ns** |
| Hold terburuk | +0,116 ns | **+0,119 ns** |
| Power Typical total | 464,21 mW | **476,18 mW** |
| Power Maximum / Tj 100°C total | 925,69 mW | **937,55 mW** |

Kapasitas resource dan timing **cukup** untuk varian ini: tambahan hanya
**54 ALM, 281 register dan 7 DSP**, tanpa tambahan M10K. Percepatan core
sekitar **7,86×**. ALM merupakan resource FPGA; ini bukan estimasi luas ASIC mm².

Power Typical: **50,36 mW dynamic + 413,27 mW static + 12,55 mW I/O**.
Maximum/Tj100°C: **50,36 mW dynamic + 865,80 mW static + 21,40 mW I/O**;
selisih 0,01 mW dari total berasal dari pembulatan komponen report.
Keduanya confidence **Low**, vectorless, HPS Off, bukan daya board terukur.
Estimasi total masih <1.000 mW, tetapi target total 350 mW belum tercapai.
Tidak ada jaminan produksi/thermal dari estimasi ini.

Bukti angka: [Fitter summary](output_files/igor_src_policy.fit.summary),
[semua timing corner](output_files/igor_src_policy.sta.summary),
[power Typical](artifacts/power/typical/igor_src_policy.pow.summary),
[power Maximum/Tj100°C](artifacts/power/maximum_tj100/igor_src_policy.pow.summary),
[CSV sumber/baris/SHA](artifacts/metric_evidence.csv),
[acceptance dan identitas source/SOF](artifacts/acceptance.json).

Full compilation selesai **09:22:32 WIB**, 0 error / 49 warning yang direview:
24 warning 10037 adalah pemilihan nama bank konstan hasil source expansion;
24 warning 10030 adalah tiga port tulis ROM read-only × delapan bank;
satu warning 10230 adalah penjumlahan neuron 32 bit ke register 8 bit.
Pada jadwal legal neuron selalu 0,8,...,120; increment hanya sampai 120,
sehingga pemotongan tersebut tidak membuang bit bernilai satu.
Collector menolak kategori/jumlah warning lain. Icarus juga memberi warning
bentuk named generate scope, tanpa error. Tidak ada critical warning kompilasi;
Power Analyzer mempunyai peringatan HPS tidak dimodelkan dan confidence Low.

Kandidat ini mempertahankan model **74→128→64→3**, Q8.8, akumulator signed
40 bit, urutan penjumlahan setiap neuron, ReLU/clamp, protokol UART dan
pengamanan baseline. Delapan neuron dihitung bersamaan, masing-masing dengan
satu multiplier, accumulator, aktivasi dan bank ROM. Operand input dibroadcast;
tidak ada adder tree yang mengubah urutan penjumlahan.

Hidden storage juga dibagi menjadi delapan bank dengan satu port tulis per
bank. Percobaan awal array hidden bersama dengan delapan port tulis dihentikan
saat elaborasi memerlukan waktu panjang; log aslinya dipertahankan sebagai
`artifacts/initial_elaboration_interrupted.log`. Itu bukan build PASS. Regresi
dijalankan ulang setelah perubahan banking hidden storage.
Akumulator dibuat sebagai register lokal setiap lane, dan tiga action ditulis
eksplisit. Log percobaan sebelum perubahan register ini ada pada
`artifacts/banked_hidden_elaboration_interrupted.log` dan juga bukan build PASS.
Versi generated sekarang memakai delapan scope lane literal dan alias hidden
storage literal, tanpa nested genvar loop. Log percobaan sebelumnya disimpan
sebagai `artifacts/local_register_elaboration_interrupted.log`. Perubahan
bentuk source ini tidak mengubah siklus atau aritmetika; regresi tetap wajib.

Seluruh kandidat berada di `fpga/experiments/parallel8`. Proyek baseline
`fpga/fpga_de10_nano/src_policy` tidak diganti. Buka
[`igor_src_policy.qpf`](igor_src_policy.qpf) untuk kandidat, bukan QPF baseline.
Device **5CSEBA6U23I7**, clock **50 MHz**, pin planning dan constraint disalin
dari baseline. KEY0 reset, KEY1 E-stop, UART dan LED tetap pada pin yang sama;
lihat [`pin_assignment.tcl`](pin_assignment.tcl).
Tabel konektor JP1 dan arti LED ada di
[README board baseline](../../fpga_de10_nano/src_policy/README.md).
Untuk programming setelah build diterima, buka Programmer dari QPF kandidat,
pilih USB-Blaster, Auto Detect chain, pilih FPGA Cyclone V lalu tambahkan
`output_files/igor_src_policy.sof` kandidat dan centang Program/Configure.
Jangan memakai SOF baseline saat menguji angka 138,32 µs. Programming fisik
belum dilakukan; GPIO UART adalah jalur runtime, bukan pengganti JTAG
untuk memasukkan SOF pada rancangan ini.

## Jadwal dan batas klaim

| Layer | Grup neuron | Input/grup | Siklus |
|---|---:|---:|---:|
| 74→128 | 16 | 74 | 16×(3×74+4) = 3.616 |
| 128→64 | 8 | 128 | 8×(3×128+4) = 3.104 |
| 64→3 | 1 | 64 | 1×(3×64+4) = 196 |
| Total | 25 | | **6.916** |

Mulai penerimaan `start` sampai `done`: **138,32 µs = 0,13832 ms**, dibanding
baseline 1,08696 ms. Target <160 µs menyisakan **21,68 µs (13,55%)**. Angka ini
memerlukan timing 50 MHz terpenuhi; hasil Fitter/STA harus diperiksa.

Target tersebut **hanya core**, bukan round-trip UART. Serial 164 byte dengan
divider 54 tetap memerlukan 1,7712 ms ideal; jumlah serial+core **1,90952 ms**,
belum termasuk parser, host, OS dan jeda. Komunikasi perlu perubahan tersendiri
jika target 0,16 ms dimaksudkan untuk seluruh sistem.

## ROM dan edge cases

`prepare.py` membagi neuron dengan `neuron = group×8+lane`. Setiap bank memuat
2.297 kata, dipad menjadi 4.096 kata; delapan bank total 32.768 kata/64 KiB,
sama dengan kapasitas padded baseline. Layout tiap bank:

- W1 0–1183; b1 1184–1199.
- W2 1200–2223; b2 2224–2231.
- W3 2232–2295; b3 2296.

Lima lane tidak terpakai pada layer akhir diberi bobot/bias nol. Hanya tiga
action disimpan; tidak ada akses action[3..7]. Dua hidden layer adalah kelipatan
delapan sehingga tidak ada tail write melewati array. Fault, incomplete frame,
write/start saat busy, load+start ambigu, output index invalid, abort di semua
state aktif, reset/recovery dan saturation tetap diperiksa oleh suite baseline.

Parameter `ROM_FILE` core dipertahankan untuk kompatibilitas port wrapper,
namun sumber bobot kandidat adalah **bank0.mem–bank7.mem** hasil pembagian
canonical `policy_weights.mem`. Jangan mengganti hanya ROM_FILE untuk model
baru: jalankan export model yang tervalidasi lalu `prepare.py` dan seluruh tes.

## Bukti simulasi

- [`artifacts/core.log`](artifacts/core.log): 236 vektor jaringan, 8.364 kasus
  aktivasi, 54.399 assertion. Seluruh 192 hidden activation dan tiga action
  diperiksa terhadap oracle integer independen, bukan hanya output final.
- [`artifacts/uart.log`](artifacts/uart.log): 184 transaksi / 268 assertion,
  termasuk CRC, batas semua 74 field, E-stop/parser/inferensi/TX, stale,
  watchdog, saturating counters dan recovery.
- [`artifacts/board.log`](artifacts/board.log): 18 checkpoint wrapper board,
  clock/framing aktual dan KEY safety.
- [`core_checkpoints.csv`](core_checkpoints.csv): start cycle 499 → done 7415,
  selisih **6.916**; vektor berikutnya 7491 → 14407, juga 6.916.

Golden inputs tetap berasal dari `verification/src_policy/artifacts`.
Testbench kandidat diturunkan dari suite baseline dengan perubahan deklarasi
latensi dan lokasi output, tanpa melonggarkan assertion nilai/fault.
Kesamaan integer mempertahankan karakterisasi error kuantisasi baseline;
ini bukan bukti formal seluruh kemungkinan input ataupun uji hardware fisik.

## Reproduksi

Dari root workspace:

```powershell
python fpga/experiments/parallel8/prepare.py
python fpga/experiments/parallel8/run.py --build
python fpga/experiments/parallel8/capture.py
python fpga/experiments/parallel8/archive.py
python fpga/experiments/parallel8/power.py
python fpga/experiments/parallel8/collect.py
```

`prepare.py` meregenerasi RTL/testbench/QSF/bank dari baseline, sehingga perubahan
manual pada file generated harus dilakukan di generator. Build dan simulasi
menulis output lokal kandidat. Jangan mempromosikan kandidat hanya dari hasil
simulasi: resource, semua timing corner, pin dan power perlu hasil tool sendiri.
Collector memverifikasi 18.051 koefisien, padding, dua interval cycle counter,
log simulasi, SHA input simulasi, status full compilation, seluruh slack yang
dilaporkan serta kesamaan 13 fitted pins terhadap baseline. Arsip VCD `.gz`
bersifat lossless; [`artifacts/waveforms.json`](artifacts/waveforms.json)
mencatat SHA sebelum dan sesudah kompresi. Capture GTKWave native ada di
[`artifacts/core_latency.png`](artifacts/core_latency.png), dengan counter
hex `00001B04` = 6.916, done=1 dan fault=0 pada marker completion.
