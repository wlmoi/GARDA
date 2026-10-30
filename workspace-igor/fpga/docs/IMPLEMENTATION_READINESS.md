# Checklist implementasi IGOR dan penerimaan demo

Tanggal audit: **16 Oktober 2026, Asia/Jakarta**. Dokumen ini menerjemahkan semua butir A1–A14, B1–B6, dan D1–D7 dari catatan internal tim menjadi pekerjaan yang dapat diuji. Catatan internal adalah sumber kebutuhan; angka, rencana, dan label “Jumat” di dalamnya tidak dengan sendirinya menjadi hasil pengukuran baru.

**Status keseluruhan: paket RTL dan prosedur penerimaan tersedia; penerimaan board dan robot masih harus dilakukan dengan perangkat fisik.** Berhasil menyimulasikan RTL, membuat SOF, atau selesai menjalankan host script tidak membuktikan roda bergerak atau berhenti. Setiap status fisik di bawah tetap terbuka sampai ada rekaman, log, identitas board, dan hash bitstream dari run yang sama.

Sesuai arahan terbaru, **semua hasil baru berada di `./fpga`**. `./src` adalah referensi software murni dan `./peruri-iseedesign` adalah referensi checklist/arsitektur. Perbaikan transport, controller, MCU dan LiDAR ada pada snapshot runnable `fpga/software_integration/src`, sehingga source referensi tidak perlu diubah.

## Pilih arsitektur yang benar sebelum menguji

| Jalur | Kontrak model/data | Bukti yang berlaku | Batas penggunaan |
|---|---|---|---|
| Software workspace `src` dan RTL policy baru | PPO residual **74 → 128 → 64 → 3**; 64 LiDAR, 6 IMU, 3 perintah, 1 heading; output residual vx/vy/omega | Bobot sumber workspace, model integer policy, test core dan UART policy | Residual bukan empat kecepatan roda dan bukan izin motor. `safety_permit` pada wrapper policy berarti residual valid setelah pemeriksaan transport/E-stop/lease. Blending, CBF/mini-DWA, kinematika dan motor tetap memerlukan integrasi host yang benar. |
| Accelerator PERURI lama | Neural **24 → 64 → 64 → 4**, aset `neural_24_64_64_4`; planner DWA 512 kandidat × 20 langkah; peta 128 × 128 | [Metodologi lama](VERIFICATION.md), [hasil dan batas bukti](RESULTS_AND_SCOPE.md), [build planner saat ini](../evidence/current_builds/planner.json) | 400/400 dan 18.192 siklus adalah bukti jalur ini. Tidak boleh dipindahkan menjadi klaim policy 74-input. Neural dan planner lama belum otomatis membentuk jalur AI → DWA → gate. |
| Safety gate planner lama | `igor_top` → `igor_safety_security_gate` → v/omega/permit; logger fault | [RTL gate](../rtl/igor_safety_security_gate.v), [RTL logger](../rtl/igor_status_logger.v), regresi safety terkini | Melindungi keluaran planner terkait; bukan bukti bahwa keluaran policy baru atau seluruh pesan STM32 sudah melewati gate. |

Catatan internal menyebut SAC 24-input. README workspace dan bobot aktual menjelaskan PPO 74-input. Untuk permintaan “RTL dari software `src`”, sumber kebenaran adalah bobot dan kontrak software aktual. Simpan kedua jalur dengan nama berbeda. Jika demo memilih arsitektur lama, tuliskan pilihannya pada manifest run; jangan menampilkan hasil policy baru dengan angka jaringan lama.

## Pemetaan permintaan pengguna ke implementasi

README workspace dibaca sebelum desain dan file internal digunakan sebagai checklist kebutuhan. Instruksi yang tertulis di dokumen lampiran tidak memberi izin untuk mengirim materi internal, memublikasikan repository, atau mengklaim hasil fisik. Tidak ada push/publikasi yang dilakukan oleh penyiapan checklist/workflow ini.

| ID | Permintaan teks pengguna | File / acceptance yang menjawab | Status bukti |
|---|---|---|---|
| R1 | Baca README terlebih dahulu | `README.md` akar workspace; perbedaan kontrak model dijelaskan di atas. | DIAUDIT; model sumber 74-input dibedakan dari catatan 24-input. |
| R2 | Gunakan software `src` untuk menghasilkan RTL | [RTL policy](../rtl/igor_src_policy/), [exporter dan regresi](../verification/src_policy/run.py), `model_provenance.json` yang dihasilkan runner. | Source-true melalui hash/quantization check terhadap referensi software; implementasi host yang diperbaiki hanya berada di `software_integration/src/`. |
| R3 | GTKWave, lokasi dan titik tepat | [save core](../verification/src_policy/core.gtkw), [save UART policy](../verification/src_policy/uart.gtkw); safety `evidence/current_safety/{gate,units,top,uart}.gtkw`; CSV checkpoint safety berisi `time_ns`, policy memakai `time_ps` (bagi 1000 untuk ns). | Jalankan runner dan buka pasangan VCD/save dari run yang sama. Titik audit ditabelkan di bawah. |
| R4 | DE10-Nano dan pin planning langsung | [QPF policy](../fpga_de10_nano/src_policy/igor_src_policy.qpf), [QSF](../fpga_de10_nano/src_policy/igor_src_policy.qsf), [pinplan](../fpga_de10_nano/src_policy/pin_assignment.tcl), [SDC](../fpga_de10_nano/src_policy/igor_src_policy.sdc). | Target 5CSEBA6U23I7; programming dan verifikasi kabel fisik tetap A1. |
| R5 | Gunakan Quartus 25 yang terbuka / fresh compile | `fpga_de10_nano/src_policy/output_files/igor_src_policy.*`; README board dan laporan compile terkait. | Hasil build hanya berlaku bila source hash, tool version, fitter/STA dan SOF pada build yang sama tersedia. Tidak membuktikan JTAG programming. |
| R6 | Semua checklist folder PERURI | Seluruh A1–A14, B1–B6, D1–D7 pada dokumen ini. | 27/27 butir mempunyai acceptance dan status; butir hardware tidak dicentang tanpa perangkat. |
| R7 | GitHub Actions | Paket `ci/workflows/rtl-verification.yml` dan `quartus-src-policy.yml`; panduan instalasi `ci/README.md`. | Workflow disiapkan; YAML diuji lokal. Eksekusi GitHub memerlukan paket `fpga` di-commit dan dipublikasikan dalam repository workspace. |
| R8 | E-stop, perintah/peta invalid, output nol, error log traceable | [Safety runner](../verification/run_safety_regression.py), [akuisisi hardware](../verification/capture_hardware_safety.py), [host regression](../verification/run_host_regression.py); `current_safety/cases.csv`. | SIMULASI untuk fault/regresi; bukti board/robot ada di A3–A5 dan belum diklaim. |
| R9 | Seluruh arsitektur dijelaskan pada README | README workspace dan board, tabel kontrak model di atas, [arsitektur legacy](ARCHITECTURE.md). | Batas policy, host, planner, gate, UART dan motor disebut eksplisit. |
| R10 | Verifikasi intens dan edge case jelas | Matriks kode 0–11, malformed UART, timeout/lease, counter, numeric bounds di bawah; testbench dan source hashes dari kedua runner. | Coverage enumerasi + directed/random simulation; tidak mengklaim semua state space atau formal proof. |

## Arti status dan lokasi bukti

- **SIMULASI**: assertion/model integer lulus pada simulator; belum menyatakan hasil board.
- **ARSIP**: laporan lama tersedia dengan cakupan dan hash lama; belum menyatakan source yang berubah telah dibangun ulang.
- **SIAP DIUJI**: prosedur, RTL atau alat tersedia; acceptance belum terekam.
- **TERBUKA FISIK**: perlu board, Jetson, robot, alat ukur atau video.
- **TIDAK DIKLAIM**: hasil atau angka belum tersedia. Isi ini sebagai teks eksplisit pada slide; jangan menggantinya dengan angka contoh.

Entry point simulasi dari folder `fpga`:

```powershell
python verification/src_policy/run.py
python verification/run_board_wrapper.py
python verification/run_safety_regression.py
python verification/run.py all
python verification/run.py tt_generic
```

Policy baru menyimpan hasil pada `verification/src_policy/artifacts/`. Jalankan board wrapper sesudah policy runner agar vektor tersedia; hasilnya ada pada `evidence/current_board_wrapper/`. Uji ini memakai wrapper DE10-Nano aktual dengan clock 50 MHz dan divisor UART 54 clock untuk konfigurasi 921600 baud, bukan mempercepat UART testbench. Safety terkini menyimpan `summary.json`, `cases.csv`, source hashes, log suite, serta pasangan `gate`, `units`, `top`, `uart` berekstensi `.vcd` dan `.gtkw` pada `evidence/current_safety/`. Buka file `.gtkw` yang berpasangan dengan VCD hasil run yang sama; gunakan checkpoint waktu yang dicatat log/CSV. VCD menunjukkan sinyal digital model RTL, bukan tegangan pin fisik atau gerak motor.

Workflow siap dipasang ada di `fpga/ci/workflows/`. GitHub menjalankan workflow setelah maintainer menyalinnya ke `.github/workflows/` pada akar workspace; pekerjaan ini tidak mengubah folder di luar `fpga`. Semua job memakai working directory `fpga`. Paket `fpga` berisi source RTL, bobot ekspor, project board, testbench, model, evidence dan snapshot software integrasi; tidak memiliki repository Git tertanam. `src` dan `peruri-iseedesign` pada akar workspace dipertahankan sebagai referensi baca saja. Source/workflow lama di dalam folder referensi tidak menjadi target build baru.

`rtl-verification.yml` menjalankan empat job: policy sumber (`--check` untuk menolak ROM usang) beserta wrapper board pada UART aktual; safety; host fail-closed beserta driver LiDAR; regresi legacy+motor offline. Semua artifact menunjuk `fpga/`. CI memerlukan seluruh source paket `fpga` ikut di-commit; tidak melakukan checkout repository referensi, tidak memakai branch eksternal bergerak, dan tidak mengubah referensi. Menyiapkan YAML lokal bukan bukti workflow telah dijalankan di GitHub. Tidak ada push/publikasi otomatis.

`quartus-src-policy.yml` berjalan manual pada runner Windows terpercaya berlabel `quartus-25`; set `QUARTUS_SH` ke executable atau `QUARTUS_ROOTDIR` ke direktori Quartus. Runner memerlukan PowerShell 7, Cyclone V support, lisensi berlaku dan Actions Runner yang mendukung Node 24. Minimum runtime checkout adalah runner v2.327.1 menurut [README action yang dipin](https://github.com/actions/checkout/blob/d23441a48e516b6c34aea4fa41551a30e30af803/README.md). Job mengompilasi dan menyimpan laporan/SOF/hash; timing dan pinplan diperiksa sesuai project. Hosted CI tidak memiliki board/lisensi Quartus dan tidak membuktikan programming atau gerak robot.

Validator `scripts/validate_repository.py` pada referensi lama memeriksa manifest historis serta paket Nano/Lite arsip. Ia tidak digunakan sebagai acceptance source baru; manifest lama tidak diregenerasi untuk mengesahkan file baru. Release baru harus memiliki manifest paket `fpga` sendiri dengan source, bobot, hasil build dan software integration yang sesuai.

### Titik GTKWave safety dari run yang direkam

Lokasi berikut relatif terhadap `fpga`. Angka diambil dari CSV hasil regresi saat ini, bukan waktu video robot. Bila testbench berubah, CSV run baru menjadi sumber kebenaran; pastikan hash source pada `summary.json` sama dengan source yang diperiksa.

| File save / VCD | Waktu tepat | Checkpoint dan sinyal yang harus terlihat |
|---|---:|---|
| `evidence/current_safety/top.gtkw` / `top.vcd` | **814531 ns** | `valid_nonzero_result_7938_cycles`: `motor_enable=1`, `v_command=15`, `fault_code=0`. Ini kontrol positif sebelum E-stop. |
| Sama | **814535 ns** | `estop_asserted_between_clocks_immediate_zero`: E-stop aktif di antara clock, enable/v/omega langsung nol dan kode 2. Logger belum mendapat edge berikutnya. |
| Sama | **814551 ns** | `estop_registered_error_log`: output tetap nol, `event_count=3`, `last_fault=2`. Ini titik pencatatan yang harus dipasangkan dengan titik assertion. |
| Sama | **2931031 ns** | `write_without_map_begin_zero_and_logged`: output nol, fault 5, event_count 3, last_fault 5. |
| Sama | **3904291 ns** | `compute_deadline_variant_zero_and_logged`: instance `deadline_core`, output nol, fault 8, last_fault 8. Pilih sinyal instance varian deadline bila belum terlihat. |
| Sama | **3945471 ns** | `map_freshness_exact_boundary_zero`: instance `freshness_core`, `map_age=10000`, output nol, fault 5. Logger menyusul di 3945491 ns. |
| Sama | **3945511 ns** | `result_command_lease_exact_boundary_zero`: elapsed 10000, output nol, fault 8. Logger menyusul di 3945531 ns. |
| Sama | **4759921 ns** | Commit peta sequence baru menarik hasil peta lama: output nol, fault 9. Logger menyusul 4759931 ns; run baru sequence 2 memberi permit lagi di 4918711 ns. |
| `evidence/current_safety/uart.gtkw` / `uart.vcd` | **366251 ns** | `run_nonzero_payload`: `invalid_command=1`, accepted_commands 0, output nol, fault 4 dan last_fault 4. Payload RUN wajib nol. |
| Sama | **944631 ns** | `crc_corruption_zero_and_logged`: protocol_fault 1, accepted_commands 0, output nol; replay frame benar sesudah CRC salah tetap ditolak sampai reset. |

Seluruh 111 checkpoint ada di `evidence/current_safety/cases.csv`; test gate membandingkan 111.210 vektor pada 12 outcome. Jumlah ini adalah hasil regresi saat ini, bukan jumlah kemungkinan keseluruhan sistem. Source-current legacy cocotb juga diulang: gate, neural, top, UART, wrapper dan netlist generic berjumlah 8 testcase; uji serializer serta motor controller tetap offline.

Host integrasi mempunyai 29 testcase yang memeriksa valid response dan motor nonnol sebagai kontrol positif, STOP operator, CBF yang mengembalikan kandidat unchanged, hard stop seluruh axis pada jarak kritis, batas/envelope akhir, NaN/inf, scan malformed dan metadata sudut, IMU stale, monotonic watchdog serta lease yang kedaluwarsa selama compute. Transport failure dilatch agar balasan lama tidak dipakai setelah retry. Protokol residual tidak membawa sequence/permit motor; E-stop yang ditekan sesudah sebuah balasan valid lengkap terkirim masih membutuhkan interlock fisik independen agar motor berhenti langsung. Ini batas integrasi A3–A5, bukan hasil yang ditutup dengan simulasi policy.

## A. Checklist hardware A1–A14

Semua baris hardware berikut berstatus **TERBUKA FISIK** sampai acceptance-nya dicatat. Adanya SOF/laporan historis dicatat sebagai prasyarat, bukan centang selesai.

| ID | Prasyarat dan langkah implementasi | Selesai jika / bukti yang disimpan |
|---|---|---|
| A1 | Pilih model/bitstream, cek DE10-Nano **5CSEBA6U23I7**, programming JTAG dan readback; jalankan seluruh vektor model terpilih dan enam scene planner lama bila planner ikut demo. | Log programming sukses + identitas board, SHA256 SOF/bobot/script, raw output per vektor, expected/actual dan mismatch=0. Klaim “100 vektor/400 output” hanya untuk 24→64→64→4; policy 74-input memakai jumlah output aktual runner. Video memperlihatkan board dan terminal. |
| A2 | Baca counter kernel dari FPGA untuk setiap inferensi/scene; pisahkan kernel, UART dan end-to-end. | CSV per keputusan berisi sequence, model, cycles, clock Hz; min/median/p99/max dan daftar cycle unik. Target arsip 18.192/7.938 hanya diterima untuk kernel lama yang sama. Policy baru memakai cycle hasil model barunya. |
| A3 | Jalankan matriks safety di bagian berikut pada board; mulai dengan roda terangkat. Injeksi E-stop, protective stop, peta invalid/stale/replay, limit, delta dan timeout. | Setiap fault: permit=0 dan semua output command=0, kode prioritas benar, last_fault/event_count tercatat, timestamp/video tersinkron. Ada run kontrol normal sebelum dan sesudah pemulihan yang diizinkan. |
| A4 | Buat mode kurir Jetson yang meneruskan **output gate** apa adanya: sequence, expiry, permit, fault, command. Validasi framing/CRC, sequence dan lease; STOP bila paket salah/hilang/terlambat, restart atau proses mati. | Byte/payload RX FPGA dan TX motor dapat dicocokkan per sequence; hanya konversi kinematika/encoding terdokumentasi yang diizinkan. Cabut kabel saat roda diangkat: log timeout → STOP, dan video berhentinya roda. Driver inferensi residual pada workspace bukan mode kurir ini. |
| A5 | Audit satu-satunya jalur menuju motor: tidak ada fallback CPU/perintah lama saat permit=0. Rekam output gate, pesan kurir dan TX STM32 bersamaan. | Dalam semua sabotase, motor menerima nol karena output gate nol atau lease gagal; sequence dan timestamp menghubungkan ketiga lapisan. LED fault saja tidak cukup. |
| A6 | Setelah A3–A5, uji empat roda bersamaan: maju, mundur, geser kanan/kiri, putar kedua arah, STOP; catat ID, tanda, satuan dan supply. | Video semua roda pada frame yang sama, log empat setpoint/STOP dan pengamatan fisik per roda. Riwayat roda individual tidak menutup butir ini. |
| A7 | Ukur model yang identik pada Jetson dan DWA versi C: 10.000 iterasi idle + 10.000 sibuk; warmup terpisah; log governor, suhu, beban dan clock. | Raw CSV waktu monotonic, script/weights hash dan metadata; median, p99, max. Laporkan deadline miss. Jangan menyebut benchmark AI kecil ini sebagai bukti FPGA lebih cepat dari GPU. |
| A8 | Ukur UART request-start → valid response diterima, termasuk encoding, payload, polling, CRC dan timeout. Uji 115200 dan baud pilihan yang benar-benar dipakai. | Raw CSV RTT per sequence + breakdown kernel/transport; persentil dan total p99/max dibandingkan periode kontrol aktual. Tidak memakai waktu kernel 0,36 ms untuk menyatakan RTT <100 ms. |
| A9 | Setelah jalur aman siap, lakukan 3 run Jetson + 3 run FPGA dengan start/tujuan, peta, model, obstacle dan batas kecepatan sama. | Setiap run: sensor mentah bertimestamp, command, safety status, posisi, outcome, video; jarak tujuan/timeout/collision didefinisikan sebelum run. Hasil gagal tetap disimpan. |
| A10 | Replay sensor run Jetson yang sama, berurutan dan dengan preprocessing sama, ke FPGA; jangan membandingkan dua lintasan sensor berbeda. | CSV input/expected/actual per timestep, scaling/rounding, mismatch lengkap dan source hash. Pisahkan fixed-point vs FP32 error dari ketidaksesuaian integer RTL. |
| A11 | Rekam D1–D5, board/pin, layar log, fault, STOP slow-motion dan footage tambahan. | Indeks file video per run dan checksum; dua salinan terverifikasi pada media berbeda. Sertakan frame rate/timebase untuk pengukuran waktu berhenti. |
| A12 | Putuskan “retrain/tidak” **sebelum freeze** berdasarkan timeout dan Studi A; tetapkan arsitektur model terpilih. | Catatan keputusan beserta bukti. Jika retrain model legacy, ukuran tetap 24→64→64→4; jika model workspace, ekspor ulang jaringan aktual 74→128→64→3 dan ulangi seluruh golden, RTL, build dan board acceptance. Tidak ada pergantian bobot diam-diam. |
| A13 | Bekukan folder `FINAL/<run-id>/`: source, SOF, QPF/QSF/SDC, pinplan, bobot, exporter, golden, host, laporan, manifest dan log uji. | SHA256 semua file + commit/worktree state + versi tools. Rebuild/ubah satu file membuat versi baru; jangan menimpa bukti run lama. Snapshot arsip lama tidak mewakili source baru. |
| A14 | Opsional: ukur daya dengan meter sesuai rail board; pisahkan idle/aktif, board total/rail FPGA, adaptor dan kondisi periferal. | CSV/screenshot alat, akurasi, interval dan kondisi beban; W rata-rata/min/max. Estimasi Quartus tetap diberi label estimasi dan tidak diperlakukan sebagai ukur daya. |

## B. Checklist laptop B1–B6

| ID | Implementasi dan acceptance | Status awal |
|---|---|---|
| B1 | Studi A: ≥100 episode AI vs DWA pada simulator, seed, sensor, fisika, timeout dan start/goal yang sama; tambah lima skenario ekstrem yang ditetapkan. Simpan konfigurasi dan outcome mentah. Tabel berisi goal, collision, timeout, durasi, panjang lintasan dan ukuran kehalusan yang didefinisikan. | **TERBUKA**; gambar/GIF dan 50 episode historis tidak menggantikan studi pasangan 100 seed. |
| B2 | Studi B: AI saja vs AI+gate pada input berpasangan; injeksi sensor beku/hilang, peta usang, command ekstrem dan obstacle tak terlihat AI. Tentukan unsafe command dan false stop sebelum eksperimen. Laporkan collision, unsafe yang lolos dan false stop beserta denominaturnya. | **TERBUKA**; regresi RTL safety tersedia sebagai bukti invariant, bukan hasil episode robot/studi ini. |
| B3 | Buat dua grafik dari A2/A7/A8: distribusi latency kernel FPGA vs Jetson dan breakdown RTT. Simpan data, script dan satuan; tampilkan p99/max dan jumlah sampel, bukan hanya mean. | **MENUNGGU DATA FISIK**; angka target tidak boleh dijadikan data grafik. |
| B4 | Audit setiap angka slide: model, versi, sumber, cakupan, label simulasi/board/estimasi. Angka yang belum diukur ditulis “tidak diklaim”; hapus semua placeholder angka kosong. | **SIAP DIKERJAKAN** dengan ledger angka di bawah. |
| B5 | Naskah/slide mengikuti D1–D7; setiap klaim punya satu kalimat penjelasan dan tautan bukti. Latihan penuh 3 kali dengan durasi dan kendala dicatat. | **TERBUKA**; prosedur demo tersedia, rekaman latihan belum ada. |
| B6 | Susun video cadangan 3–5 menit dari footage aktual, berlabel jenis bukti; uji offline pada laptop dan flashdisk. | **MENUNGGU A11**; rundown bukan file video. |

## D. Checklist demonstrasi D1–D7

| ID | Apa yang ditampilkan | Kriteria terima / bukti |
|---|---|---|
| D1 | Robot menempuh lintasan yang sama dengan A9; output FPGA dan sequence terlihat. | Sampai tujuan tanpa menyentuh obstacle, semua command traceable dari output FPGA; tandai jalur policy residual+host atau planner+gate secara akurat. **Menunggu A4–A6/A9.** |
| D2 | Replay sensor yang sama; expected/FPGA, mismatch dan cycle counter berdampingan. | Cocok integer per timestep; counter milik model yang benar. Nilai 18.192 hanya untuk legacy. **Menunggu A2/A10.** |
| D3 | E-stop saat roda terangkat dan berputar; output, permit, fault dan event_count di layar. | FPGA output nol, permit=0, kode 2, counter naik sesuai semantik logger; roda berhenti dibuktikan video. **Menunggu A3/A5.** |
| D4 | Peta invalid/stale dan command batas kecepatan/perubahan mendadak, satu fault per run lalu kombinasi. | Kode 5/10/11 sesuai prioritas gate, output nol, roda tidak bergerak; run ID menautkan sinyal/log/video. **Menunggu A3/A5.** |
| D5 | Putus kabel FPGA–Jetson ketika roda terangkat. | Kurir tidak mengulang command kedaluwarsa; STOP dan berhenti fisik terukur. Laporkan t_stop hasil A4, bukan nilai watchdog asumsi. **Menunggu A4/A11.** |
| D6 | Grafik waktu, Studi A/B, ringkasan equality dan fault. | Semua angka menyebut model, jenis bukti, N dan sumber. Gunakan 400/400 dan 9/9 hanya untuk regresi legacy terkait. Data belum ada ditulis “tidak diklaim”. **Menunggu B1–B4.** |
| D7 | Pengguna PERURI, retrofit, jejak audit, pembayaran dan langkah pilot. | Pengguna sasaran dan langkah pilot jelas; harga/TAM/payback diberi label estimasi, bukan kontrak/pendapatan aktual; tidak mengklaim sertifikasi atau keunikan finalis tanpa bukti. **Butuh review materi.** |

## Matriks safety yang harus dibuktikan

Prioritas gate adalah urutan pada tabel. Jika beberapa fault aktif, kode pertama menang. `permit=0`, `v_command=0`, `omega_command=0` untuk **setiap** kode 1–11. “Output nol” di sini berarti command digital; menghentikan energi/gerak mekanis perlu rem dan acceptance sistem fisik.

**Tabel kode berikut milik gate planner legacy**, bukan `error_code` policy baru. Pada `igor_src_policy_uart`, kode lokalnya ialah 1 E-stop, 2 framing, 3 header, 4 opcode, 5 panjang, 6 CRC, 7 inter-byte timeout, 8 rentang observasi, 9 busy, 10 core, 11 residual stale, 12 inference watchdog. Nama project dan namespace kode wajib dicatat pada log. Policy tidak menerima costmap; uji peta A3/D4 harus memakai planner+gate, dan belum membuktikan policy terhubung ke pemeriksa peta dalam chip. Untuk D3 planner, E-stop diharapkan kode 2; untuk guard policy, E-stop kode 1 dan residual nol.

| Kode | Pemicu | Edge case wajib |
|---|---|---|
| 0 | Semua syarat benar | Command nol dan nonnol; tepat pada limit kecepatan/delta; hasil normal setelah recovery yang sah. |
| 1 | Reset aktif | Power-on, reset saat RUN/RESULT, output tidak boleh glitch menjadi nonnol. |
| 2 | E-stop aktif | Sebelum start, saat RUN, setelah permit, saat UART TX; tahan aktif; kombinasi dengan semua fault berprioritas lebih rendah. |
| 3 | Protective stop | Saat permit dan selama run; E-stop+protective stop menghasilkan kode 2. |
| 4 | `ready=0` | Ready turun sesudah hasil valid; reset/estop tetap lebih tinggi. |
| 5 | Peta invalid | Belum ada peta, partial/truncated, alamat lompat, replay, sequence salah/wrap, unknown, stale, commit di saat salah; dua bank tidak boleh membuka peta setengah terkirim. |
| 6 | Konfigurasi invalid | Belum lock, write setelah lock, bit terlarang, reset/relock, write saat run; expected fault mengikuti prioritas peta/ready. |
| 7 | Arithmetic fault | Paksa overflow/error datapath yang didefinisikan dan pastikan hasil valid lama tidak dipakai. |
| 8 | Deadline/timeout | Satu cycle sebelum, tepat di, dan sesudah deadline; hasil terlambat tidak menghidupkan output; hasil/command lease kedaluwarsa. |
| 9 | Hasil tidak lengkap/tidak valid | Start tanpa hasil, satu evaluator belum selesai, semua kandidat blocked; start ganda dan result lama. |
| 10 | Batas absolut dilanggar | v=max dan max+1; omega ±max dan ±(max+1); omega signed minimum −64, maksimum +63; nilai 0; max limit 0. |
| 11 | Perubahan command dilanggar | Delta tepat max, max+1, kedua arah, −64→+63 dan +63→−64; prev=0; max_delta=0. Selisih harus diperlebar agar tidak overflow. |

Logger [igor_status_logger.v](../rtl/igor_status_logger.v) mencatat **transisi menuju kode fault nonnol yang berbeda**, bukan menambah counter setiap clock fault ditahan. Urutan 0→2→2 menambah sekali; 2→5 menambah lagi; 5→0 tidak menambah; 0→5 menambah lagi. Counter 32-bit saturasi di `0xffffffff`; `last_fault` mempertahankan kode nonnol terakhir. Sertakan baseline reset dan nilai sebelum/sesudah agar angka counter bisa diaudit.

Uji UART harus mencakup header/trailer salah, CRC salah, paket terpotong, idle gap, stop bit/framing salah, opcode/alamat tidak sah, input back-to-back, reset di tengah paket dan fault latched. CRC hanya mendeteksi korupsi; tidak mengautentikasi peta atau pengirim. Replay sequence dan freshness bukan HMAC. HMAC/secure element, motor acknowledgement, interlock fisik independen dan sertifikasi tetap roadmap sampai implementasi serta pengujiannya tersedia.

## Format bukti hardware yang bisa ditelusuri

Gunakan direktori baru per run, misalnya `evidence/hardware/20261016T150000+0700_A3/`. Waktu pada contoh nama folder hanya format, bukan rekaman uji. File minimum:

```text
manifest.json           # run_id, timezone, board/serial, model, commit/dirty, tools
sha256.csv              # SOF, QSF/SDC, weights, scripts, raw data, video
programmer.log          # device dan hasil programming aktual
fpga_uart_rx.bin        # bytes asli, tidak ditulis ulang dari angka yang diharapkan
courier.jsonl           # RX/TX, sequence, timestamp monotonic + wall-clock
cases.csv               # stimulus, expected, actual, PASS/FAIL, checkpoint
signals.stp_or_csv      # SignalTap/logic analyzer bila dipakai; nama alat nyata
video_index.csv         # filename, sha256, frame/time fault dan frame roda berhenti
results.md              # ringkasan kegagalan, batas bukti, recovery, reviewer
```

Schema satu baris `cases.csv`: `run_id,case_id,t_monotonic_ns,sequence,stimulus,expected_permit,actual_permit,expected_fault,actual_fault,fpga_v,fpga_omega,fpga_events,fpga_last_fault,courier_tx_zero,video_file,video_frame,result`. Untuk policy tiga output, simpan `residual_vx,residual_vy,residual_omega` dan **tambahkan** command motor yang berasal dari integrasi host; jangan mengganti nama residual menjadi output gate. Simpan satuan dan format Q pada manifest.

Syarat traceability A3/D3/D4: satu identitas run harus menghubungkan **input fault → output FPGA → safety status → logger → payload kurir → motor → video**. Untuk uji digital tanpa robot, isi motor/video sebagai `not_measured` dan label hasil SIMULASI/BOARD DIGITAL sesuai sumbernya. Jangan mengisi PASS fisik berdasarkan log simulasi.

Alat akuisisi planner tersedia pada [capture_hardware_safety.py](../verification/capture_hardware_safety.py). Contoh berikut **prosedur yang belum dijalankan pada board**; ganti port dan SOF dengan perangkat/project planner yang benar, pasang roda terangkat, dan aktifkan tombol E-stop fisik sebelum query:

```powershell
python verification/capture_hardware_safety.py --port COM5 --case H01_estop_held --output evidence/hardware/H01.jsonl --seconds 3 --expect-zero --expected-fault 2 --bitstream fpga_de10_nano/quartus/output_files/igor.sof
```

Mode default hanya query. Injeksi `--inject invalid-map-write` dan `--inject invalid-run-payload` harus diminta eksplisit saat uji terkontrol; expected fault masing-masing 5 dan 4 pada UART planner. Script menyimpan frame raw valid-CRC, timestamp, gate/output/event/last_fault dan menandai snapshot beberapa query sebagai non-atomic. Operasi ini **bukan protocol policy 153-byte**; jangan menjalankannya ke project policy baru. Untuk E-stop planner yang sudah sticky fault lain, reset dan siapkan baseline terlebih dahulu agar prioritas/latched reason tidak menutupi skenario uji.

## Ledger angka dan batas klaim

| Angka/klaim | Sumber yang sah | Label saat ini |
|---|---|---|
| Legacy 100 vektor, 400 output, 18.192 cycle | [neural_cocotb_results.json](../verification/neural_cocotb_results.json) dan source/model legacy terkait | ARSIP SIMULASI; board belum dibuktikan oleh file ini. |
| DWA enam scene, 7.938 cycle | [scene_cocotb_results.json](../verification/scene_cocotb_results.json) | ARSIP SIMULASI; tidak berarti semua peta mungkin terverifikasi. |
| Gate 13.078 kasus / 12 outcome | [gate_functional_coverage.json](../verification/gate_functional_coverage.json) | ARSIP SIMULASI; outcome coverage, bukan line/toggle/formal. |
| Sembilan skenario fault | [fault_status.csv](../evidence/current_safety/cases.csv) | ARSIP SIMULASI; sumber baru harus meregenerasi bukti terkait. |
| Current policy equality, latency dan error terhadap FP32 | `verification/src_policy/artifacts/results.json` dari runner saat ini | Pakai angka artifact aktual. Bit-exact merujuk model integer dengan quantization sama; FP32 hanya karakterisasi numerik. |
| Current safety regression | `evidence/current_safety/summary.json`, `cases.csv` dan hash source run yang sama | Pakai hasil run aktual; jumlah kasus bukan bukti semua state space/formal. |
| Resource/timing/SOF | Laporan Quartus dan SHA256 untuk **project dan build yang sama** | ARSIP atau BUILD BARU sesuai provenance; target 50 MHz tidak cukup untuk mengklaim timing pass. |
| Daya ±0,51 W | Laporan power vectorless historis | ESTIMASI; bukan board measurement. |
| Jetson latency, RTT, stop time, Studi A/B, daya board | A7/A8/A4/B1/B2/A14 | TIDAK DIKLAIM sampai raw data tersedia. |
| Harga Rp25 juta, TAM, balik modal | Proposal dengan asumsi/version | ESTIMASI; bukan penjualan/kontrak. |

## Kriteria freeze dan keputusan go/no-go

Sebelum demonstrasi gerak, A1–A6, A8 dan A13 harus memiliki bukti lulus pada **model dan bitstream yang didemokan**. A9–A11 melengkapi klaim lintasan/replay/video. Jika gagal, tampilkan demo digital yang benar-benar lulus dan beri label cakupannya. Jangan menghapus failure atau memperlakukan fallback sebagai keputusan FPGA.

Untuk freeze software: golden integer dan RTL core/UART lulus, model hash konsisten, safety regression lulus, pinplan sesuai project, Quartus compile dan timing project terkait diperiksa, CI memproduksi artifact baru, seluruh A/B/D mempunyai status dan owner aktual. Untuk freeze hardware: tambah programming/readback dan bukti fisik sesuai matriks. A14 opsional; B1/B2 boleh tetap tidak diklaim jika datanya belum ada, tetapi tidak boleh ditampilkan sebagai hasil selesai.
