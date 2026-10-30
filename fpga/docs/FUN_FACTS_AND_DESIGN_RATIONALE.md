# IGOR Parallel8: fun facts, keputusan desain dan keunggulan yang terukur

19 Oktober 2026. Profil: **PPO 74→128→64→3**, Parallel8, DE10-Nano **5CSEBA6U23I7**, clock **50 MHz**, UART nominal **921600 baud**. Tujuan dokumen: menjelaskan *mengapa* arsitekturnya dipilih, bagaimana data bergerak, dan apa yang dibuktikan angka implementasi. Semua path relatif terhadap dokumen ini. Ini dokumentasi atas implementasi yang sudah ada; tidak ada perubahan RTL atau SOF.

**Pesan utama:** IGOR memakai delapan jalur perkalian paralel, parameter lokal dan aritmetika fixed-point untuk menyelesaikan core inferensi dalam **138,32 µs**, dengan **3.303 ALM total, 64 M10K dan 8 DSP**. Kekuatan desain terletak pada kesesuaian target, pengelolaan data, perilaku yang terdefinisi dan bukti yang dapat dilacak. “Paling bagus” di sini berarti keputusan yang kuat untuk kebutuhan IGOR; klaim terbaik universal memerlukan benchmark dengan workload dan batas sistem yang sama.

## 1. Peta angka yang paling menarik

| Fakta | Angka | Apa artinya |
|---|---:|---|
| Model dipertahankan | 74→128→64→3 | Arsitektur mengikuti policy software, bukan jaringan demonstrasi yang diperkecil |
| Weights aktif | **17.856** | 74×128 + 128×64 + 64×3 |
| Bias aktif | **195** | 128 + 64 + 3 |
| Total parameter aktif | **18.051** | Weights + bias, terikat model sumber |
| Parallelism | **8 lane** | Delapan neuron dalam satu grup berbagi operand |
| Latensi core | **6.916 siklus = 138,32 µs** | Start-ke-done pada 50 MHz, bukan seluruh transaksi host |
| Margin terhadap 160 µs | **21,68 µs / 13,55%** | Target core tercapai pada build yang sama |
| ALM seluruh top | **3.303/41.910 = 7,8812%** | GUI Quartus membulatkan menjadi 8% |
| ALM core saja | **2.402,7 = 5,7330% kapasitas** | Atribusi hierarchy core inclusive, bukan standalone fit |
| Core + UART policy | **3.300,7 ALM** | Termasuk parser, buffer, validasi dan penjagaan transaksi |
| Parameter memory | **64 KiB configured** | 8×4.096×16 bit, 64 M10K |
| DSP | **8/112 = 7,1429%** | Delapan signed multiplier terpetakan ke DSP |
| PLL | **0/6** | Clock board 50 MHz digunakan langsung |
| Pin top | **13/314 = 4,1401%** | 1 clock + 2 KEY + RX/TX + 8 LED |
| Worst setup/hold | **+5,647/+0,119 ns** | Multicorner timing summary tersimpan |
| Fmax slow 100°C | **69,67 MHz** | Analisis tool; clock operasi tetap 50 MHz |
| Pengujian core | **54.399 assertions** | Termasuk hidden/output integer, kontrol dan activation |
| Inferensi UART fisik | **98/98**, mean **4,594 ms**, max **5,920 ms** | Hasil transaksi nyata pada sesi 18 Oktober, cakupan berbeda dari core latency |

Bukti primer: [acceptance Parallel8](../experiments/parallel8/artifacts/acceptance.json), [hierarchy Fitter](../experiments/parallel8/output_files/igor_src_policy.fit.rpt:1411), [GUI Quartus asli](../evidence/quartus_gui/README.md), [sesi fisik](../../final_docs.md). Ledger perhitungan dan SHA: [design_funfacts.json](../evidence/design_funfacts/design_funfacts.json).

## 2. Tanpa PLL: target dicapai lewat arsitektur

**Fakta:** top menghubungkan `FPGA_CLK1_50` langsung ke policy/core. SDC menyatakan period 20 ns. GUI melaporkan **0 PLL** dan satu clock 50 MHz. [RTL top](../experiments/parallel8/igor_src_policy_de10_nano.v), [clock GUI](../evidence/quartus_gui/10_clock_50mhz.jpg), [resource GUI](../evidence/quartus_gui/02_fitter_summary.jpg).

**Mengapa masuk akal:** 6.916 siklus pada 50 MHz sudah memenuhi 160 µs. Secara aritmetika, 6.916/160 µs = **43,225 MHz** menghasilkan tepat 160 µs; untuk target *strictly below* 160 µs diperlukan lebih dari angka tersebut. Ini bukan hasil build baru pada 43,225 MHz. Clock board yang tersedia memberi margin tanpa kebutuhan menambah PLL, generated-clock constraint atau ketergantungan sinyal PLL lock.

Clock internal tunggal juga membuat hubungan register di dalam core mudah dianalisis. UART RX dan tombol tetap asynchronous terhadap clock, sehingga sinkronisasi/reset dan constraint masih diperlukan; “satu domain clock” tidak berarti tidak ada CDC sama sekali. Top menggunakan reset release dua register; RX mempunyai jalur sinkronisasi tersendiri.

**Kalimat publikasi:** “Target latensi dicapai pada clock board 50 MHz tanpa PLL, melalui penjadwalan komputasi delapan lane.”

Jangan menjelaskan ketiadaan PLL sebagai “tidak pernah ada implementasi lebih cepat” atau “ASIC pasti sudah cukup”. Bukti mendukung kecukupan **clock FPGA 50 MHz untuk target core ini**. Kecepatan ASIC memerlukan mapping dan STA ASIC untuk desain neural yang sama. Fmax 69,67 MHz tidak membuktikan image berjalan pada frekuensi tersebut. [Fmax GUI](../evidence/quartus_gui/11_fmax_slow100c.jpg).

## 3. Parallelism dipilih pada sumbu neuron

Setiap neuron menghitung `bias + Σ(input × weights)`. Pada satu layer, banyak neuron memerlukan input yang sama. IGOR menyiarkan satu `operand[15:0]` ke delapan lane; tiap lane membaca weights berbeda dan memiliki `accumulator[39:0]` sendiri.

```text
                         operand[15:0]
                    broadcast ke 8 lane
               /          |             \
bank0 weights[15:0]   bank1 weights   ... bank7 weights
        |                   |                 |
    multiplier          multiplier        multiplier
 product[31:0]        product[31:0]      product[31:0]
        |                   |                 |
accumulator[39:0]   accumulator[39:0] ... accumulator[39:0]
        |                   |                 |
 ReLU / clamp          ReLU / clamp        ReLU / clamp
```

Dengan cara ini, parallelism tidak memerlukan delapan pembacaan input independen. Akses weights dibagi ke delapan bank; input dipakai ulang. Semua lane tetap menyelesaikan urutan penjumlahan neuron yang sama dengan baseline serial. Tidak ada adder tree baru yang mengubah pengelompokan operasi atau urutan saturasi. [Datapath RTL](../experiments/parallel8/igor_src_policy_core.v), [diagram editable](assets/igor_core_simple.drawio).

## 4. Mengapa delapan lane sangat cocok dengan bentuk jaringan

Hidden pertama mempunyai 128 neuron: **16 grup × 8**. Hidden kedua mempunyai 64 neuron: **8 grup × 8**. Kedua layer itu habis dibagi delapan sehingga seluruh lane dipakai pada setiap grupnya. Layer output hanya tiga neuron; lima lane terakhir diisi weights/bias nol dan hanya tiga action ditulis.

Total grup: **16+8+1 = 25**. Total slot neuron yang dijadwalkan: **25×8 = 200**, dengan **195 neuron berguna = 97,5% slot**. Ini adalah pemakaian *slot neuron*, bukan persentase DSP aktif setiap clock dan bukan efisiensi energi. Core tidak menulis `actions[3..7]`; tail akhir ditangani eksplisit. [Layout dan edge cases](../experiments/parallel8/README.md).

## 5. Kecepatan tumbuh jauh lebih cepat daripada ALM

| Besaran, model sama | Baseline serial | Parallel8 | Implikasi |
|---|---:|---:|---|
| Siklus inferensi | 54.348 | 6.916 | **7,8583×** percepatan core |
| Latensi 50 MHz | 1,08696 ms | 0,13832 ms | **87,2746%** pengurangan |
| ALM top | 3.249 | 3.303 | **+54 ALM = +1,6620%** terhadap baseline |
| Register | 5.996 | 6.277 | **+281** |
| M10K | 64 | 64 | **Tidak bertambah** |
| DSP | 1 | 8 | Tambahan tujuh DSP untuk tujuh lane komputasi |

Ini argumen efisiensi yang kuat: paralelisasi memanfaatkan hardware multiplier yang tersedia dan banking yang terencana, sehingga biaya penambahan ALM kecil pada hasil fit ini. Ini bukan bukti bahwa DSP bebas biaya atau setiap model akan memperoleh rasio yang sama. Sumber: [baseline summary](../fpga_de10_nano/src_policy/output_files/igor_src_policy.fit.summary), [Parallel8 summary](../experiments/parallel8/output_files/igor_src_policy.fit.summary).

Rasio speedup terhadap ideal delapan kali adalah **98,2287%**. Angka itu hanya membandingkan kedua jadwal inferensi; tidak sama dengan pemakaian multiplier tiap clock atau parallel efficiency universal.

## 6. Mengapa menggunakan DSP block

Perkalian signed 16×16 menghasilkan product signed 32-bit. FPGA menyediakan hardware aritmetika khusus. Quartus mengenali operasi perkalian HDL dan memetakannya ke DSP; GUI menunjukkan **8 fixed-point signed multipliers** dan **8 DSP blocks**. Logika ALM tetap digunakan untuk kontrol, routing data, pemilihan operand, akumulasi/aktivasi sesuai hasil mapping. [DSP GUI](../evidence/quartus_gui/08_dsp_summary.jpg).

Manfaat desainnya: multiplier tidak harus seluruhnya dibangun dari tabel logika umum, sementara ALM dapat dipakai untuk FSM, validasi dan interface. Ini pilihan implementasi hardware, bukan sekadar label “AI accelerator”. Dokumentasi resmi menjelaskan inferensi multiplier/DSP/memory dan kemampuan variable-precision Cyclone V [P1][P2]. Kita tidak mengklaim seluruh adder accumulator 40-bit sudah masuk DSP tanpa melihat netlist terpetakan.

Cyclone V mempunyai beberapa mode DSP. Karena itu **8 multiplier logis tidak secara universal berarti harus 8 DSP** pada setiap struktur HDL. Yang membuat angka delapan sah di IGOR adalah hasil Fitter aktual, bukan perkiraan dari jumlah operasi. Pemadatan multiplier atau MAC inference lain adalah eksperimen lanjutan, bukan optimasi yang sudah diklaim.

## 7. Reuse hardware: 17.856 weights tidak berarti 17.856 multiplier

Ada **17.856 koneksi berbobot** per inferensi, tetapi hardware hanya mempunyai delapan lane perkalian. Masing-masing lane dipakai lagi untuk input berikutnya, grup neuron berikutnya dan layer berikutnya. Weights berpindah dari bank ROM ke datapath secara terjadwal; unit aritmetika yang sama menjalankan banyak operasi sepanjang waktu.

Dengan 195 neuron komputasional dan 8 lane, rata-rata terdapat **24,375 neuron berguna per lane per inferensi**, bukan satu multiplier permanen untuk tiap neuron. Ini menjelaskan bagaimana desain mempertahankan model penuh dengan pemakaian DSP yang terbatas.

## 8. Bagaimana 6.916 siklus terbentuk

| Layer | Grup | Input per grup | Rumus jadwal | Siklus |
|---|---:|---:|---|---:|
| 74→128 | 16 | 74 | 16×(3×74+4) | **3.616** |
| 128→64 | 8 | 128 | 8×(3×128+4) | **3.104** |
| 64→3 | 1 | 64 | 1×(3×64+4) | **196** |
| Total | 25 | | | **6.916** |

Faktor tiga mencerminkan jadwal akses weight sinkron dan MAC, bukan satu operasi floating-point selama tiga siklus. FSM core memiliki delapan state bernama: IDLE, BIAS_ADDRESS, BIAS_WAIT, BIAS_TAKE, WEIGHT_ADDRESS, WEIGHT_WAIT, MAC dan ACTIVATE. Storage sinkron diberi state tunggu eksplisit agar operand/weight yang dipakai sesuai alamatnya.

CSV menyimpan contoh start cycle **499** dan done **7.415**, selisih **6.916**; transaksi berikutnya **7.491→14.407** memberi selisih sama. Ini menjelaskan deterministic core latency untuk inferensi valid yang selesai, bukan janji bahwa frame malformed atau abort mempunyai waktu selesai inferensi yang sama. [Cycle checkpoints](../experiments/parallel8/core_checkpoints.csv), [FSM](FSM_3_SIMPLE.md).

## 9. Throughput dijelaskan dengan denominator yang benar

Upper bound core, tanpa waktu memuat input/host: `50.000.000/6.916` = **7.229,61 inferensi/detik**. Pekerjaan berguna per inferensi = 17.856 MAC berbobot, sehingga ekuivalen **129,092 juta MAC/detik**. Jika satu multiply dan satu add dihitung dua operasi, nilainya **258,184 juta operasi/detik = 0,258184 GOPS**. Bias/activation/transport tidak dihitung dalam definisi ini.

Delapan multiplier pada 50 MHz memberi batas aritmetika mentah 400 juta perkalian/detik *jika* semuanya menerima data baru setiap siklus. Jadwal IGOR saat ini tidak bekerja begitu: ada akses memori, state tunggu dan tail output. Karena itu jangan memasarkan 400 MMAC/s sebagai sustained core throughput terukur.

Batas teoritis core juga bukan throughput UART nyata. Pemisahan ini justru membantu proses desain: ketika core telah cepat, optimasi berikutnya dapat diarahkan ke transport dan buffering sesuai kebutuhan aplikasi.

## 10. Parameter lokal: komputasi tidak menunggu DDR eksternal

Seluruh parameter core tersedia di fabric dalam delapan bank ROM sinkron. Jalur inferensi tidak memerlukan HPS Linux, DDR eksternal, cache miss atau transfer bobot baru pada setiap inferensi. Host tetap mengirim observasi, bukan seluruh model. Ini mengurangi ketergantungan runtime terhadap lalu lintas parameter eksternal, bukan bukti penghematan daya yang telah diukur tersendiri.

GUI menunjukkan **8 bank logis 4.096×16 bit**. Totalnya **524.288 bit = 65.536 byte = 64 KiB**. Setiap bank dipetakan memakai delapan M10K; keseluruhan **64 M10K**. [RAM GUI](../evidence/quartus_gui/07_ram_summary.jpg).

Saat delapan bank dibaca bersamaan, delapan word 16-bit menyediakan **128 bit = 16 byte weights** di sisi internal, sementara operand broadcast hanya **16 bit**. Lebar paralel internal ini tidak memerlukan 128 pin eksternal: seluruh transfer terjadi di dalam FPGA. Ini hubungan konkret antara memory banking, parallelism dan interface serial yang ringkas.

M10K merupakan block memory FPGA berbasis SRAM yang di sini diinisialisasi dan **digunakan sebagai ROM parameter**. Ini berbeda dari macro SRAM hasil fabrikasi ASIC. Model baru memerlukan export, banking dan validasi image baru; mengubah satu string ROM_FILE tidak cukup karena Parallel8 benar-benar memakai `bank0.mem` sampai `bank7.mem`.

## 11. Mengapa memori dialokasikan lebih besar dari parameter aktif

Parameter aktif berjumlah **18.051 word × 16 = 288.816 bit = 36.102 byte**. Dibanding kapasitas logis 32.768 word, penggunaan aktif adalah **55,0873%**. Delapan bank masing-masing mempunyai 2.297 slot terjadwal; total **18.376 slot**, termasuk 325 slot nol untuk lima lane output yang tidak berguna: `5×(64 weights + 1 bias) = 325`.

Kapasitas bank dibulatkan menjadi 4.096 word untuk struktur memory/addressing. Padding bukan tambahan parameter yang dipelajari. Memori yang lebih teratur memberi akses delapan lane tanpa delapan port baca ke satu RAM tunggal.

Fitter juga mencatat **655.360 implementation bits = 64×10.240**, berbeda dari 524.288 configured data bits. Rasio configured/implementation adalah **80%**. Ini menjelaskan granularitas blok fisik, bukan hilangnya data. Data bits dan implementation bits adalah dua pandangan atas memori yang sama; jangan dijumlahkan. [Memory GUI](../evidence/quartus_gui/06_memory_dsp_capacity.jpg).

## 12. Hidden activation dibank agar penulisan paralel jelas

Hidden activation membutuhkan `(128+64)×16 = 3.072 bit` secara logis. Pada tiap lane terdapat h1 16×16 dan h2 8×16, sehingga lane menulis storage miliknya sendiri. Input observations membutuhkan **74×16 = 1.184 bit**; tiga action **48 bit**; delapan accumulator **320 bit**. Angka ini mendeskripsikan storage logis pada source dan tidak boleh langsung dijumlahkan untuk menebak total register fitted karena optimisasi/packing juga berlaku.

Banking menghindari desain array bersama yang seolah memerlukan delapan port tulis pada satu struktur. Riwayat percobaan elaborasi yang dihentikan disimpan di experiment README; build accepted memakai scope lane literal dan storage bank yang eksplisit. Keunggulannya adalah struktur RTL yang dapat disintesis dan diuji pada tool yang benar-benar dipakai, bukan hanya diagram yang tampak paralel.

## 13. Fixed-point membuat operasi numerik dapat diaudit

Input, weights dan bias memakai kode signed 16-bit dengan skala **1/256**. Resolusi satu kode adalah **0,00390625**. Produk dua nilai berskala ini mempunyai skala **1/65.536**; karena itu bias disejajarkan dengan **geser kiri delapan bit** sebelum ditambahkan ke accumulator.

```text
accumulator = sign_extend(bias) << 8
accumulator += sign_extend(input * weights)
scaled = accumulator[39:8]       // floor signed divide by 256
hidden = clamp(ReLU(scaled), 0, 32767)
action = clamp(scaled, -256, 256)
```

Tidak ada pembagi umum untuk rescale ini: pemilihan bit menjadi bagian datapath. Hidden maksimal 32.767 kode atau **127,99609375** pada skala Q8.8; output dibatasi **[-1,+1]** pada skala riil. Hardware menerapkan batas yang eksplisit, tidak membiarkan interpretasi overflow bergantung pada software host.

Accumulator **40-bit** memberi ruang untuk partial sum sebelum aktivasi. Sebagai bound kasar struktural, 128 produk signed16×16 masing-masing maksimal magnitudo 2^30 memerlukan akomodasi hingga sekitar 2^37 sebelum bias; signed40 mencakupnya. Bound ini bukan alasan otomatis untuk mempersempitnya: domain, bias dan seluruh partial sum harus dibuktikan pada kandidat baru. [Aktivasi dan accumulator source](../experiments/parallel8/igor_src_policy_core.v).

## 14. Ketepatan diuji sampai hidden layer

Suite core tidak hanya melihat tiga output akhir. **236 vektor jaringan**, **8.364 activation cases**, dan **54.399 assertions** memeriksa hasil intermediate, kontrol dan kesesuaian terhadap oracle integer. Dua hidden layer mempunyai **192 nilai** per inferensi; output **3 nilai**. Tidak ada mismatch integer yang teramati pada suite yang dicatat.

Kesamaan terhadap oracle integer berbeda dari error terhadap floating reference. Karakterisasi baseline model yang sama melaporkan **153 vektor valid / 459 output**, maximum absolute error **0,0145717638971**, MAE **0,00362498421469**, RMSE **0,00426786892476**. Maksimum itu sekitar **3,73037 LSB output**; bukan “0 bit error terhadap FP32”. Parallel8 mempertahankan aritmetika integer dan diuji ekuivalensinya. [Metrics baseline](../evidence/current_metrics/metrics.json), [audit suite produksi](../evidence/uart_rtl_audit/20261018T071219039780Z/REPORT.md).

## 15. Mengapa pin sedikit meskipun input neural berjumlah 74

**Jumlah fitur bukan jumlah pin.** Host mengirim 74 word melalui UART secara serial, lalu FPGA menampungnya sebelum menghitung. Tiga action juga diserialisasi menjadi enam byte payload. Karena data tidak dibuat menjadi bus eksternal 74×16 = 1.184 jalur, runtime link hanya memerlukan **RX dan TX**, ditambah common ground konektor.

Perhitungan 13 port fitted sangat jelas: **1 clock + 2 KEY + 1 RX + 1 TX + 8 LED = 13**. Delapan LED memberi observability lokal; dua KEY memberi reset dan E-stop. Pin daya, ground dan pin konfigurasi dedicated tidak dihitung sebagai port logika top yang sama. `13/314` juga bukan persentase jalur yang dapat diakses pada satu GPIO header. [Pin Planner GUI](../evidence/quartus_gui/16_pin_planner.jpg).

Serialisasi memberi interface sederhana dan mudah dihubungkan ke Jetson/adapter 3,3 V. Komprominya adalah waktu transfer, sehingga sedikit pin tidak berarti semua data bergerak serentak. ASIC pad ring juga memiliki kebutuhan power/test/clock sendiri dan tidak dapat ditebak dari 13 pin top FPGA.

## 16. UART merupakan protokol transaksi, bukan aliran byte tanpa konteks

Request **153 byte** memuat **148 byte observasi**, header/type/length dan CRC. Reply **11 byte** memuat **6 byte action**. Payload efficiency berturut-turut **96,7320%** dan **54,5455%**. Overhead reply secara proporsional besar karena hasilnya memang sangat kecil.

Pada 8N1, 164 byte request+reply membutuhkan **1.640 bit serial**. Divider 54 pada 50 MHz memberi satu bit **1,08 µs**, sehingga serial ideal **1,7712 ms**. Ditambah core **0,13832 ms**, komponen minimum itu **1,90952 ms** sebelum parsing/load/host/gap. Nominal 921600 menghasilkan baud aktual sekitar **925.925,93**, deviasi **+0,4694%**. Ini konsisten dengan pengujian toleransi bit-time dan koneksi fisik yang dicatat, bukan izin memakai sembarang baud.

Angka ini menjelaskan mengapa RTT fisik beberapa milidetik tidak bertentangan dengan core 138,32 µs. Desain komputasi dan interface diukur dengan batas waktu yang berbeda.

## 17. “UART overhead” juga membeli validasi dan pengendalian

Core murni: **2.402,7 ALM, 2.324 ALUT, 4.747 register**. Core+policy UART: **3.300,7 ALM, 3.359 ALUT, 6.272 register**. Selisih **898 ALM, 1.035 ALUT, 1.525 register**, tanpa tambahan M10K/DSP. Receiver+transmitter leaf hanya **59,8 ALM**.

Sebagian besar biaya interface berada pada buffering observasi, parser, CRC, range check, scheduling, timeout dan status. Ini menjelaskan keputusan desain yang penting: biaya kontrol tidak disamarkan sebagai komputasi neural. Pengguna mendapatkan paket transaksi yang dapat ditolak dan dipulihkan, bukan sekadar multiplier yang cepat. Angka hierarchy fractional mengandung estimasi packing; sumber dan catatan inklusif terlihat langsung di [GUI hierarchy](../evidence/quartus_gui/04_core_uart_resources.jpg).

## 18. Input lengkap sebelum inferensi

Core mempunyai bitmap **74 bit** untuk mencatat observasi yang telah dimuat. Start tidak boleh diterima hanya karena beberapa nilai kebetulan sudah ada pada register dari transaksi sebelumnya. Range setiap field diperiksa oleh policy: fitur LiDAR 64 field dan 10 field lain mengikuti domain normalisasi yang ditetapkan source.

Dengan gate transaksi lengkap, parser dan core tidak memperlakukan setengah frame sebagai sampel neural yang sah. Edge cases mencakup indeks invalid, input belum lengkap, load/start ambigu dan operasi saat busy. Ini memperkuat integritas alur data; istilahnya **input validation**, bukan autentikasi kriptografi.

## 19. Keamanan operasional dibuat terlihat

KEY1 mengassert stop dan melatch sampai KEY0 reset. Top juga mempunyai path raw KEY untuk inhibit dan path tersinkronisasi; ia tidak hanya bergantung pada state software. Default parameter UART memberi RX inter-byte timeout **1.000.000 siklus = 20 ms**, result lease **20 ms**, infer watchdog **100.000 siklus = 2 ms** pada 50 MHz.

LED mapping: **LED0 permit**, **LED1 reset released**, **LED2 response-valid pulse**, **LED3 stop active**, **LED7:4 error code**. Status ini membantu diagnosis tanpa perlu alat debug internal. Frame accepted/rejected dan error history memberi jejak transaksi di interface debug yang diimplementasikan. [Top RTL](../experiments/parallel8/igor_src_policy_de10_nano.v), [policy RTL](../rtl/igor_src_policy/igor_src_policy_uart.v).

CRC8 mendeteksi kerusakan frame sesuai polinomialnya; ia bukan identitas pengirim dan bukan perlindungan terhadap pemalsuan oleh adversary. Keunggulan security yang sah adalah validation, fail-closed behavior pada kontrak terkait, status fault dan pemisahan jalur safety. Sertifikasi industri atau cryptographic root-of-trust tidak diklaim dari mekanisme tersebut.

## 20. Uji fault tidak hanya dilakukan sebelum dan sesudah transaksi

Suite UART mencatat **184 transaksi / 268 assertions**. Wrapper board mempunyai **18 checkpoints**. Audit tambahan menguji independent host nominal 921600 dan real-clock stress **50/50 valid frames**, tepat **550 reply bytes**, **150 golden actions**, dengan nominal dan variasi bit duration **±1%**.

Pengujian mencakup reset/startup UART idle, start/stop bit, header/CRC, framing error, parser recovery, E-stop saat parsing/inferensi/transmit, watchdog dan stale output. Ada pemeriksaan tidak muncul byte tambahan setelah transaksi dan silence lebih dari **21 ms** sesudah hasil terakhir. Ini lebih kuat daripada hanya mengirim satu input normal dan melihat LED menyala. [Audit dan log suite](../evidence/uart_rtl_audit/20261018T071219039780Z/REPORT.md).

## 21. Coverage diukur dengan denominator eksplisit

Suite core mencatat native line **68/68 = 100%**, branch **96/96 = 100%**, toggle **870/908 = 95,81%**. Model functional FSM mencatat state **8/8** dan normal arc **10/10**. Coverage tidak disamakan dengan test pass rate atau jumlah checkpoint inventory. [Coverage results](../evidence/rtl_coverage/COVERAGE_RESULTS.md).

Keunggulan prosesnya adalah dapat menjawab *bagian mana yang pernah dieksekusi*. Seratus persen pada metric tertentu bukan bukti seluruh kombinasi input dan seluruh mekanisme fault fisik telah terbukti; klaimnya tetap sesuai denominator masing-masing.

## 22. Memisahkan AI residual dari perintah motor adalah keputusan arsitektur

FPGA mengembalikan **tiga residual**, sementara Jetson melakukan preprocessing sensor, blending/filter/CBF, kinematics Mecanum dan pengiriman **empat wheel RPS** ke STM32. Hal ini mempertahankan batas antara policy AI dan keputusan actuator di host.

Karena residual nol tidak otomatis berarti motor nol, host mempunyai tanggung jawab final STOP atas keseluruhan command. Menyebutnya secara eksplisit mencegah integrator salah menghubungkan sinyal `permit` inferensi sebagai sertifikasi motor aman. Jalur FPGA yang diprogram tidak langsung menjalankan motor ketika SOF dimuat. [Operating guide aktual](../../final_docs.md), [direct UART runbook](../../docs/direct_uart_runbook.md).

## 23. Resource kecil menyisakan kapasitas pengembangan yang terukur

Setelah top Parallel8 terpasang, sisa kapasitas aritmetika adalah **38.607 ALM**, **489 M10K** dan **104 DSP**. Persentase pemakaian kelas resource: **7,8812% ALM**, **11,5732% M10K**, **7,1429% DSP**. Ini mendukung ruang eksplorasi untuk interface, observability atau kandidat arsitektur berikutnya pada perangkat yang sama.

Ruang kapasitas bukan jaminan semua tambahan akan place/route atau memenuhi timing. Resource class tidak dapat dijumlahkan menjadi satu persen luas silicon. ALM, ALUT, register, M10K dan DSP mempunyai granularitas/packing yang berbeda; bukti 8% pada GUI adalah **logic utilization**, bukan “8% luas die” atau “92% silicon kosong”.

## 24. Timing margin yang terlihat, bukan frekuensi rekaan

Quartus multicorner summary menunjukkan setup terburuk **+5,647 ns**, hold **+0,119 ns**, recovery **+14,279 ns**, removal **+0,253 ns**, minimum pulse width **+8,462 ns**, dan design-wide TNS **0** pada check yang dilaporkan. [Timing GUI](../evidence/quartus_gui/09_multicorner_timing.jpg).

Fmax slow 100°C **69,67 MHz** dan slow −40°C **72,74 MHz** adalah analisis pada clock domain dan path yang dicakup report. Itu mendukung keputusan menggunakan 50 MHz dengan margin. Constraint asynchronous reset/UART dan output LED/UART juga harus tetap dibaca; screenshot positif tidak mengubah asynchronous signal menjadi source-synchronous interface. Mengganti clock memerlukan verifikasi baru termasuk UART divider dan timeout.

## 25. Power: komputasi dinamis dan leakage dipisahkan

| Profil power Parallel8 | Dynamic | Static | I/O | Total |
|---|---:|---:|---:|---:|
| Typical | **50,36 mW** | **413,27 mW** | **12,55 mW** | **476,18 mW** |
| Maximum, Tj100°C | **50,36 mW** | **865,80 mW** | **21,40 mW** | **937,55 mW** |

Pada profil Typical, dynamic hanya sekitar **10,58% total**, sedangkan static sekitar **86,79%**. Ini menjelaskan mengapa mengurangi switching datapath tidak menurunkan seluruh daya FPGA dengan proporsi yang sama. Angka ini **estimasi vectorless confidence Low**, HPS Off; bukan daya board, motor, ASIC atau hasil ukur rail. Tidak digunakan untuk menghitung energy-per-inference terukur karena workload/activity duty belum dikalibrasi.

Baseline Typical dynamic **38,51 mW** menjadi **50,36 mW**, kenaikan **11,85 mW** pada model estimasi yang tersedia. Kecepatan core naik 7,8583×, sementara total Typical naik **11,97 mW = 2,5786%**. Ini hubungan trade-off dari report, bukan benchmark energy efficiency dengan aktivitas nyata yang sama. Sumber: [Typical asli dalam Quartus](../evidence/quartus_gui/17_typical_power_original_report.jpg), [Maximum panel](../evidence/quartus_gui/12_power_summary_maximum.jpg), [confidence GUI](../evidence/quartus_gui/15_power_confidence.jpg).

## 26. Bukti fisik memberi lapisan validasi yang berbeda

Programming JTAG berhasil dengan **HPS posisi 1 bypass, FPGA posisi 2**, menggunakan SOF Parallel8. Sesi fisik direct Jetson GPIO UART mencatat **98/98 inference requests** sesuai expected fixed-point, termasuk **16 fixtures**. Mean RTT **4,594 ms**, maksimum **5,920 ms** adalah hasil link end-to-end pada sesi tersebut.

Bukti compile, simulation dan physical transaction saling melengkapi: compile membuktikan implementability pada tool/device, oracle memeriksa perhitungan/kontrol, programming membuktikan konfigurasi device, UART fisik memeriksa transaksi pada board. Masing-masing tidak menggantikan yang lain. Navigasi robot bergerak lengkap dan power rail measurement mempunyai acceptance tersendiri. [Sesi fisik](../../final_docs.md), [programming receipt](../evidence/current_programming/20261019T0245566102607Z/programming_result.json).

## 27. Mengapa proses desain dapat direproduksi

Bank parameter memiliki provenance terhadap model sumber. QSF memilih source yang benar-benar dikompilasi. Acceptance menyimpan SHA source, reports, hasil simulasi dan SOF. Script `check_parallel8()` memeriksa binding ini; image handoff harus sama dengan compiled SOF, bukan hanya mempunyai nama file yang mirip.

Native GUI screenshot menyertakan judul project Parallel8 dan panel report asli. File wave, CSV checkpoints, oracle/log dan report tekstual tetap tersedia, sehingga orang lain tidak perlu menerima klaim dari gambar yang ditulis ulang. **18 screenshot asli Quartus** meliputi hierarchy, RAM, DSP, timing, power dan Pin Planner. [Indeks bukti](../evidence/quartus_gui/README.md), [manifest capture](../evidence/quartus_gui/manifest.json).

## 28. ASIC memberi arah pengembangan, dengan batas fungsi yang jelas

Repository juga menyimpan physical report IHP CMOS5L `tt_um_igorchip`, sebuah programmable protocol engine. Angka fisiknya: standard cells **0,0698308 mm²**, satu macro SRAM 512 byte **0,0281271 mm²**, jumlah footprint **0,0979579 mm²**, allocated block **0,916214 mm²**. Ini bukti proses implementasi ASIC untuk top tersebut, bukan luas neural Parallel8 yang sudah diproduksi.

Nilai “tanpa PLL”, “8% ALM” dan “0,0979579 mm²” tidak boleh dilebur seolah berasal dari satu chip neural ASIC yang sama. ASIC memakai standard cells/macro, tidak membawa LUT/M10K/DSP FPGA secara literal. Langkah berikutnya adalah mapping neural top dan memory ke library IHP yang sama, lalu membandingkan area/timing/power pada fungsi yang ekuivalen. [Area analysis](AREA_CORE_UART_ASIC.md), [status fisik ASIC](ASIC_SIGNOFF_STATUS.md).

## 29. Kandidat peningkatan yang paling masuk akal berdasarkan data

1. **Weights/bias 9-bit lossless untuk model ini.** Range yang diaudit **−123..129** muat signed9, tetapi 129 tidak muat signed8. Kapasitas bank logis dapat berubah 524.288→294.912 bit, turun **43,75%**, sebelum granularitas M10K diperhitungkan. Belum ada klaim M10K aktual turun tanpa build baru.
2. **Accumulator sizing berbasis bound.** Buktikan seluruh partial sum per neuron; jangan mempersempit 40-bit hanya karena beberapa vector terlihat kecil.
3. **Hidden memory mapping.** Storage logis hidden 3.072 bit dapat dieksplorasi sebagai memory block dengan banking dan read latency yang benar. Trade-off ALM/register/M10K dan jadwal harus diukur.
4. **Transport.** Jika target aplikasi adalah RTT, waktu serial ideal 1,7712 ms menunjukkan titik optimasi yang berbeda dari core. Pilih interface lebih cepat/buffering sesuai kontrak, lalu uji kembali integritas dan fault recovery.
5. **DSP packing/MAC inference.** Periksa netlist dan mode perangkat sebelum mengklaim penghematan. Semua kandidat memerlukan oracle integer, regresi, fit dan STA yang baru.

Ini ide engineering berbasis struktur aktual, bukan perubahan yang diam-diam sudah dimasukkan ke SOF. [Techniques lengkap](techniques.md).

## 30. Narasi publikasi yang dapat langsung digunakan

> IGOR Parallel8 menghadirkan akselerator neural dengan delapan lane komputasi yang memproses policy 74→128→64→3 dalam 138,32 mikrodetik pada clock 50 MHz. Banking parameter dan reuse operand mempertahankan model 18.051 parameter dengan 64 M10K, sementara delapan DSP menjalankan perkalian signed fixed-point. Implementasi lengkap hanya memakai 3.303 ALM—sekitar 8% kapasitas logika DE10-Nano—dan menyediakan interface UART ber-CRC, validasi transaksi, timeout serta E-stop yang dapat diamati melalui status hardware. Keputusan desain didukung oracle integer, laporan fitting dan timing, screenshot GUI Quartus asli, serta 98 transaksi inferensi UART fisik yang berhasil pada sesi pengujian terdokumentasi.

Untuk presentasi, jelaskan urutannya: **target → baseline → banking dan reuse → delapan lane → integer correctness → Fitter/STA → protokol/safety → bukti fisik**. Dengan alur ini, angka tidak berdiri sendiri: audiens melihat kebutuhan, pilihan, biaya dan hasilnya.

## Pustaka dan sumber primer

Sumber project lebih berwenang untuk angka IGOR daripada deskripsi umum arsitektur perangkat. Pustaka vendor menjelaskan kemampuan dan metode, bukan membuktikan implementasi IGOR secara otomatis.

- **[P1] Altera.** *Design Compilation User Guide, §3.5: Inferring Multiplier, DSP, and Memory Functions from HDL Code.* Dokumentasi resmi tentang pengenalan operasi HDL dan pemetaan ke resource perangkat. [Dokumen](https://docs.altera.com/r/docs/683283/18.1/design-compilation-user-guide-quartus-prime-standard-edition/inferring-multiplier-dsp-and-memory-functions-from-hdl-code?contentId=wmnswszCTQKsOuMH4H_cqw). Diakses melalui indeks dokumentasi 19 Oktober 2026.
- **[P2] Altera.** *Cyclone V Device Overview: Variable-Precision DSP Block.* Mode presisi dan konfigurasi DSP Cyclone V. [Dokumen](https://docs.altera.com/r/docs/683694/current/cyclone-v-device-overview/variable-precision-dsp-block?contentId=DfL21bJ5g7LHAndq9mObpQ). Diakses melalui indeks dokumentasi 19 Oktober 2026.
- **[P3] Terasic.** *DE10-Nano Kit*, spesifikasi board dan sumber clock. [Halaman resmi](https://www.terasic.com.tw/cgi-bin/page/archive.pl?CategoryNo=199&Language=Taiwan&No=1047&PartNo=2). Keberadaan tiga sumber 50 MHz pada spesifikasi board tidak berarti seluruhnya dipakai oleh IGOR; top dan SDC hanya memakai FPGA_CLK1_50.
- **[L1] Quartus Prime 25.1.** [Fitter summary](../experiments/parallel8/output_files/igor_src_policy.fit.summary), [Fitter hierarchy](../experiments/parallel8/output_files/igor_src_policy.fit.rpt:1411), [timing summary](../experiments/parallel8/output_files/igor_src_policy.sta.summary).
- **[L2] IGOR verification.** [Acceptance](../experiments/parallel8/artifacts/acceptance.json), [cycle checkpoints](../experiments/parallel8/core_checkpoints.csv), [UART audit](../evidence/uart_rtl_audit/20261018T071219039780Z/REPORT.md), [coverage](../evidence/rtl_coverage/COVERAGE_RESULTS.md).
- **[L3] Native GUI evidence.** [18 screenshot asli](../evidence/quartus_gui/README.md), capture metadata dan hashes. Report berasal dari build 17 Oktober, diinspeksi GUI 19 Oktober 2026.
- **[L4] Physical integration.** [Final operating guide](../../final_docs.md), [direct UART runbook](../../docs/direct_uart_runbook.md), [physical logs](../../docs/ethernet_validation/).
- **[L5] Source RTL.** [Parallel8 core](../experiments/parallel8/igor_src_policy_core.v), [top](../experiments/parallel8/igor_src_policy_de10_nano.v), [UART policy](../rtl/igor_src_policy/igor_src_policy_uart.v), [techniques](techniques.md).

Semua hitungan turunan diberi definisi di atas. Script ledger `fpga/scripts/collect_design_funfacts.py` membaca angka sumber dan menghitung kembali rasio; script tersebut tidak membuat angka Fitter/STA/power dan tidak menjalankan hardware.
