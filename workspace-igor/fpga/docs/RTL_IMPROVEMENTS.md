# Perbaikan RTL: diterapkan hanya dengan bukti validasi

Tanggal 17 Oktober 2026. Model utama tetap PPO 74→128→64→3 dari `src`; perubahan hanya dalam `fpga`. Tujuan pekerjaan ini adalah meningkatkan kualitas bukti dan ketahanan pencatatan tanpa mengubah kontrak numerik, bobot, protokol atau fungsi host menjadi klaim hardware baru.

## 1. Perbaikan yang sudah diterapkan dan lulus

### Counter accepted/rejected policy tidak boleh wrap menjadi nol

Sebelumnya, tiga jalur increment pada [igor_src_policy_uart.v](../rtl/igor_src_policy/igor_src_policy_uart.v) memakai penjumlahan 32-bit biasa: counter accepted, task reject, dan kejadian E-stop. Ketika `0xffffffff` ditambah satu, counter menjadi nol. Pada observasi audit jangka panjang, nol itu dapat disalahartikan sebagai belum ada transaksi/penolakan sejak reset.

Sekarang ketiganya **saturating**: increment hanya bila nilainya belum `32'hffffffff`. Kejadian fault tetap memperbarui error/history dan tetap membatalkan permit/respons; counter penuh tidak menghentikan evaluasi keselamatan. Reset hardware tetap menghapus counter. Tidak ada opcode, panjang frame, CRC, bobot, range output atau latency inferensi yang diubah.

Ini memperbaiki port debug RTL. Board policy standar tidak mengekspos query counter melalui UART, dan Fitter dapat memangkas counter yang tidak dipakai pada top board. Karena itu perbaikan ini tidak diklaim menambah telemetri serial atau log fisik yang belum diimplementasikan.

### Validasi batas dengan transaksi nyata pada simulator

Testbench [tb_src_policy_uart.sv](../verification/src_policy/tb_src_policy_uart.sv) menambahkan test ID **1400–1406**:

| ID | Stimulus dan harapan |
|---|---|
| 1400 | Seed accepted=`fffffffe` pada negedge saat idle, kirim frame UART sah sampai response selesai → accepted=`ffffffff`; respons cocok oracle. |
| 1401 | Kirim frame valid kedua tanpa reset → accepted tetap `ffffffff`; residual tetap benar, tidak wrap. |
| 1402 | Seed rejected=`fffffffe`, kirim frame CRC salah → rejected=`ffffffff`, permit dan guarded residual nol, error 6. |
| 1403 | Kirim CRC salah kedua → rejected tetap `ffffffff`, fault tetap diproses. |
| 1404 | E-stop saat rejected sudah penuh → counter tetap maksimum, output nol dan error/history E-stop tercatat. Ini memeriksa jalur increment E-stop yang terpisah dari task reject. |
| 1405 | Reset setelah kondisi penuh → accepted/rejected=0, permit lama tidak hidup kembali. |
| 1406 | Transaksi valid baru → accepted=1, rejected=0, residual sesuai oracle; recovery tidak rusak. |

Seed counter adalah **injeksi state testbench** agar batas 2³² dapat dicapai tanpa miliaran frame. Sesudah seed, penambahan benar-benar melewati parser UART, frame CRC, inferensi/response dan raw E-stop; hasil bukan menetapkan counter ke nilai expected sesudah transaksi.

Seluruh test lama tetap dijalankan; kasus tambahan ditempatkan setelah checkpoint lama sehingga waktu E-stop/map/CRC yang sudah didokumentasikan tidak bergeser. Bukti: [uart.log](../verification/src_policy/artifacts/uart.log), [CSV](../verification/src_policy/artifacts/uart_checkpoints.csv), screenshot [accepted max](../evidence/visual_review/13_counter_accepted_max.png), [rejected max](../evidence/visual_review/14_counter_rejected_max.png), [recovery](../evidence/visual_review/15_counter_reset_recovery.png).

| Pemeriksaan | Sebelum | Sesudah | Kesimpulan |
|---|---:|---:|---|
| UART directed transactions / assertions | 177 / 237 | **184 / 268** | Tujuh kasus batas baru dan pemeriksaan recovery lulus. |
| Network vectors / activation cases | 236 / 8.364 | **236 / 8.364** | Kontrak integer tetap cocok. |
| Core assertions | 54.399 | **54.399** | Tidak mengurangi regresi perhitungan. |
| Latency core @50 MHz | 54.348 siklus | **54.348 siklus** | Tidak mengklaim speed-up. |
| Actual board-wrapper simulation | 18 checkpoint | **18 checkpoint** | Default divider 54 / 50 MHz tetap lulus. |
| Quartus source policy | PASS | **PASS, 0 error / 3 warning** | Source sebelum/sesudah build cocok; SOF baru dihasilkan. |
| Resource ALM / M10K / DSP | 3.249 / 64 / 1 | **3.249 / 64 / 1** | Tidak ada perubahan pemakaian pada top board ini; port debug unused dapat dipangkas. |
| Worst setup / hold | +6,019 / +0,116 ns | **+6,019 / +0,116 ns** | Tidak ada degradasi timing pada laporan build ini. |

Baseline berasal dari commit `303fd81`, disimpan sebagai [receipt baseline](../evidence/visual_review/baseline_source_policy.json) dan [hasil baseline](../evidence/visual_review/baseline_policy_results.json). Sesudah perubahan: [receipt current](../evidence/current_builds/source_policy.json), [hasil current](../verification/src_policy/artifacts/results.json). Angka identik pada resource/timing tidak membuktikan equivalence semua rangkaian; equivalence numerik yang diklaim adalah regresi oracle dengan scope yang ditetapkan.

SOF policy baru SHA256: `fb9fcd28136b647492d2284fef82beca34b97f8300ce0579c25e0745fa88cf4a`. SOF lama tidak digunakan sebagai bukti build source baru.

### Save file GTKWave menampilkan bus yang benar

Pada GTKWave Windows v3.3.100 terpasang, nama bus tanpa rentang bit pada save file dapat hilang dari daftar trace, meskipun loader tidak gagal. [core.gtkw](../verification/src_policy/core.gtkw) dan [uart.gtkw](../verification/src_policy/uart.gtkw) sekarang memakai rentang persis header VCD. Layout juga disesuaikan ke 1400×720 dan kolom sinyal 400 pixel agar nilai marker tidak terpotong.

Script capture memeriksa keberadaan setiap fasilitas VCD serta jumlah trace GTKWave sebelum Grab To File; screenshot dengan trace hilang ditolak. Ia juga membaca VCD untuk memastikan nilai marker known (bukan X/Z) dan cocok dengan CSV. Offset sebelum pergantian stimulus/dump-off dicatat eksplisit agar delta-cycle testbench tidak disalahartikan sebagai fault desain. Ini perbaikan reproduksibilitas inspeksi, bukan perubahan RTL datapath. Gambar asli ada pada [galeri](../evidence/visual_review/index.html).

## 2. Cara memperbaiki desain berikutnya — belum dimasukkan ke rilis

Usulan berikut memerlukan implementasi dan acceptance tersendiri. Tidak ada status PASS atau angka performa baru yang diberikan sebelum pengujian.

| Prioritas | Perbaikan yang disarankan | Mengapa perlu | Bukti wajib sebelum diterima |
|---|---|---|---|
| 1 | Jalur keputusan policy → shield holonomik → gate → kinematika/serializer tunggal | Gap terbesar: policy residual, checker v/omega, host blending dan motor masih terpisah. Nama `safety_permit` policy tidak cukup untuk menyatakan izin motor. | Kontrak `vx/vy/omega` dan empat roda, permit/lease/fault, replay integer end-to-end, semua injeksi fault mencapai payload motor nol, interlock fisik, A4/A5/stop-time board. |
| 2 | Protokol versi baru dengan transaction ID, sequence/epoch, timestamp/lease dan status query atomic | Respons lama yang sudah diterima host tidak dapat ditarik kembali; current bridge melatch fault dan memerlukan reset/restart. Query status policy belum ada. | Respons salah ID, replay, rollover sequence, reset di tengah frame, busy, host restart, timeout exact-boundary, backward compatibility dan host test. Jangan mengubah framing current diam-diam. |
| 3 | Bundel status/fault/event/last_fault/output dalam satu snapshot coherent | Query planner saat ini beberapa transaksi dan dapat menangkap keadaan berbeda. | Latch snapshot pada satu edge, ID/version snapshot; fault yang berubah di antara query tidak menghasilkan status campuran; no-motor-effect query; UART oracle. |
| 4 | Sinkronisasi/constraint CDC yang dinyatakan dan dianalisis, serta pemisahan reset TX/cancellation yang terdefinisi | STA build menyebut chain synchronizer, tetapi MTBF tidak dihitung karena synchronizer belum dispesifikasikan untuk analisis tersebut. Jalur E-stop harus tetap assert cepat dan release terkontrol. | Laporan CDC/metastability yang benar, review recovery/removal dan asynchronous path, reset assertion/deassertion di berbagai fase clock, E-stop saat RX/RUN/TX dan board validation. Tidak asal menambahkan false path yang menyembunyikan jalur. |
| 5 | Pipelining ROM/MAC atau penambahan lane MAC terukur | Core sekarang menunggu ROM dan melakukan serial MAC; optimasi mungkin mengurangi kernel latency tetapi menambah resource/control complexity. | Semua hidden/output bit-exact, signed/floor/saturation tetap, latency assertion baru, default 50 MHz STA semua corner, ALM/DSP/M10K dan RTT sebelum/sesudah. UART/host bisa menjadi bottleneck sehingga kernel lebih cepat belum berarti sistem lebih cepat. |
| 6 | Map/goal/footprint yang bisa dikonfigurasi sesuai robot, inflasi dan braking envelope terukur | Planner legacy mempunyai pose/goal/scoring tetap dan point rollout; keamanan fisik tergantung peta, robot dan dinamika. | Uji robot footprint, sudut/celah/out-of-map, stale sensors, envelope speed-vs-distance, swept volume/braking, golden model dan scene baru yang dibekukan. |
| 7 | Assertion formal pada invariant gate/protocol/control | Simulasi sekarang luas tetapi tidak mencakup semua urutan temporal. | Properties yang benar-benar dibuktikan, assumptions eksplisit, bound/coverage/vacuity dan counterexample; liveness dipisah dari safety. Tidak memberi label formal hanya karena ada assertion simulasi. |
| 8 | Autentikasi map/command dan secure key path | CRC/sequence/freshness belum autentikasi terhadap penyerang. | Threat model, key/reset/nonce policy, replay/tamper tests, resource/timing, host interoperability dan evaluasi independen; sertifikasi tidak otomatis mengikuti implementasi HMAC. |

Kriteria penerimaan setiap perubahan: source/bobot jelas → kontrol positif → edge/fault/recovery → oracle independen → wrapper/host yang terdampak → kompilasi dan timing/pin → SOF/hash baru → dokumentasi. Perubahan yang gagal tidak disebut rilis tervalidasi.

## 3. Batas hasil saat ini

Perbaikan audit counter dan save file telah diuji. Tidak ada perubahan pada topology/weights atau klaim bahwa AI, safety map dan motor sudah menyatu. Tidak ada JTAG programming, uji roda, daya atau stop-time fisik baru. Screenshot dan report membantu audit; bukti utama tetap source, oracle, raw log/checkpoint dan receipt yang hash-nya cocok.
