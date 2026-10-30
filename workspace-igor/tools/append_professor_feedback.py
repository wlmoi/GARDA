"""Append measured Professor Feedback Audit to Bennaya.md, preserving its prefix."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
FPGA=ROOT/'fpga'
TARGET=FPGA/'Bennaya.md'
OUT=FPGA/'evidence/rtl_coverage'
MARKER='<!-- professor-feedback-audit-measured-v1 -->'
original=TARGET.read_bytes()
assert MARKER.encode() not in original,'Appendix already exists; review before updating'
coverage=json.loads((OUT/'coverage_summary.json').read_text())
for suite in ['core','uart','board','gate']:
    r=json.loads((OUT/suite/'receipt.json').read_text())
    assert r['status']=='PASS'
    for relative,digest in r['sha256'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative

text=r'''

<!-- professor-feedback-audit-measured-v1 -->

## Professor Feedback Audit: coverage, parameter implementasi dan bukti verifikasi

Bagian lanjutan ini menyatukan audit masukan dosen dengan **hasil pengukuran
coverage RTL**, parameter FPGA/ASIC dan referensi metodologi. Angka di sini
menggantikan status coverage awal yang belum terukur pada audit historis.
Istilah hasil yang dipakai adalah **verifikasi RTL terukur**, fitting FPGA,
STA dan estimasi implementasi; setiap hasil tetap mengikuti top serta tahapnya.

### Jawaban langsung untuk masukan dosen

Masukan mengenai jalur `if/else`, `case/default`, kondisi dan state yang belum
diuji ditanggapi melalui instrumentasi Verilator, inspeksi counter mentah,
penambahan fault injection dan pengujian ulang. Pada core Parallel8, satu
block `default` FSM semula belum tercapai. Tes tambahan menyuntikkan state
ilegal **15**, memeriksa keluaran tidak valid/nol dan **error 6**, lalu
memastikan reset memulihkan inferensi dengan latensi **6.916 siklus**.
Coverage line/block meningkat dari **67/68 (98,53%)** menjadi **68/68 (100%)**.
Tidak ada perubahan RTL produksi atau penghapusan jalur fault untuk memperoleh angka ini.

Cabang yang belum teruji tidak otomatis berarti ada latch. Latch dapat
terinferensi karena assignment logika kombinasi tidak lengkap; coverage
menilai aktivitas pengujian. Banyak testcase/assertion juga tidak otomatis
berarti functional coverage lengkap. Bahkan coverage 100% tidak membuktikan
semua input, urutan waktu, gangguan fisik atau ancaman security telah diuji.

Bukti utama: [hasil persentase lengkap](evidence/rtl_coverage/COVERAGE_RESULTS.md),
[receipt core](evidence/rtl_coverage/core/receipt.json),
[log core](evidence/rtl_coverage/core/simulation.log),
[tes state ilegal](verification/src_policy/coverage_illegal_state.svh), dan
[audit penjelasan gap](evidence/rtl_coverage/GAP_REVIEW.md).

### Cara menghitung dan menilai coverage

**Coverage (%) = jumlah bin dengan hit > 0 / seluruh bin DUT yang dihasilkan
instrumentasi x 100.** Counter testbench tidak ikut dihitung. Tidak ada waiver
manual dalam persentase mentah ini. Penyebut adalah counter yang benar-benar
diemisikan tool untuk elaborasi tersebut, bukan seluruh baris teks atau semua
kombinasi input HDL. Konstanta/elaborasi dan optimisasi tool memengaruhi bin;
persentase antar simulator tidak boleh dianggap langsung identik.

Simulator yang tercatat: **Verilator 5.018**, dengan `--timing --coverage --assert`;
compiler WSL menggunakan GCC. Script menyimpan command, SHA256 sumber,
testbench asli/salinan, bank bobot dan counter `coverage.dat`. Metrik native
yang muncul dipertahankan namanya: `v_line`, `v_branch`, `v_toggle`.
`v_line` adalah line/basic-block coverage, bukan klaim statement coverage
tekstual independen. Kategori yang tidak dihasilkan tetap ditulis belum diukur.

Kriteria berikut adalah **kebijakan review proyek**, bukan angka wajib ISO:

| Aspek | Target review | Syarat penilaian |
|---|---:|---|
| Tes/assertion wajib | 100% PASS | Jumlah tes yang diharapkan harus benar dan tidak ada failure/error. |
| Line/block dan branch | >=95% mentah | Jalur keselamatan/recovery yang tersisa ditinjau satu per satu. |
| Toggle | >=90% mentah | Bit konstan, encoding, counter dan domain stimulus dijelaskan. |
| Model requirement/scenario dan state/transisi legal yang dideklarasikan | 100% bin | Penyebut serta batas model harus tersedia. |
| Expression/condition | >=90% jika diukur | Tidak dapat digantikan oleh branch coverage atau pass rate. |
| MC/DC | Belum ditetapkan/diukur | Tidak ada klaim MC/DC dari data ini. |

[UCIS 1.0](https://www.accellera.org/downloads/standards/ucis) menjadi rujukan
interoperabilitas/semantik data coverage; tabel ini tidak berarti file `.dat`
proyek telah diekspor atau disertifikasi sebagai database UCIS. ISO/IEC 27090
membahas ancaman AI, bukan penetapan ambang code coverage. Definisi dan aturan
penilaian lengkap terdapat pada [panduan verifikasi](VERIFICATION_GUIDE.md).

### Persentase utama per modul dan suite

Persentase berikut memakai suite yang disebut pada setiap baris. File core
juga memuat logika aktivasi. Hasil ini tidak dirata-ratakan menjadi satu angka
yang dapat menyembunyikan gap pada transport atau wrapper.

| Modul / suite | Line/block | Branch | Toggle | Penilaian terhadap target proyek |
|---|---:|---:|---:|---|
'''

def value(suite,name,metric):
    found=[r for r in coverage if r['suite']==suite and Path(r['file']).name==name and r['metric']==metric]
    if not found: return 'Belum dihasilkan tool'
    r=found[0]
    return f"{r['percent']:.2f}% ({r['hit']}/{r['total']})"

primary=[('Core Parallel8','core','igor_src_policy_core.v','Memenuhi target line, branch dan toggle pada suite core.'),
         ('Transport policy','uart','igor_src_policy_uart.v','Line/branch memenuhi; toggle belum mencapai 90%.'),
         ('UART RX','uart','igor_uart_rx.v','Branch memenuhi; line dan toggle belum mencapai target.'),
         ('UART TX','uart','igor_uart_tx.v','Line/branch memenuhi; toggle belum mencapai 90%.'),
         ('Wrapper DE10-Nano','board','igor_src_policy_de10_nano.v','Line/branch memenuhi; toggle belum mencapai 90%.'),
         ('Safety gate','gate','igor_safety_security_gate.v','Line/toggle memenuhi; branch native tidak dilaporkan.')]
for label,suite,name,verdict in primary:
    text+=f"| {label} / `{suite}` | {value(suite,name,'v_line')} | {value(suite,name,'v_branch')} | {value(suite,name,'v_toggle')} | {verdict} |\n"

text+=r'''
**Mengapa toggle tidak semuanya 100%?** Sebagian bit adalah encoding atau
counter lebar yang tidak berubah pada domain legal/lamanya pengujian. Pada
safety gate, empat bit tinggi `fault_code[4..7]` tetap nol untuk kode 0..11;
`abs_dw[7]` tetap nol karena selisih absolut input signed 7-bit maksimal 127.
Wrapper board juga hanya menjalankan sejumlah kecil transaksi terarah sehingga
bit tinggi counter/debug belum aktif. Semua miss tetap masuk penyebut; tidak
ada angka toggle 100% yang diperoleh dengan mengecualikannya secara diam-diam.

Transport masih memiliki block default/recovery dan aktivitas data yang belum
seluruhnya tercapai pada suite terkait. Daftar setiap bin yang belum tercakup:
[core](evidence/rtl_coverage/core/uncovered.json),
[UART](evidence/rtl_coverage/uart/uncovered.json),
[board](evidence/rtl_coverage/board/uncovered.json), dan
[gate](evidence/rtl_coverage/gate/uncovered.json).
Gap ini membatasi klaim closure seluruh sistem meskipun tes fungsionalnya PASS.

### Semua hasil native, termasuk pengukuran di dalam suite integrasi

Pengujian core melalui UART/board memang tidak sama dengan suite unit core
yang mengakses input/start/abort secara langsung. Oleh karena itu tabel lengkap
tetap menyertakan hasil yang lebih rendah, tanpa memilih angka terbaik saja.

| Suite | File DUT | Metrik native | Covered / total | Persentase |
|---|---|---|---:|---:|
'''
for r in coverage:
    text+=f"| `{r['suite']}` | `{Path(r['file']).name}` | `{r['metric']}` | {r['hit']}/{r['total']} | {r['percent']:.2f}% |\n"

text+=r'''
### Functional coverage, FSM dan hasil pengujian

| Bukti / cakupan | Pembilang dan penyebut | Hasil dan batas interpretasi |
|---|---|---|
| Core bit-exact | 236 network vectors; 8.364 activation cases; 54.401 assertion checks | PASS; semua 192 hidden activation dan tiga output diperiksa per vector. Dua checks merupakan tambahan state ilegal/recovery terhadap baseline 54.399. Bukan 54.401 requirement independen. |
| UART policy | 184 directed transactions; 268 assertions | PASS; framing serial, numerik dan recovery. |
| Board wrapper | 18 checkpoints | PASS pada model clock 50 MHz dan divider 54 clock/bit untuk setting 921600 baud. |
| FSM: state legal | 8/8 = 100% | Model observasi fungsional dari VCD yang diikat ke hash RTL. |
| FSM: transisi normal | 10/10 = 100% | Sepuluh arc normal non-self-loop yang dideklarasikan; bukan semua arc reset/abort atau urutan temporal. |
| Gate: decision outcomes | 22/22 = 100% | Model sebelas keputusan prioritas, masing-masing true/false saat keputusan itu tercapai. Bukan native expression atau MC/DC. |
| Gate: outcome/fault bins | 12/12 = 100% pada 111.210 pembandingan oracle | Semua outcome 0..11 muncul; berbeda dari 13.078 kasus pada artefak gate legacy. |
| Safety unit/top/UART | 31 / 29 / 39 checkpoint bernama | PASS; total bersama 12 checkpoint gate = 111 checkpoint. Checkpoint bukan persentase seluruh requirement. |
| Host software fixtures | 29/29 tes = 100% pass rate | PASS; bukan code coverage Python atau uji motor fisik. |
| LiDAR fixtures | 16/16 tes = 100% pass rate | PASS; bukan pengukuran sensor fisik. |
| GLS terlampir | 1/1 testcase = 100% pass rate pada testcase terlampir | XML menyatakan PASS; bukan 100% gate/line/toggle coverage, bukan bukti semua vector neural atau anotasi SDF lengkap. |
| Expression/condition, MC/DC dan FSM native | Belum tersedia pengukuran persentase | Tidak diganti menjadi 0% atau 100%. |

Bukti model FSM: [JSON state/arc dan penyebut](evidence/rtl_coverage/fsm_observation.json).
Waveform sengaja tidak merekam vector 2..235; script hanya menghitung segmen
yang teramati dan tidak menginterpolasi celah. State ilegal diperiksa oleh
tes tambahan tersendiri. Bukti keputusan gate:
[JSON bin keputusan](evidence/rtl_coverage/gate_decision_model.json).

Rincian jumlah outcome gate pada run terbaru:

| Kode | Frekuensi outcome |
|---:|---:|
'''
safety=json.loads((FPGA/'evidence/current_safety/summary.json').read_text())
for code,count in sorted(safety['gate_fault_bins'].items(),key=lambda item:int(item[0])):
    text+=f'| {code} | {count:,} |\n'

text+=r'''
### Proses verifikasi dan cara menggunakannya

Jalankan perintah dari root repository. Icarus tersedia pada
`C:/iverilog/bin`; coverage memerlukan WSL, Verilator, make dan C++ compiler.
Runner menyimpan log dan hasil, serta menghentikan proses bila assertion atau
pembandingan oracle gagal. Tidak ada perintah berikut yang memprogram board
atau menggerakkan motor.

| Tahap | Tujuan dan proses pemeriksaan | Perintah / hasil |
|---|---|---|
| 1. Provenance dan baseline policy | Periksa ekspor bobot/MEM, hasilkan vector referensi integer independen, uji rounding, saturation, hidden activation dan output RTL. | `python fpga/verification/src_policy/run.py --check`; hasil pada `verification/src_policy/artifacts/`. |
| 2. Baseline board wrapper | Kirim bit UART ke wrapper aktual, uji reset dua tahap, KEY inhibit/latch dan respons numerik. | `python fpga/verification/run_board_wrapper.py`; hasil pada `evidence/current_board_wrapper/`. |
| 3. Parallel8 | Jalankan core, UART dan board benches terhadap vector golden yang sama; periksa kesetaraan numerik dan siklus kandidat. | `python fpga/experiments/parallel8/run.py`; hasil pada `experiments/parallel8/artifacts/`. |
| 4. Safety gate | Bentuk 1.024 kombinasi kontrol, domain/batas numerik dan random seed tetap; bandingkan prioritas fault, enable dan keluaran dengan oracle. | `python fpga/verification/run_safety_regression.py`; hasil gate, units, top, UART dan `cases.csv` pada `evidence/current_safety/`. |
| 5. Host | Fixture menjalankan bridge/controller untuk input NaN/range, respons salah, CRC, timeout, late reply, fault latch dan command/sensor freshness. | `python fpga/verification/run_host_regression.py`; `evidence/current_host/results.json`. |
| 6. LiDAR | Parser production menerima data terfragmentasi/rusak, bin hilang/duplikat dan timestamp usang; publikasi scan harus memenuhi kontrak. | `python fpga/verification/run_lidar_regression.py`; `evidence/current_lidar/results.json`. |
| 7. Instrumentasi core | Salin bench, pertahankan stimulus/assertion, tambahkan tes state ilegal; compile dengan coverage, simulasi, baca counter hanya dari file DUT. | `python tools/run_rtl_coverage.py --suite core`. |
| 8. Instrumentasi transport/board/gate | Jalankan tiap suite terpisah; input scan gate memakai temporary register untuk scheduling compiled simulator tanpa mengubah vector/oracle. | Ulangi command tahap 7 dengan `--suite uart`, `--suite board`, `--suite gate`. |
| 9. Model FSM dan keputusan | Cocokkan state/arc VCD dengan daftar legal yang eksplisit; hitung keputusan gate hanya setelah syarat prioritas sebelumnya tidak aktif. | `python tools/measure_core_fsm.py`; `python tools/measure_gate_decisions.py`. |
| 10. Inventaris dan ringkasan | Indeks definisi Python `test_*` dan checkpoint SV dengan source line; kumpulkan persen, pembilang dan penyebut. | `python tools/build_verification_inventory.py`. |
| 11. Validasi paket | Pastikan keempat receipt PASS, log memuat PASS, hash source tetap sama dan semua persen cocok dengan pembilang/penyebut. | `python tools/finalize_verification_evidence.py`; paket `evidence/rtl_coverage_evidence.zip`. |
| 12. Build FPGA, bila RTL berubah | Regresi kandidat kemudian compile, fitting dan STA. | `python fpga/experiments/parallel8/run.py --build`; bukan GLS atau pengukuran power fisik. |

Untuk menjalankan suite Cocotb legacy, gunakan
`python fpga/verification/run.py gate` (atau `neural`, `top`, `uart`, `tt`).
Top/protokolnya harus sesuai; hasil legacy tidak disamakan dengan Parallel8.
Runner `tt_sram` memang ditandai archived. [Panduan lengkap](VERIFICATION_GUIDE.md)
mencakup dependensi, keluaran, cara membaca hasil dan batas setiap suite.

[Inventaris 287 definisi tes/checkpoint](evidence/rtl_coverage/TEST_INVENTORY.md)
memuat nama, uraian dan source line. Angka 287 adalah inventaris definisi,
bukan jumlah seluruh tes yang terbukti dieksekusi. Gunakan log/receipt untuk
menghubungkan definisi dengan run aktual, seed dan hash sumbernya.

### Parameter arsitektur, performa dan PPA

| Parameter | Nilai / interpretasi | Bukti |
|---|---|---|
| Neural policy | 74 input, hidden 128 dan 64, tiga residual output; PPO source IGOR | [Provenance model](verification/src_policy/artifacts/model_provenance.json), [bobot source](../src/igor_navigation/igor_navigation/weights/model_weights.json). |
| Parameter model | 18.051 words termasuk bias; storage 32.768 words x 16 bit = 64 KiB | Provenance model dan Fitter; kapasitas storage berbeda dari parameter terpakai. |
| Datapath | Delapan lane MAC, operand input dibroadcast, delapan bank bobot dan hidden storage terbagi bank | [RTL Parallel8](experiments/parallel8/igor_src_policy_core.v), [generator bank](experiments/parallel8/prepare.py). |
| Aritmetika | Q8.8; perkalian signed 16x16; accumulator signed 40-bit; floor shift 8 bit; hidden signed16 jenuh/ReLU; output clip -256..256 | RTL dan reference integer. |
| Clock dan latency | 50 MHz, periode 20 ns; 6.916 siklus = 138,32 us | Log core dan [STA FPGA](experiments/parallel8/output_files/igor_src_policy.sta.summary). |
| Baseline | 54.348 siklus = 1.086,96 us; speedup 54.348/6.916 = 7,858x | [Perbandingan kandidat](experiments/parallel8/README.md). |
| Operasi / throughput | 74x128 + 128x64 + 64x3 = 17.856 MAC/inference; 129,092 MMAC/s; ideal kernel-only 7.229,61 inference/s | Perhitungan berdasarkan model dan latency; tidak termasuk loading/UART/host. |
| Resource | 3.303/41.910 ALM; 6.277 registers; 64/553 M10K; 8/112 DSP; 13 pin | [Fitter summary](experiments/parallel8/output_files/igor_src_policy.fit.summary). |
| Resource tambahan | +54 ALM, +281 registers, +7 DSP; M10K tetap 64 dibanding baseline | Perbandingan kandidat. |
| STA FPGA | Worst setup +5,647 ns, worst hold +0,119 ns, TNS 0 pada corner dilaporkan; WNS pelanggaran negatif = 0 | STA FPGA; bukan hasil ASIC. |
| Typical FPGA power | Total 476,18 mW; dynamic 50,36 + static 413,27 + I/O 12,55 mW | [Power Typical](experiments/parallel8/artifacts/power/typical/igor_src_policy.pow.summary); vectorless, confidence Low, bukan daya board. |
| Maximum/Tj100 power | Total estimasi 937,55 mW | [Power maximum](experiments/parallel8/artifacts/power/maximum_tj100/igor_src_policy.pow.summary); confidence Low. |
| Energy ilustratif | Total-power x core-time sekitar 65,87 uJ/inference; dynamic-only sekitar 6,97 uJ | Estimasi dengan asumsi daya konstan selama kernel, bukan pengukuran transaksi. |
| UART | 921600 baud, 8N1, request 153 byte/74 signed int16 LE, response 11 byte/tiga signed int16 LE, CRC-8/MAXIM | [RTL transport](rtl/igor_src_policy/igor_src_policy_uart.v), [bridge host](software_integration/src/igor_controller/igor_controller/fpga_bridge.py). |
| Wire time | 164 byte x 10/921600 sekitar 1,7795 ms; ditambah core sekitar 1,9178 ms sebelum overhead lain | Batas waktu ideal; bukan benchmark round-trip Jetson. |

Percepatan berasal dari delapan neuron yang dihitung bersamaan. Urutan
penjumlahan tiap neuron tetap sehingga kesetaraan integer dapat dipertahankan.
Typical total power naik 11,97 mW atau sekitar 2,58%; peningkatan utama adalah
latensi dan estimasi energi kernel, bukan semua metrik sekaligus. [README
Parallel8](experiments/parallel8/README.md) menjelaskan pilihan banking dan
iterasi elaborasi yang mendahului implementasi yang diterima.

### Parameter ASIC protocol engine: lingkup terpisah

Arsip `gds-diagnostics-1.zip` memiliki SHA256
`1e41c73286b1c053fc08f3c031c4424dd7aa44c06dff380925f5e40393589506`.
Top arsip adalah **tt_um_igorchip**, berbeda dari neural FPGA; belum ada
bukti ekuivalensi keduanya. Berikut hasil diagnostik implementasinya:

| Parameter ASIC | Nilai dan batas |
|---|---|
| Teknologi | PDK `ihp-sg13cmos5l`, keluarga IHP 130 nm; constraint clock 20 ns. |
| Die / core area | 0,916214 / 0,902417 mm2. |
| Cell | 5.316 standard cells + satu macro; total 71.108 instances mencakup 65.791 fill cells, bukan jumlah gerbang logika ekuivalen NAND2. |
| Memori program | Macro 256x16-bit = 512 byte; berbeda dari storage bobot FPGA 64 KiB. |
| Typical power | 2,037372 mW pada 1,20 V/25 C; internal 1,663574, switching 0,323768, leakage 0,050029 mW; estimasi post-route. |
| Corner power lain | Fast 1,32 V/-40 C: 2,662040 mW; slow 1,08 V/125 C: 1,620704 mW. |
| Timing diagnostik | Slow setup WNS -2,637272 ns, TNS -258,604708 ns, 253 setup violations; worst hold +0,107577 ns. |
| Pemeriksaan fisik | KLayout DRC 0, LVS error 0 dan route DRC 0; 42 illegal overlaps serta 26 slew, 11 cap dan 58 fanout violations masih tercatat. |
| Konfigurasi pemeriksaan | `RUN_MAGIC_DRC=false`, `ERROR_ON_ILLEGAL_OVERLAPS=false`; nol error pada pemeriksaan lain tidak menghapus temuan overlap. |
| Artefak arsip | 614 member; ZIP yang diperiksa tidak memuat file `.gds`, `.gdsii`, `.oas`. Laporan diagnostik bukan pengganti layout final. |

Sumber: [ringkasan ASIC](evidence/asic_import/gds_diagnostics_1/summary.json),
[199 metrik final](evidence/asic_import/gds_diagnostics_1/final_metrics.csv),
[power Typical raw](evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/56-openroad-stapostpnr/nom_typ_1p20V_25C/power.rpt),
dan [keterangan GLS](evidence/asic_import/gatelevel_test_results/summary.json).
Angka power protocol engine tidak digunakan untuk mengklaim energi inferensi
neural Parallel8. Status tahap implementasi mengikuti temuan di atas.

### Integritas numerik, safety dan korelasi ISO/IEC 27090:2026

[ISO/IEC 27090:2026](https://www.iso.org/standard/27090) berjudul
*Cybersecurity - Artificial intelligence (AI) - Addressing security threats
and compromises to AI systems*. ISO mencatat publikasinya pada 14 Oktober
2026. Standar memberi panduan ancaman AI sepanjang lifecycle, termasuk
data poisoning dan pencurian model, serta melengkapi ISO/IEC 27001/27002.
Pemetaan ini merupakan interpretasi engineering atas cakupan publik, bukan
audit klausul penuh atau pernyataan sertifikasi.

| Risiko / fungsi | Mekanisme yang tersedia | Batas bukti |
|---|---|---|
| Paket/input rusak | Header, length, CRC, domain input 0..63 dalam [0,1], input 64..73 dalam [-1,1] | CRC mendeteksi error transfer, bukan autentikasi atau perlindungan input adversarial yang masih dalam range. |
| Transaksi macet/hasil usang | Busy rejection, watchdog, freshness, abort dan host fault latch | Belum membuktikan ketahanan flooding/DoS, replay, atau seluruh interleaving. |
| Konsistensi model | Bobot ROM, ekspor terverifikasi dan hash sumber/bukti | Hash bukan secure boot, signature verification, anti-rollback atau proteksi JTAG. |
| Dampak numerik | Saturation/clipping, invalid-result gate dan KEY inhibit | Residual nol bukan perintah STOP motor; output terbatas belum tentu aksi navigasi aman. |
| Kepemilikan I/O | `pin_mask` pada protocol engine ASIC | Bukan fitur autentikasi UART neural; top yang berbeda harus disebut. |
| Integrasi keselamatan | Fault handling host dan safety gate planner tersedia | Penyatuan residual neural, pemeriksa peta, kinematika dan motor sepenuhnya di FPGA belum dibuktikan. |
| Lifecycle AI | Hasil deterministik memudahkan reproduksi | Provenance dataset, secure training/update, pengujian backdoor/model extraction/side channel memerlukan bukti tambahan. |

Peta error berbeda menurut blok: core neural **1..6**, UART policy **1..12**,
safety gate **0..11** (0 = permit), dan protocol engine mempunyai kontraknya
sendiri. Jangan memakai satu daftar kode untuk mewakili seluruh sistem.
ISO tidak menyebabkan speedup; paralelisasi menyebabkan speedup, sementara
kontrol integritas/fault membantu menjaga kepercayaan hasil dalam threat model
yang diuji.

### Referensi arsitektur dan asal keputusan desain

Referensi dipisahkan antara **asal model yang terbukti**, **implementasi lokal**,
dan **bacaan konseptual tambahan**. Tidak ada bukti bahwa kode Parallel8 disalin
atau diturunkan langsung dari paper akselerator tertentu.

| ID | Referensi | Bagian yang didukung dan cara menggunakannya |
|---|---|---|
| R01 | [Model provenance IGOR](verification/src_policy/artifacts/model_provenance.json) dan [model source](../src/igor_navigation/igor_navigation/weights/model_weights.json) | Sumber primer bentuk 74-128-64-3, bobot, bias dan tata letak word. Arsitektur layer ini berasal dari artefak model lokal, bukan angka yang ditetapkan oleh paper PPO. |
| R02 | [RTL Parallel8](experiments/parallel8/igor_src_policy_core.v), [prepare.py](experiments/parallel8/prepare.py), [README eksperimen](experiments/parallel8/README.md) | Sumber primer delapan lane MAC, broadcast operand, banking dan urutan penjumlahan. Pelajari pembagian neuron per grup dan alamat bobot untuk mereproduksi arsitektur. |
| R03 | Schulman et al., 2017, [Proximal Policy Optimization Algorithms](https://arxiv.org/abs/1707.06347) | Rujukan algoritma PPO. Tidak menjadi bukti konfigurasi layer lokal, hasil training/akurasi navigasi, atau implementasi delapan lane. |
| R04 | [MIT Eyeriss Project](https://eyeriss.mit.edu/) dan [penjelasan dataflow oleh peneliti MIT](https://eems.mit.edu/research/) | Bacaan pembanding tentang pemrosesan paralel, reuse dan biaya perpindahan data. Eyeriss membahas dataflow row-stationary CNN; Parallel8 adalah MLP dengan neuron paralel, bukan klaim implementasi Eyeriss/systolic array yang sama. Dicantumkan sebagai bacaan tambahan, bukan riwayat inspirasi yang telah dibuktikan. |
| R05 | [Verilator: coverage dan simulasi](https://verilator.org/guide/latest/simulating.html), [coverage tool](https://verilator.org/guide/latest/exe_verilator_coverage.html) | Referensi cara instrumentasi/counter dan interpretasi coverage. Dokumentasi latest dapat mencakup fitur lebih baru daripada versi 5.018 yang tercatat; hanya counter aktual run yang dilaporkan. |
| R06 | [Accellera UCIS 1.0](https://www.accellera.org/downloads/standards/ucis) | Rujukan semantik/interoperabilitas data coverage; bukan kewajiban ambang 95%/90% dan bukan bukti database proyek telah conformant. |
| R07 | [ISO/IEC 27090:2026](https://www.iso.org/standard/27090) | Rujukan cakupan ancaman AI dan lifecycle. Pemetaan kontrol di atas tidak menggantikan audit standar lengkap. |
| R08 | [Runner dan oracle baseline](verification/src_policy/run.py), [safety oracle](verification/run_safety_regression.py), [coverage runner](../tools/run_rtl_coverage.py) | Referensi praktis membentuk stimulus independen, mengikat source hash dan mengukur coverage. Dasar klaim hasil tetap log/receipt, bukan teori paper saja. |

### Bukti visual dan paket untuk reviewer

![Ringkasan coverage terukur](evidence/rtl_coverage/coverage_summary.png)

Gambar di atas adalah render dari JSON hasil, bukan screenshot simulator.
Counter, log dan hash tersedia untuk pemeriksaan ulang.

![Waveform core Parallel8](experiments/parallel8/artifacts/core_latency.png)

Screenshot GTKWave existing memperlihatkan `latency_cycles=0x1B04=6916` serta
busy/done. Ini waveform simulasi, bukan osiloskop atau pengukuran board.

![Penolakan CRC pada jalur policy](evidence/visual_review/09_policy_crc_reject.png)

Screenshot existing menunjukkan error 0x06, rejected frame bertambah dan
permit/action tidak dilepas pada frame CRC salah. Ini ilustrasi jalur policy
shared, bukan persentase coverage keseluruhan.

Reviewer dapat membuka [manifest hash](evidence/rtl_coverage/manifest.json),
[CSV persentase](evidence/rtl_coverage/coverage_summary.csv),
[inventaris tes](evidence/rtl_coverage/test_inventory.csv),
[panduan semua suite](VERIFICATION_GUIDE.md), serta
[paket bukti ZIP](evidence/rtl_coverage_evidence.zip).

**Kalimat presentasi berbasis bukti:** “The Parallel8 core was rigorously
verified within the stated RTL simulation scope using independent reference
checks, fault injection, and measured code coverage: 100% line/block,
100% branch, and 95.81% toggle coverage. Integration coverage and remaining
transport, physical implementation and security validation tasks are reported
separately.”
'''

TARGET.write_bytes(original+text.encode('utf-8'))
assert TARGET.read_bytes().startswith(original),'Existing document changed'
assert TARGET.read_text(encoding='utf-8').count(MARKER)==1
record={'target':'fpga/Bennaya.md','operation':'append only',
        'original_bytes':len(original),'original_sha256':hashlib.sha256(original).hexdigest(),
        'appended_bytes':len(text.encode('utf-8')),'final_sha256':hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        'coverage_source':'fpga/evidence/rtl_coverage/coverage_summary.json'}
dest=FPGA/'evidence/bennaya_answers/professor_feedback_append_receipt.json'
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
