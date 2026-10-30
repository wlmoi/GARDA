# Penerimaan final paket FPGA IGOR

Audit kebutuhan: **16 Oktober 2026, Asia/Jakarta**. Lampiran terbaru
“Kekuatan yang ingin kami tonjolkan” dipakai sebagai daftar kebutuhan
**K1–K7, A1–A14, B1–B6, D1–D7**, bukan sebagai bukti baru atau instruksi
untuk memublikasikan dokumen internal. Seluruh perubahan paket sesi ini
dibatasi pada `./fpga`; `./src` dan `./peruri-iseedesign` adalah referensi.

**Paket digital dapat disiapkan dan diperiksa; penerimaan board dan robot
tetap memerlukan perangkat fisik.** SOF, timing pass, waveform dan unit test
tidak membuktikan programming JTAG, tegangan pin, roda berhenti atau robot
sampai tujuan. Tidak ada pengukuran fisik baru yang diklaim dokumen ini.

## Project yang dibuka dan arti keluarannya

| Profil | Project Quartus | Kontrak yang benar |
|---|---|---|
| Policy dari software workspace | [`igor_src_policy.qpf`](../fpga_de10_nano/src_policy/igor_src_policy.qpf), top `igor_src_policy_de10_nano` | PPO residual **74→128→64→3**; observasi 74 nilai Q8.8 → tiga residual twist. UART 921600, frame request 153 byte/respons 11 byte. Hasil bukan setpoint roda. |
| Planner dan safety gate | [`igor.qpf`](../fpga_de10_nano/quartus/igor.qpf), top `igor_uart_top` | Planner peta 128×128 dan neural legacy **24→64→64→4** dengan protokol UART tersendiri, 115200. Kode E-stop planner adalah **2**; pada policy kode E-stop adalah **1**. |

Keduanya memakai DE10-Nano **Cyclone V 5CSEBA6U23I7**, clock **50 MHz**.
Pilih profil pada manifest setiap run dan gunakan host yang sesuai.
Jangan mencampur frame, satuan, kode fault, bobot atau statistik kedua model.
Klaim **400/400 output dan 18.192 siklus** hanya berlaku pada neural legacy;
policy sumber mempunyai 236 vektor jaringan pada regresi digital saat ini
dan latency core **54.348 siklus**. Cocok dengan model integer bukan berarti
identik dengan model FP32.

Policy mengembalikan residual untuk blending/filter/kinematika host.
Residual nol sendiri **bukan STOP motor**. Pada fault, host harus menolak
transaksi dan mengirim empat command motor nol. Paket policy belum membentuk
seluruh jalur AI→pemeriksa peta→gate→motor di FPGA. Saat respons valid sudah
diterima host, E-stop yang menyusul memerlukan interlock motor fisik independen;
menghentikan TX UART tidak dapat menarik kembali byte yang telah diterima.

## Pemeriksaan bukti yang dapat diulang

Jalankan dari folder `fpga`, dengan Python dan Icarus Verilog pada PATH:

```powershell
python verification/src_policy/run.py --check
python verification/run_board_wrapper.py
python verification/run_safety_regression.py
python verification/run_host_regression.py
python verification/run_lidar_regression.py
python verification/audit_acceptance.py
```

`--check` tetap meregenerasi golden dan provenance, tetapi menolak ROM yang
tidak sesuai model JSON/enam MEM sumber. Jika model sengaja diganti, ekspor
tanpa `--check`, lalu ulangi seluruh verifikasi, compile dan penerimaan board.
Jangan memperbarui hash dalam ringkasan lama untuk membuatnya terlihat lulus.

[`current_acceptance/audit.json`](../evidence/current_acceptance/audit.json)
memeriksa **raw SHA256** source dan testbench pada hasil policy, wrapper board,
safety, host, driver LiDAR, serta model provenance. Ia juga memeriksa keberadaan
SOF, laporan flow berhasil/slack nonnegatif, dan 13 pin policy pada laporan
fitter. **Audit PASS berarti integritas bukti digital yang diperiksa cocok.**
Ia tidak menjalankan ulang simulator, membuktikan seluruh input/state space,
atau mengikat SOF ke source secara mandiri. Gunakan manifest build/release
yang dihasilkan dari compile source yang sama untuk ikatan source→SOF.

`evidence/RELEASE_MANIFEST.json` bawaan adalah **manifest historis repository
referensi**, dengan cakupan/path lama; ia bukan manifest penerimaan paket
`fpga` saat ini. Jangan memakai keberadaannya untuk mengesahkan release baru.
Simpan hash laporan dan SOF dari run compile yang sama, beserta identitas tool
dan seluruh input compile pada manifest release baru. Ubah source, bobot,
QSF, SDC atau pinplan berarti wajib membuat bukti run baru.

| Bukti digital | Lokasi | Yang dibuktikan dan batasnya |
|---|---|---|
| Integer policy / UART | [`results.json`](../verification/src_policy/artifacts/results.json), `core.log`, `uart.log`, `model_provenance.json` | 236 vektor, 8.364 kasus aktivasi, 54.399 assertion core, 184 transaksi terarah/268 assertion UART pada konfigurasi regresi bawaan. Seluruh 192 hidden activation dan tiga output dibandingkan per vektor. Jumlah ini adalah sampel/coverage yang didefinisikan, bukan formal proof. |
| Wrapper board aktual | [`summary.json`](../evidence/current_board_wrapper/summary.json), `simulation.log`, `checkpoints.csv` | 18 checkpoint, clock 50 MHz, UART 54 clock/bit; reset, LED, latch E-stop dan traffic serial diuji dalam simulasi wrapper yang dipasang pada project. |
| Gate/planner | [`summary.json`](../evidence/current_safety/summary.json), [`cases.csv`](../evidence/current_safety/cases.csv) | 111.210 pembandingan gate, 12 outcome, 111 checkpoint suite gate/unit/top/UART; command output nol, fault dan logger diperiksa bersama. Tidak mencakup semua peta 16.384 byte dan seluruh interleaving temporal. |
| Host controller / transport | [`results.json`](../evidence/current_host/results.json) | 29 fixture test: kontrol positif nonnol, malformed/timeout, NaN/Inf, STOP seluruh axis, lease dan transport fault. Fixture tidak mengukur ROS scheduling atau waktu berhenti motor. |
| LiDAR driver | [`results.json`](../evidence/current_lidar/results.json) | 16 fixture test pada production driver, parsing/recovery/freshness dan unknown range. Tidak mengukur sensor A1 fisik. |
| Compile dan fitted pins | `fpga_de10_nano/{src_policy,quartus}/output_files/` | Laporan Quartus dan SOF masing-masing profil. Angka resource/slack harus diambil dari build aktual, bukan angka 4.964 ALM/+0,146 ns dalam lampiran historis. |

Nomor di atas hanya boleh ditampilkan sebagai **hasil source saat ini** bila
audit hash dan hasil suite terkait lulus. Jika runner gagal atau audit SHA
gagal, status kembali **BUKTI USANG/GAGAL**, walaupun log lama berisi PASS.

GTKWave dari `fpga`:

```powershell
gtkwave verification/src_policy/artifacts/core.vcd verification/src_policy/core.gtkw
gtkwave verification/src_policy/artifacts/uart.vcd verification/src_policy/uart.gtkw
gtkwave evidence/current_board_wrapper/board.vcd evidence/current_board_wrapper/board.gtkw
gtkwave evidence/current_safety/top.vcd evidence/current_safety/top.gtkw
```

Waktu tepat policy ada pada `*_checkpoints.csv` kolom **time_ps**; safety
pada `cases.csv` kolom **time_ns**. Pilih checkpoint dari run yang sama dengan
VCD. Contoh skenario safety yang harus tampak: kontrol positif nonnol,
E-stop di antara clock → nol segera, edge logger berikutnya → last_fault 2
dan counter bertambah, write peta tanpa begin → fault 5, deadline tepat batas
→ fault 8, sequence peta berubah → hasil lama dicabut. Titik dan sinyal detail
ada pada [checklist implementasi](IMPLEMENTATION_READINESS.md) dan
[README RTL policy](../rtl/igor_src_policy/README.md).

## K1–K7: klaim yang boleh dan belum boleh dibuat

| ID | Bukti paket saat ini | Acceptance yang masih perlu dilengkapi |
|---|---|---|
| K1 AI tangguh | Policy sumber tersedia dan karakterisasi integer/FP32 terdokumentasi. | Studi pasangan AI vs DWA ≥100 seed, lima skenario ekstrem dan validasi perilaku setelah kuantisasi (B1/A9). Statistik 50 episode historis tidak membuktikan studi baru. |
| K2 AI mengemudi, chip memutuskan | Gate/planner dan policy memiliki pengujian digital masing-masing. | Jalur final model terpilih→gate→kurir→motor serta Studi B (A3–A5/B2). Tidak boleh menyatakan policy residual telah melewati pemeriksa peta FPGA. |
| K3 Fail-closed | Directed/random gate, fault UART, watchdog, lease, host STOP dan E-stop wrapper diuji digital. | Fault board, putus kabel, proses mati, restart dan stop roda dengan interlock independen serta waktu berhenti terukur (A3–A6/A8). |
| K4 Deterministik/identik | Golden integer dan latency core diperiksa per vektor dengan arsitektur/kuantisasi jelas. | Board readback, cycle counter fisik, RTT dan benchmark Jetson model yang sama (A1/A2/A7/A8/A10). |
| K5 Jejak audit | Kode fault, sticky flags/last fault, counter, checkpoint waktu dan SHA source tersedia. | Satu run menghubungkan input→FPGA→safety status→kurir→STM32→video, dengan metadata board dan SOF aktual (A3–A5/A13). |
| K6 Nyata | Project Quartus, pinplan, laporan dan SOF tersedia sebagai artifact digital. | Log programming berhasil, seluruh roda, tiga run robot, replay dan video (A1/A6/A9–A11). Source/model yang berbeda tidak boleh menukar bukti. |
| K7 Hemat/menuju chip lokal | Resource/timing dapat dilaporkan dari build yang dipilih; prototipe ASIC lama diberi label arsip. | Daya board terukur dan validasi ASIC sesuai flow fisik (A14). Power Analyzer adalah estimasi; tidak disamakan dengan USB meter. Harga, TAM, payback tetap estimasi bisnis. |

## A1–A14: penerimaan hardware

**Semua baris berikut terbuka untuk bukti fisik.** Menyediakan script/prosedur
atau compile tidak mengubah status menjadi lulus board.

| ID | Bekal dalam paket | Bukti minimum untuk menutup baris |
|---|---|---|
| A1 | Dua QPF/SOF, bobot, golden dan host sesuai profil. | Board ID/device, programming log sukses, SOF/script/model SHA, actual vs expected per vektor; 100×4 output dan enam scene hanya untuk profil legacy, vektor/output policy memakai jumlah aktual. |
| A2 | Counter latency dan golden cycle tersedia pada profil masing-masing. | Raw cycle FPGA per keputusan, clock, min/median/p99/max; pisahkan kernel dan transport. |
| A3 | Matriks edge case, suite safety, `capture_hardware_safety.py`. | Untuk tiap injeksi: output FPGA nol, permit nol, kode prioritas benar, logger/counter serta raw UART/SignalTap dan video. Uji E-stop, peta usang/invalid/replay, speed/delta dan deadline. |
| A4 | Snapshot host fail-closed dan fixture transport. | Mode kurir yang meneruskan keluaran gate model terpilih; pasangan RX/TX per sequence/lease, putus kabel/proses mati→STOP dan waktu berhenti fisik. Host policy residual bukan otomatis kurir gate legacy. |
| A5 | Batas jalur residual dan gate dijelaskan terpisah. | Audit satu-satunya command path ke motor; rekam gate, kurir dan STM32 serentak; tidak ada penggunaan command lama saat permit nol. |
| A6 | Source motor/prosedur tersedia; hasil offline berlabel offline. | Empat roda serentak: maju/mundur/geser/putar/STOP, tanda/ID/satuan benar, video semua roda dalam satu frame. |
| A7 | Kontrak model dan pemisahan kernel/RTT jelas. | Jetson AI yang sama + DWA C, 10.000 sampel idle dan sibuk, warmup terpisah, suhu/clock/governor, median/p99/max dan deadline miss. |
| A8 | UART 921600 policy/115200 planner dan ukuran frame terdokumentasi. | Raw request-start→response-validated per sequence, breakdown encode/UART/kernel/poll/CRC, p99/max dibanding periode kontrol; target <0,1 s harus diukur. |
| A9 | Snapshot integrasi dan definisi output model tersedia. | Tiga run Jetson + tiga run FPGA dengan start/goal/model/sensor/obstacle sama; raw sensor, command, safety, posisi, outcome dan video termasuk run gagal. |
| A10 | Golden integer dan export provenance tersedia. | Replay urutan sensor run Jetson yang sama, preprocessing/scaling identik, expected/actual setiap langkah dan mismatch lengkap. Pisahkan FP32 quantization error dari integer mismatch. |
| A11 | Schema log/video dijelaskan pada checklist. | Rekaman D1–D5, stop slow-motion, indeks timestamp/frame/checksum dan dua salinan terverifikasi. |
| A12 | Dua arsitektur dipisahkan eksplisit. | Keputusan retrain sebelum freeze berdasarkan data timeout/Studi A. Policy sumber tetap 74→128→64→3 kecuali kontrak sengaja direvisi; syarat 24→64→64→4 lampiran berlaku untuk jalur legacy. Bobot baru wajib mengulang golden/RTL/build/board. |
| A13 | Source, project, bobot dan bukti digital tersedia. | Freeze satu versi dengan manifest source/SOF/bobot/QSF/SDC/pinplan/tools/host/log/raw-data/video dari run yang sama; perubahan apa pun membuat run baru. |
| A14 | Prosedur membedakan estimasi dan pengukuran. | Opsional: meter/rail/beban/akurasi/interval jelas, raw idle vs aktif; laporkan board total terpisah dari rail FPGA. |

## B1–B6: hasil laptop dan materi demo

| ID | Status saat audit | Acceptance |
|---|---|---|
| B1 | **Belum ada hasil studi baru dalam paket.** | ≥100 seed pasangan AI/DWA dan lima skenario ekstrem; raw outcome goal/collision/timeout/durasi/panjang/kehalusan serta config/hash. |
| B2 | **Belum ada hasil studi episode baru.** Regresi invariant RTL tersedia. | AI saja vs AI+gate dengan gangguan sama; unsafe command dan false stop didefinisikan sebelum run, hasil dan denominasi serta satu grafik. |
| B3 | **Menunggu data A2/A7/A8.** | Dua grafik dari raw data: distribusi latency kernel dan breakdown RTT dengan satuan/n/median/p99/max. Jangan membuat data dari target. |
| B4 | **Ledger klaim tersedia** pada dokumen ini dan checklist implementasi. | Angka slide ditautkan ke model/source/build/run yang benar; data belum diukur ditulis “tidak diklaim”. Tidak ada placeholder angka. |
| B5 | **Urutan D1–D7 tersedia sebagai acceptance.** | Slide/naskah aktual, sumber tiap klaim dan tiga latihan penuh yang direkam/dicatat oleh tim. |
| B6 | **Menunggu rekaman fisik.** | Video cadangan 3–5 menit dapat diputar offline pada laptop dan flashdisk, checksum kedua salinan cocok. |

## D1–D7: penerimaan demonstrasi

| ID | Jalur yang mendukung | Berhasil jika |
|---|---|---|
| D1 Lintasan | A1/A3–A6/A9 | Robot sampai tujuan tanpa tabrakan; log membuktikan semua command berasal dari jalur FPGA model terpilih dan transformasi kurir terdokumentasi. **Belum diuji fisik.** |
| D2 Replay | A1/A2/A10 | Input yang sama→expected/actual per langkah identik dalam model integer; cycle counter sesuai profil, bukan memaksakan 18.192 pada policy baru. **Belum diuji board.** |
| D3 E-stop | A3/A5 | Roda diangkat; output FPGA/command motor nol, roda berhenti, fault planner 2 atau policy 1 sesuai profil, counter/flags benar dan video tersinkron. **Simulasi tersedia, fisik terbuka.** |
| D4 Peta/limit | A3/A5 | Peta invalid/usang dan speed/delta ditolak oleh profil planner dengan fault 5/10/11; output nol, roda diam, log dan video. Policy 74-input tidak membawa peta. **Simulasi tersedia, fisik terbuka.** |
| D5 Cabut kabel | A4/A5/A8 | Motor berhenti karena watchdog/lease, tanpa meneruskan command lama; slow-motion dan raw log mengukur waktu stop. **Belum diukur.** |
| D6 Slide bukti | B1–B5 | Tiap angka memiliki scope dan sumber; legacy 400/400/9/9 tidak ditampilkan sebagai hasil board atau model policy; data yang belum ada ditulis tidak diklaim. |
| D7 PERURI/bisnis | B4/B5 | Pengguna, yang dibayar, harga berlabel estimasi dan langkah pilot jelas. Retrofit melengkapi sensor/rem proteksi; HMAC/secure element, sertifikasi dan klaim produksi bukan kemampuan yang telah dibuktikan paket ini. |

## Keputusan penerimaan

**Go untuk membuka project, memeriksa pinplan, menjalankan regresi digital dan
menyiapkan programming terkontrol** setelah hasil terbaru dan manifest cocok.
**Penerimaan demonstrasi gerak belum selesai:** A1–A6, A8 dan A13 harus lulus
pada board/robot dan bitstream yang benar-benar dipakai. A9–A11 diperlukan
untuk klaim lintasan/replay/video. B1/B2/A7/A14 boleh tetap “tidak diklaim”
apabila datanya belum ada; status tersebut tidak boleh diganti angka contoh.

Format run dan bukti lengkap, urutan fault, boundary, logger saturation,
recovery serta go/no-go ada pada
[IMPLEMENTATION_READINESS.md](IMPLEMENTATION_READINESS.md). Simpan kegagalan
beserta hasil lulus agar jejak audit menunjukkan apa yang benar-benar diuji.
