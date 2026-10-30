# IGOR Chip — keunggulan untuk pengendalian protokol industri

**IGOR Chip adalah prototipe yang sangat menarik untuk pengembangan
pengendali protokol industri: hemat energi, dapat diprogram, dan memiliki
proteksi operasi I/O yang diterapkan langsung di RTL.**

Desain ASIC **`tt_um_igorchip`** pada PDK **`ihp-sg13cmos5l`** menggabungkan
empat context eksekusi, register state per context, host SPI, GPIO yang
dikelola berdasarkan kepemilikan, dan SRAM program **256×16 bit**.

## Angka yang menonjol

| Aspek | Hasil tercatat |
|---|---:|
| Total power Typical, estimasi post-route | **2,037372 mW** |
| Dynamic power Typical | **1,9873419 mW** |
| Total power pada tiga profil analisis | **1,620704–2,662040 mW** |
| Die area | **0,916214 mm²** |
| Context eksekusi | **4** |
| SRAM program | **256×16 bit** |
| Pengujian gate-level yang dilampirkan | **PASS** |

[power.md](power.md) memuat rincian power dan sumber setiap angka.

## Keunggulan tambahan yang sudah ditelusuri

- **Multi-protocol dalam satu engine:** demo UART RX, UART TX, I²C dan SPI
  memakai **254 word / 508 byte** dalam SRAM program.
- **Empat context concurrent:** diuji bersama dan dibandingkan terhadap
  model referensi setiap clock eksekusi.
- **Penanganan bus yang eksplisit:** UART start/stop qualification, I²C
  ACK/NACK, open-drain dan clock stretching mempunyai pengujian tersendiri.
- **Program upload dengan readback:** driver host dapat memverifikasi
  data program sebelum eksekusi.
- **Bukti pengujian yang kuat untuk presentasi:** suite yang tersedia
  dijalankan ulang pada 17 Oktober 2026, **42 tes PASS**, source tetap sama.

[CHIP_ADVANTAGES.md](CHIP_ADVANTAGES.md) memetakan setiap poin ke RTL,
firmware, nama tes, dan [log hasil pengujian](evidence/chip_highlights/regression.log).

## Security operasional yang tertanam di hardware

Keunggulan desain terletak pada mekanisme pembatasan operasi dan kendali
akses I/O yang eksplisit. Fitur berikut mendukung integritas operasi
pengendali protokol industri:

| Mekanisme RTL | Perilaku hardware | Manfaat pada aplikasi industri |
|---|---|---|
| Kepemilikan pin per context | `pin_mask` membatasi pin yang diubah oleh setiap context | Pembagian tanggung jawab I/O yang jelas |
| Pemeriksaan konflik pin | Alokasi mask yang bertabrakan dengan context lain ditolak dan dicatat | Membantu mencegah perebutan kendali pin |
| Proteksi program saat core aktif | Jalur write SRAM dibuka ketika core nonaktif; akses yang ditolak mencatat error | Menjaga kontrol perubahan program selama eksekusi |
| Perubahan konfigurasi pin terkontrol | Mask kepemilikan diatur saat core nonaktif | Konfigurasi mempunyai fase pengaturan yang jelas |
| Kontrol output enable | Reset dan `ena` mengendalikan output enable; perintah halt host melepaskan drive pin milik context terkait | Kendali pelepasan output tersedia pada hardware |
| Diagnostik per context | Register `errors` dan status context dapat dibaca host | Integrasi pemantauan dan penelusuran kejadian lebih mudah |
| Sinkronisasi input | Host SPI dan GPIO mempunyai register sinkronisasi | Membantu antarmuka sinyal eksternal ke domain clock internal |
| Arbitrasi mutasi host | Engine menahan langkah eksekusi saat transaksi mutasi host diproses | Urutan perubahan state dibuat eksplisit |

Sumber implementasi: [igorchip_top.v](../src/igorchip_top.v),
[program_host.v](../src/program_host.v), dan
[program_memory.v](../src/program_memory.v).

## Bukti yang dapat dipresentasikan

- **Functional gate-level PASS:** [results.xml](evidence/asic_import/gatelevel_test_results/raw/results.xml).
- **Waveform pengujian:** [tb.fst](evidence/asic_import/gatelevel_test_results/raw/tb.fst).
- **Power post-route:** [Typical report](evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/56-openroad-stapostpnr/nom_typ_1p20V_25C/power.rpt).
- **Data numerik lengkap:** [199 metrik final](evidence/asic_import/gds_diagnostics_1/final_metrics.csv), dengan sumber dan SHA256.

## Narasi singkat

> IGOR Chip menawarkan kombinasi yang kuat untuk prototipe pengendalian
> protokol industri: estimasi daya Typical sekitar **2,04 mW**, empat
> context eksekusi, serta mekanisme hardware untuk kepemilikan GPIO,
> pengendalian perubahan program, kontrol output enable, dan diagnostik
> error. Kekuatan desainnya adalah proteksi operasi yang dekat dengan
> jalur I/O, efisiensi energi, serta bukti implementasi dan pengujian
> gate-level **PASS** yang dapat ditelusuri.

---

<!-- BENNAYA_TEXTFIELD_20261017 -->

# Jawaban publikasi: inti FPGA IGOR dan seluruh text field

Tambahan **17 Oktober 2026**. Seluruh isi sebelum bagian ini dipertahankan. Bagian ini menjawab dokumen “IGOR: Kekuatan, Demo, dan To-do Menuju Top 3”, versi 15 Oktober 2026. Lampiran digunakan sebagai sumber pertanyaan; jawaban disusun dari implementasi dan bukti yang dapat dibuka. ID **K1–K7, D1–D7, A1–A14, B1–B6** mempertahankan nomor text field asal.

## Narasi utama yang siap dipresentasikan

**Kami menciptakan IGOR — Indonesian Gated Onboard Robotics — untuk membawa kecerdasan kendali ke hardware yang terukur.** Inti FPGA-nya mengolah **74 observasi** melalui jaringan PPO **74 → 128 → 64 → 3**, delapan jalur MAC dan bobot on-chip, menghasilkan tiga residual kendali dalam **138,32 µs**. Paket IGOR menyediakan motion checker, safety gate serta pencatatan fault pada jalur planner; protocol engine terprogram melengkapi visi antarmuka periferal industri.

Nilai produk kami adalah **komputasi edge, pembatasan operasi dekat keluaran, serta jejak bukti yang dapat ditelusuri**. Visi sistem terpadu menghubungkan kemampuan tersebut menuju kendali robot. Bukti teknis tetap diberi identitas blok: **core AI FPGA**, **planner/safety RTL**, dan **protocol engine ASIC**. Angka masing-masing blok merujuk hasil implementasi serta kondisi analisisnya sendiri.

## Parameter inti `fpga/` yang dapat dijelaskan

| Parameter | Nilai dan makna | Sumber |
|---|---|---|
| Clock / periode | **50 MHz / 20 ns** | [S01](#sumber-s01), [S02](#sumber-s02) |
| Siklus / latensi core | **6.916 clock / 138,32 µs / 0,13832 ms** | [S01](#sumber-s01), [S02](#sumber-s02) |
| Jadwal layer | Hidden 1 **3.616**, hidden 2 **3.104**, output **196 clock** | [S01](#sumber-s01), [S15](#sumber-s15) |
| Datapath | **8 lane MAC**, signed operand 16-bit, product 32-bit, accumulator 40-bit | [S01](#sumber-s01) |
| Model | **17.856 bobot + 195 bias = 18.051 word berguna** | [S01](#sumber-s01), [S02](#sumber-s02), [S22](#sumber-s22) |
| Memori neural | **8 bank × 4.096 × 16-bit = 64 KiB alokasi**, memakai M10K sebagai ROM bobot | [S01](#sumber-s01), [S03](#sumber-s03) |
| Isi model berguna | **36.102 byte**; padding bank dicatat terpisah | [S02](#sumber-s02), [S15](#sumber-s15) |
| Format numerik | **Q8.8**, langkah representasi **1/256**; residual dibatasi kode **−256…+256** | [S01](#sumber-s01), [S22](#sumber-s22) |
| Resource fitted | **3.303 ALM, 6.277 register, 64 M10K, 8 DSP** | [S02](#sumber-s02), [S03](#sumber-s03) |
| Worst setup / hold | **+5,647 ns / +0,119 ns** pada laporan timing FPGA | [S02](#sumber-s02), [S04](#sumber-s04) |
| MAC berguna per inferensi | **17.856** = 74×128 + 128×64 + 64×3 | [S01](#sumber-s01) |
| Throughput ekuivalen core | **7.229,61 inferensi/detik** = 50.000.000/6.916 | Turunan [S02](#sumber-s02) |
| Laju MAC berguna ekuivalen | **129,09 MMAC/s** = 17.856/138,32 µs | Turunan [S01](#sumber-s01)/[S02](#sumber-s02) |
| Verifikasi Parallel8 | **54.399 assertion core**, **268 assertion UART**, **18 checkpoint board wrapper**, PASS simulasi | [S02](#sumber-s02) |
| Safety planner | **111.210 vektor**, seluruh outcome fault **0–11**, **111 checkpoint** | [S05](#sumber-s05), [S06](#sumber-s06) |
| Host fail-closed | **29 tes**, 0 failure, 0 error; software fixture | [S09](#sumber-s09) |
| SRAM program ASIC | **256×16-bit / 512 byte**, satu port, byte-write mask, empat context | [S12](#sumber-s12), [S13](#sumber-s13), [S15](#sumber-s15) |
| Power FPGA Parallel8 | **50,36 mW dynamic / 476,18 mW total Typical**; estimasi Quartus vectorless, HPS Off, confidence Low | [S26](#sumber-s26) |
| Power protocol engine ASIC | **2,037372 mW total Typical**, estimasi post-route 1,20 V / 25°C | [S13](#sumber-s13) |

Throughput ekuivalen adalah perhitungan dari waktu core dengan asumsi tanpa overhead; sustained throughput komunikasi/robot dilaporkan dari pengukuran sistem. Satu MAC berarti satu perkalian-penjumlahan untuk satu bobot berguna. Q8.8 menjelaskan resolusi representasi; galat jaringan terhadap FP32 mempunyai karakterisasi tersendiri pada [S23](#sumber-s23). Tabel ini tidak menyatukan daya ASIC dan latency FPGA menjadi satu hasil chip gabungan.

## K1–K7: jawaban eksplisit untuk kekuatan IGOR

Kalimat berikut dapat dipakai dalam naskah publikasi dengan jenis bukti yang menyertainya. Katalog Sxx di akhir bagian menyediakan tautan langsung.

| Text field asal | Jawaban untuk dijelaskan | Jenis bukti | Sumber |
|---|---|---|---|
| <a id="textfield-k1"></a>**K1 — AI driver tangguh** | IGOR membawa kebijakan neural ke datapath yang dapat diulang: PPO 74→128→64→3, delapan lane MAC, dan pemeriksaan terhadap model integer dengan bobot yang sama. Ketangguhan navigasi per episode dilaporkan dari simulator, seed dan dataset studi yang dibekukan. | RTL/model tersedia; hasil episode mengikuti raw studi | [S01](#sumber-s01), [S02](#sumber-s02), [S22](#sumber-s22), [S23](#sumber-s23) |
| <a id="textfield-k2"></a>**K2 — AI mengemudi, chip memutuskan** | Prinsip produk: AI mengusulkan koreksi, aturan kendali menjaga pelepasan keluaran. Core neural menghasilkan residual; jalur planner memiliki checker dan gate. Studi B mengukur dampak penyatuan jalur pada gangguan yang ditentukan. | Arsitektur blok dan RTL; integrasi sistem mempunyai acceptance | [S01](#sumber-s01), [S07](#sumber-s07), [S11](#sumber-s11), [S25](#sumber-s25) |
| <a id="textfield-k3"></a>**K3 — fail-closed** | Pada jalur planner yang diuji, E-stop dan kondisi invalid menutup izin serta menolkan keluaran. Safety regression mencakup 111.210 vektor dan outcome 0–11; host fixture memeriksa penghentian pada kegagalan transport. | RTL dan host PASS | [S05](#sumber-s05), [S06](#sumber-s06), [S07](#sumber-s07), [S09](#sumber-s09) |
| <a id="textfield-k4"></a>**K4 — waktu terdefinisi, hasil dapat diulang** | Parallel8 mempunyai jadwal 6.916 clock pada 50 MHz, yaitu 138,32 µs. Fase bias, baca bobot, MAC dan aktivasi memiliki urutan eksplisit; kecocokan numerik merujuk model integer dan bobot yang sama. | Simulasi serta timing FPGA PASS | [S01](#sumber-s01), [S02](#sumber-s02), [S04](#sumber-s04), [S22](#sumber-s22) |
| <a id="textfield-k5"></a>**K5 — jejak audit** | Penolakan planner dapat dijelaskan lewat fault_code, counter kejadian 32-bit dan last_fault. CSV mengikat nama kasus, waktu simulasi dan nilai output sehingga jejak dapat ditelusuri sampai RTL/waveform. | Trace digital tersedia | [S06](#sumber-s06), [S08](#sumber-s08), [S10](#sumber-s10) |
| <a id="textfield-k6"></a>**K6 — implementasi konkret** | Paket fpga berisi Verilog, bobot, proyek Quartus, pin planning, laporan compile/timing, SOF dan waveform. Proyek DE10-Nano dapat dibuka; penerimaan gerak robot dilengkapi log serta video run fisik. | Build FPGA PASS; acceptance fisik A1–A11 | [S02](#sumber-s02), [S03](#sumber-s03), [S04](#sumber-s04), [S19](#sumber-s19), [S20](#sumber-s20), [S21](#sumber-s21) |
| <a id="textfield-k7"></a>**K7 — efisien dan jalur silicon lokal** | Core FPGA memakai 3.303 ALM, 8 DSP dan 64 M10K. Protocol engine ASIC menyediakan empat context, SRAM program 512 byte dan estimasi Typical 2,037372 mW. IP mencakup RTL, firmware, model serta bukti verifikasi. | Fitted FPGA dan estimasi ASIC | [S02](#sumber-s02), [S03](#sumber-s03), [S12](#sumber-s12), [S13](#sumber-s13), [S15](#sumber-s15) |

**Cara membaca angka text field lama:** 50 episode, 68% sukses/0% tabrakan, lima skenario ekstrem dan angka Studi A/B memerlukan raw episode/notebook terkait sebelum menjadi hasil publikasi yang dapat direproduksi. Arsip neural legacy mencatat **100 vektor / 400 output** dan **18.192 siklus** pada [S16](#sumber-s16); planner legacy mencatat **7.938 siklus = 158,76 µs** pada enam scene di [S17](#sumber-s17); gate legacy **13.078 kasus** ada di [S18](#sumber-s18). Angka tersebut tetap beridentitas legacy. Resource 4.964 ALM/10 DSP/131 M10K, power sekitar 0,51 W, 29.382 pemeriksaan serta 684 sel/1.010 konfigurasi dalam text field dipakai bersama laporan historis yang tepat; ledger publikasi di atas memakai bukti yang ditautkan. Klaim hasil fisik menggunakan rekaman run board/robot, bukan label hari pada dokumen rencana.

## D1–D7: jawaban eksplisit rencana demonstrasi

| Text field asal | Jawaban / cara menampilkan dengan jelas | Acceptance dan sumber |
|---|---|---|
| <a id="textfield-d1"></a>**D1 — lintasan robot** | Overlay output FPGA, permit dan fault pada video start–tujuan; rekam payload menuju aktuator. Sebut model serta peran host yang benar-benar dipakai. | Run fisik dengan log/video satu identitas; [S10](#sumber-s10), [S11](#sumber-s11), [S25](#sumber-s25) |
| <a id="textfield-d2"></a>**D2 — replay dan timer** | Replay observasi dengan bobot sama; tampilkan expected/actual, mismatch dan cycles. Parallel8: 6.916 siklus; 18.192/400 output tetap berlabel legacy. | Bukti simulasi [S02](#sumber-s02)/[S16](#sumber-s16); replay board memakai raw run dan [S22](#sumber-s22) |
| <a id="textfield-d3"></a>**D3 — E-stop** | Tampilkan baseline nonnol, assertion E-stop, keluaran nol, fault 2, lalu update counter/last_fault. Untuk robot, roda dan terminal masuk video yang sama. | RTL PASS, checkpoint tepat pada [S06](#sumber-s06); board memakai [S10](#sumber-s10) |
| <a id="textfield-d4"></a>**D4 — peta/perintah invalid** | Tampilkan motor_enable/v/omega nol, kode sesuai penyebab dan logger. Peta invalid memakai fault 5; batas kecepatan/perubahan mengikuti test gate dan fault 10/11. | [S05](#sumber-s05), [S06](#sumber-s06), [S07](#sumber-s07); akuisisi [S10](#sumber-s10) |
| <a id="textfield-d5"></a>**D5 — cabut komunikasi** | Ukur dari putus link sampai STOP dan roda berhenti; simpan timestamp serta frame video. Host fixture mendukung pemeriksaan watchdog/transport. | [S09](#sumber-s09) adalah fixture; stop time fisik diukur dengan [S10](#sumber-s10)/[S11](#sumber-s11) |
| <a id="textfield-d6"></a>**D6 — slide bukti** | Tampilkan waveform core, tabel siklus, hasil model serta checkpoint safety. Grafik host, Studi A/B dan RTT menggunakan raw data pengukuran terkait. | [S02](#sumber-s02), [S05](#sumber-s05), [S11](#sumber-s11), [S21](#sumber-s21), [S23](#sumber-s23) |
| <a id="textfield-d7"></a>**D7 — PERURI dan bisnis** | Jelaskan pengguna integrator AGV/AMR, manfaat integritas kendali/audit, paket pilot berbayar dan langkah menuju silicon. Contoh biaya shuttle Rp40,34 juta dan jasa pilot Rp75 juta diberi label estimasi/skenario. | Rumus dan kondisi biaya [S14](#sumber-s14), [S15](#sumber-s15) |

## A1–A14: jawaban eksplisit checklist board dan robot

Status di bagian ini membedakan **paket/prosedur tersedia** dari **hasil penerimaan fisik**. Nilai pengukuran board dicatat ketika raw run, identitas perangkat dan hash SOF tersedia.

| Text field asal | Jawaban / hasil yang harus dicatat | Sumber yang disiapkan |
|---|---|---|
| <a id="textfield-a1"></a>**A1 — program dan uji vektor** | Pilih model/SOF, program board, simpan identitas board, hash, expected/actual dan mismatch. Dataset 400 output berlaku pada legacy; enam scene DWA disertakan bila planner didemokan. | [S02](#sumber-s02), [S16](#sumber-s16), [S17](#sumber-s17), [S19](#sumber-s19), [S20](#sumber-s20) |
| <a id="textfield-a2"></a>**A2 — timer board** | Catat cycles per keputusan dan clock Hz. Acuan Parallel8 6.916 siklus; DWA legacy 7.938. Pisahkan kernel, serial dan end-to-end. | [S02](#sumber-s02), [S10](#sumber-s10), [S17](#sumber-s17) |
| <a id="textfield-a3"></a>**A3 — safety di board** | E-stop, peta invalid, batas kecepatan/perubahan dan deadline harus menutup permit, menolkan output dan merekam kode/counter. Simpan raw frame, timestamp, SOF hash dan video. | [S05](#sumber-s05), [S06](#sumber-s06), [S07](#sumber-s07), [S10](#sumber-s10) |
| <a id="textfield-a4"></a>**A4 — Jetson sebagai kurir** | Mode kurir membuktikan payload FPGA diteruskan utuh, timestamp tercatat dan STOP saat lease/link gagal. Pada PPO residual, blending/kinematika yang masih dikerjakan host tetap disebut sebagai fungsi host. | [S09](#sumber-s09), [S11](#sumber-s11), [S25](#sumber-s25) |
| <a id="textfield-a5"></a>**A5 — asal perintah motor** | Telusuri stimulus, gate output, permit, fault, payload motor dan roda dalam satu run; ini acceptance yang menunjukkan jalur aktuator mengikuti keluaran yang dijaga. | [S06](#sumber-s06), [S10](#sumber-s10), [S11](#sumber-s11) |
| <a id="textfield-a6"></a>**A6 — empat roda** | Uji maju/mundur/geser/putar, label channel dan rekam payload, telemetry serta video tiap pola. | Paket motor offline [S24](#sumber-s24); acceptance [S11](#sumber-s11) |
| <a id="textfield-a7"></a>**A7 — benchmark Jetson** | Jalankan 10.000 iterasi per kondisi idle/sibuk dengan model yang sama. Simpan raw timing, median, p99, maksimum, konfigurasi mesin dan beban. | Protokol [S11](#sumber-s11), provenance [S22](#sumber-s22) |
| <a id="textfield-a8"></a>**A8 — round-trip** | Ukur observasi sampai respons dan end-to-end motor secara terpisah memakai sequence/timestamp monotonic; evaluasi raw distribusi terhadap anggaran kontrol 0,1 s. | [S10](#sumber-s10), [S11](#sumber-s11) |
| <a id="textfield-a9"></a>**A9 — run lintasan** | Tiga run tiap konfigurasi pada start/tujuan sama, dengan log sensor, model, bobot, event tabrakan/timeout dan video. | [S11](#sumber-s11), [S22](#sumber-s22) |
| <a id="textfield-a10"></a>**A10 — replay fisik** | Bekukan log observasi dan bandingkan setiap output terhadap model integer yang sama; catat indeks keputusan, cycles dan mismatch. | [S02](#sumber-s02), [S11](#sumber-s11), [S22](#sumber-s22) |
| <a id="textfield-a11"></a>**A11 — video dan cadangan** | Rekam lintasan, fault injection, slow-motion stop dan terminal; setiap video mengacu ke run_id serta hash rilis, dicadangkan dua salinan. | [S10](#sumber-s10), [S11](#sumber-s11), [S19](#sumber-s19) |
| <a id="textfield-a12"></a>**A12 — keputusan retraining** | Bekukan kontrak model dahulu: PPO source 74→128→64→3; target 24→64→64→4 pada text field adalah jalur legacy. Perubahan bobot memerlukan ekspor dan pengujian ulang. | [S16](#sumber-s16), [S22](#sumber-s22), [S23](#sumber-s23) |
| <a id="textfield-a13"></a>**A13 — freeze versi** | Manifest mengikat RTL, bobot, SOF, laporan dan script; periksa hash sebelum programming dan kaitkan log/video pada identitas rilis. | [S19](#sumber-s19) |
| <a id="textfield-a14"></a>**A14 — pengukuran daya** | Catat rail/input board, tegangan, arus, instrumen, idle/aktif dan cakupan HPS/periferal. Pisahkan pengukuran tersebut dari estimasi Quartus atau ASIC. | Metode [S11](#sumber-s11); estimasi [S13](#sumber-s13), [S26](#sumber-s26) |

## B1–B6: jawaban eksplisit analisis dan materi publikasi

| Text field asal | Jawaban / metode yang dapat direproduksi | Sumber |
|---|---|---|
| <a id="textfield-b1"></a>**B1 — Studi A** | Minimal 100 episode dengan seed berpasangan, simulator/sensor sama, plus lima skenario ekstrem; laporkan sukses, tabrakan, timeout, waktu dan kehalusan. Hasil numerik memakai raw episode studi. | [S11](#sumber-s11), [S22](#sumber-s22) |
| <a id="textfield-b2"></a>**B2 — Studi B** | Uji sensor beku/hilang, peta usang, perintah ekstrem dan obstacle; hitung unsafe command lolos, tabrakan serta stop yang tidak diperlukan. RTL fault coverage menjadi bukti blok; outcome robot/simulator dilaporkan dari studi tersendiri. | [S05](#sumber-s05), [S06](#sumber-s06), [S11](#sumber-s11) |
| <a id="textfield-b3"></a>**B3 — grafik waktu** | Gunakan raw A7/A8 dan counter A2; tampilkan core, serial dan host sebagai kategori waktu terpisah dengan satuan serta identitas model. | [S02](#sumber-s02), [S11](#sumber-s11) |
| <a id="textfield-b4"></a>**B4 — tabel angka final** | Pakai ledger di atas: model, nilai, unit, kondisi dan file bukti. Field fisik yang belum diukur diberi status pengukuran, tidak diisi angka ilustrasi. | [S02](#sumber-s02), [S05](#sumber-s05), [S13](#sumber-s13), [S14](#sumber-s14), [S19](#sumber-s19) |
| <a id="textfield-b5"></a>**B5 — slide dan latihan** | Naskah D1–D7: fungsi → replay → E-stop → input invalid → link loss → bukti → nilai bisnis; tiga latihan penuh memakai rilis yang sama. | [S11](#sumber-s11), [S15](#sumber-s15), [S19](#sumber-s19) |
| <a id="textfield-b6"></a>**B6 — video offline** | Susun 3–5 menit dari rekaman run teridentifikasi; beri judul skenario, simpan di laptop dan flashdisk, uji pemutaran offline. | [S11](#sumber-s11), [S19](#sumber-s19) |

## Security: titik bukti output FPGA, gate dan logger

**Keberhasilan safety dijelaskan lewat hubungan stimulus → izin → output → logger.** Berikut checkpoint simulasi planner yang bisa dibuka persis waktunya; angka ns adalah waktu testbench.

| Text field | File / waktu / nama kasus | Bukti keberhasilan |
|---|---|---|
| K3/K5, D3, A3/A5 | `top.vcd`, **814535 ns**, `estop_asserted_between_clocks_immediate_zero` | `motor_enable=0`, v/omega nol, `fault_code=2` saat E-stop |
| K5, D3, A3 | `top.vcd`, **814551 ns**, `estop_registered_error_log` | Keluaran tetap nol, `event_count=3`, `last_fault=2` |
| K3/K5, D4, A3 | `top.vcd`, **2931031 ns**, `write_without_map_begin_zero_and_logged` | Peta tidak sah ditolak, output nol, `fault_code=5`, `last_fault=5` |
| K3, D4, A3 | `top.vcd`, **3945471 ns**, `map_freshness_exact_boundary_zero` | Tepat `map_age=10000`, output nol dan fault 5; logger diperiksa pada checkpoint berikutnya |
| K3/K5, D4, A3 | `uart.vcd`, **366251 ns**, `run_nonzero_payload` | `invalid_command=1`, `accepted_commands=0`, output nol, fault/last_fault 4 |
| K3/K5, D4, A3 | `uart.vcd`, **944631 ns**, `crc_corruption_zero_and_logged` | `protocol_fault=1`, output nol, `last_fault=4` |

Buka [top.gtkw](evidence/current_safety/top.gtkw) dengan [top.vcd](evidence/current_safety/top.vcd), atau [uart.gtkw](evidence/current_safety/uart.gtkw) dengan [uart.vcd](evidence/current_safety/uart.vcd). CSV [S06](#sumber-s06) menyimpan nama kasus, waktu dan sinyal. Assertion memeriksa expected/actual, permit tertutup, output nol dan penyebab tercatat pada fase logger yang benar. Output langsung dan logger dibaca pada checkpoint masing-masing.

Untuk board, [S10](#sumber-s10) mengakuisisi raw frame, timestamp dan identitas SOF. Satu `run_id` harus menghubungkan **input gangguan → output FPGA → gate → fault log → payload aktuator → video**. Stop time, RTT, median/p99 Jetson, daya board, keberhasilan lintasan dan outcome Studi A/B menjadi hasil pengukuran ketika raw run tersedia; angka contoh tidak menggantikan field tersebut.

## Untuk PERURI dan Indonesia: jawaban nilai produk

**Usulan pengguna awal:** integrator AGV/AMR untuk perpindahan bahan dan produk bernilai tinggi di lingkungan kerja terkontrol. IGOR menawarkan aturan kendali dekat keluaran, antarmuka yang dapat diprogram serta log kejadian untuk diagnosis. Pilot dimulai pada satu rute dan konfigurasi yang disepakati, dengan penerimaan fungsi, gangguan, latency dan traceability. Ini adalah usulan aplikasi, bukan pernyataan kontrak atau hasil armada PERURI.

**Nilai strategis:** IP lokal meliputi Verilog, bobot terkuantisasi, firmware, model referensi, host driver dan paket verifikasi. Penguasaan komponen tersebut mendukung talenta serta desain semikonduktor nasional. HMAC/secure element untuk keaslian peta dapat menjadi kolaborasi roadmap tersendiri; CRC dibahas sebagai deteksi error transfer. Security publikasi berfokus pada integritas operasi dan akses I/O. Sertifikasi keselamatan mengikuti evaluasi produk serta audit yang sesuai, terpisah dari hasil simulasi.

Statistik pasar/kecelakaan, contoh bank sentral, 2.400 intervensi/tahun, TAM dan payback 26/46 bulan pada text field diperlakukan sebagai hipotesis proposal sampai sumber serta asumsi kuantitatifnya dilampirkan. Narasi bisnis berikut berdiri pada kemampuan teknis dan perhitungan proyek yang dapat dibuka.

## Bisnis dan fabrikasi IDR: jawaban yang konkret

Yang ditawarkan adalah rekayasa pilot/integrasi, modul dengan acceptance yang disepakati, dukungan dan opsi lisensi IP sesuai hak penggunaan komponennya. **Angka bisnis berikut adalah skenario perencanaan, bukan transaksi atau harga pasar aktual.**

| Pertanyaan text field | Jawaban | Sumber |
|---|---|---|
| Siapa pelanggan dan manfaatnya? | Integrator robot logistik/inspeksi dan otomasi; pilot PERURI adalah usulan aplikasi. Manfaat: komputasi core terukur, pembatasan operasi dan diagnosis yang dapat ditelusuri. | [S11](#sumber-s11), [S15](#sumber-s15) |
| Berapa prototipe IHP? | Protocol engine **24 tile**, **€1.995 ≈ Rp40.343.109**, sebelum pajak/bea. Kurs jual BI **Rp20.222,11/EUR**, 16 Oktober 2026; snapshot tarif Tiny Tapeout 17 Oktober. | [S14](#sumber-s14), [S15](#sumber-s15) |
| Berapa anggaran proyek? | Contoh satu iterasi protocol engine berikut engineering, PCB, test dan cadangan: **Rp132.644.575**. | Asumsi dan rumus [S15](#sumber-s15) |
| Contoh pendapatan pilot? | Harga **Rp75 juta**, biaya langsung Rp40 juta, kontribusi Rp35 juta/proyek; biaya tetap Rp150 juta, titik impas **5 proyek**. | Model jasa [S15](#sumber-s15) |
| Contoh produk volume? | Modul Rp1,5 juta, target HPP Rp900 ribu, biaya variabel Rp100 ribu, kontribusi Rp500 ribu; NRE Rp500 juta, titik impas **1.000 modul**. HPP masih asumsi yang diganti quotation. | Model modul [S15](#sumber-s15) |
| Bagaimana menuju fabrikasi? | Spesifikasi → freeze → verifikasi → implementasi IHP → sign-off → paket GDS/provenance → quotation → wafer/assembly → karakterisasi → pilot. | Alur fabless [S15](#sumber-s15) |
| Bagaimana memakai harga retrofit Rp25 juta/TAM/royalti dari proposal? | Sebagai skenario proposal dengan volume, unit, cakupan layanan serta sumber asumsi. Tidak digabung menjadi satu harga dengan contoh jasa/modul di atas. | Text field bisnis; aturan lingkup [S15](#sumber-s15) |

Biaya 24 tile berlaku pada protocol engine ASIC. Sistem AI/safety yang digabungkan memakai area hasil implementasi dan quotation tersendiri. Tarif shared shuttle berbeda cakupan dari HPP chip volume; packaging, pajak, pengiriman, test dan yield mengikuti penawaran. Manfaat finansial pelanggan dihitung dari baseline operasional pilot yang diukur.

## Glosarium untuk penjelasan lisan

- **FPGA / ASIC:** media prototipe rangkaian yang dapat diprogram ulang / implementasi chip melalui proses fabrikasi yang dipilih.
- **PPO residual / SAC legacy:** kebijakan source IGOR menghasilkan tiga koreksi kendali / identitas neural 24-input dalam text field historis.
- **MAC / siklus:** satu perkalian-penjumlahan / satu detak clock; 20 ns pada 50 MHz.
- **M10K / ROM bobot / SRAM:** resource memori blok FPGA / parameter neural yang diinisialisasi dan dibaca / memori program ASIC 256×16-bit.
- **DWA / safety gate / fail-closed:** pemeriksaan kandidat gerak / aturan pelepasan keluaran / kondisi invalid menutup izin pada jalur yang dilindungi.
- **Bit-exact / p99 / seed:** identik terhadap model integer tertentu / persentil ke-99 dataset waktu / identitas pengacakan agar skenario dapat diulang.
- **Replay / kurir:** memutar observasi rekaman / meneruskan payload tanpa keputusan; dibedakan dari host yang masih melakukan blending atau kinematika.
- **AGV/AMR / retrofit / NRE:** robot transport industri / penambahan fungsi pada sistem yang ada / biaya pengembangan tetap.

## Katalog sumber dan cara melacak text field

Cari ID Sxx di bawah. JSON S02 memuat `cycles`, `clock_hz`, `suites`, `fitter_summary`; S05 memuat `gate_comparisons`, `gate_fault_bins`, `checkpoint_count`, `source_sha256`; S09 memuat `tests`, `failures`, `errors`, `success`; S14 memuat `idr_conversion`. Pada CSV S06 cari nama kasus serta `time_ns` di tabel security.

| ID | File sumber yang dapat dibuka |
|---|---|
| <a id="sumber-s01"></a>**S01** | [Verilog core Parallel8](experiments/parallel8/igor_src_policy_core.v) |
| <a id="sumber-s02"></a>**S02** | [Acceptance Parallel8](experiments/parallel8/artifacts/acceptance.json) |
| <a id="sumber-s03"></a>**S03** | [Fitter DE10-Nano](experiments/parallel8/output_files/igor_src_policy.fit.summary) |
| <a id="sumber-s04"></a>**S04** | [STA semua corner FPGA](experiments/parallel8/output_files/igor_src_policy.sta.summary) |
| <a id="sumber-s05"></a>**S05** | [Safety summary dan hash source](evidence/current_safety/summary.json) |
| <a id="sumber-s06"></a>**S06** | [CSV checkpoint safety](evidence/current_safety/cases.csv) |
| <a id="sumber-s07"></a>**S07** | [RTL safety gate](rtl/igor_safety_security_gate.v) |
| <a id="sumber-s08"></a>**S08** | [RTL logger](rtl/igor_status_logger.v) |
| <a id="sumber-s09"></a>**S09** | [Hasil host fixture](evidence/current_host/results.json) |
| <a id="sumber-s10"></a>**S10** | [Alat akuisisi board safety](verification/capture_hardware_safety.py) |
| <a id="sumber-s11"></a>**S11** | [Matriks acceptance A/B/D](docs/IMPLEMENTATION_READINESS.md) |
| <a id="sumber-s12"></a>**S12** | [42 tes protocol engine PASS](evidence/chip_highlights/results.json) |
| <a id="sumber-s13"></a>**S13** | [Power ASIC dan sumber laporan](power.md) |
| <a id="sumber-s14"></a>**S14** | [Tarif dan kurs IDR](evidence/chip_highlights/tinytapeout_pricing.json) |
| <a id="sumber-s15"></a>**S15** | [Arsitektur, parameter, bisnis dan fabrikasi](CHIP_ADVANTAGES.md) |
| <a id="sumber-s16"></a>**S16** | [Hasil neural legacy](verification/neural_cocotb_results.json) |
| <a id="sumber-s17"></a>**S17** | [Hasil enam scene DWA legacy](verification/scene_cocotb_results.json) |
| <a id="sumber-s18"></a>**S18** | [Coverage gate legacy](verification/gate_functional_coverage.json) |
| <a id="sumber-s19"></a>**S19** | [Manifest rilis dan hash artefak](evidence/current_release/manifest.json) |
| <a id="sumber-s20"></a>**S20** | [Proyek Quartus Parallel8](experiments/parallel8/igor_src_policy.qpf) |
| <a id="sumber-s21"></a>**S21** | [Screenshot GTKWave core](experiments/parallel8/artifacts/core_latency.png) |
| <a id="sumber-s22"></a>**S22** | [Provenance model source](verification/src_policy/artifacts/model_provenance.json) |
| <a id="sumber-s23"></a>**S23** | [Karakterisasi numerik model source](verification/src_policy/artifacts/results.json) |
| <a id="sumber-s24"></a>**S24** | [Verifikasi motor offline](robot/jetauto/offline_verification.json) |
| <a id="sumber-s25"></a>**S25** | [Controller host integrasi](software_integration/src/igor_controller/igor_controller/controller_node.py) |
| <a id="sumber-s26"></a>**S26** | [Power FPGA Parallel8 Typical](experiments/parallel8/artifacts/power/typical/igor_src_policy.pow.summary) |
| <a id="sumber-s27"></a>**S27** | [Functional gate-level ASIC terlampir](evidence/asic_import/gatelevel_test_results/raw/results.xml) |

[Traceability JSON](evidence/bennaya_answers/traceability.json) menyimpan ID text field, cuplikan pendek dan posisi karakter pada lampiran asal, SHA256 dokumen sumber, lokasi jawaban serta hash sumber bukti. Dokumen internal lengkap tidak disalin ke naskah publikasi ini. Metadata menghubungkan pertanyaan asal dengan jawaban tanpa memperlakukan rencana sebagai hasil eksperimen.

**Kalimat penutup presentasi:** “IGOR membawa kecerdasan robot ke hardware yang terukur: core neural 138,32 mikrodetik, bobot on-chip, proteksi operasi pada jalur kendali, dan jejak bukti dari Verilog sampai pengujian. Kami membangun IP lokal yang dapat dijelaskan, diprogram dan dikembangkan menuju aplikasi industri serta silicon.”


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
| Core Parallel8 / `core` | 100.00% (68/68) | 100.00% (96/96) | 95.81% (870/908) | Memenuhi target line, branch dan toggle pada suite core. |
| Transport policy / `uart` | 97.87% (46/47) | 100.00% (46/46) | 71.76% (371/517) | Line/branch memenuhi; toggle belum mencapai 90%. |
| UART RX / `uart` | 90.00% (9/10) | 100.00% (14/14) | 70.45% (31/44) | Branch memenuhi; line dan toggle belum mencapai target. |
| UART TX / `uart` | 100.00% (5/5) | 100.00% (4/4) | 69.77% (30/43) | Line/branch memenuhi; toggle belum mencapai 90%. |
| Wrapper DE10-Nano / `board` | 100.00% (4/4) | 100.00% (6/6) | 26.29% (51/194) | Line/branch memenuhi; toggle belum mencapai 90%. |
| Safety gate / `gate` | 100.00% (13/13) | Belum dihasilkan tool | 95.33% (102/107) | Line/toggle memenuhi; branch native tidak dilaporkan. |

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
| `board` | `igor_src_policy_core.v` | `v_branch` | 95/96 | 98.96% |
| `board` | `igor_src_policy_core.v` | `v_line` | 60/68 | 88.24% |
| `board` | `igor_src_policy_core.v` | `v_toggle` | 789/908 | 86.89% |
| `board` | `igor_src_policy_de10_nano.v` | `v_branch` | 6/6 | 100.00% |
| `board` | `igor_src_policy_de10_nano.v` | `v_line` | 4/4 | 100.00% |
| `board` | `igor_src_policy_de10_nano.v` | `v_toggle` | 51/194 | 26.29% |
| `board` | `igor_src_policy_uart.v` | `v_branch` | 35/46 | 76.09% |
| `board` | `igor_src_policy_uart.v` | `v_line` | 37/47 | 78.72% |
| `board` | `igor_src_policy_uart.v` | `v_toggle` | 214/517 | 41.39% |
| `board` | `igor_uart_rx.v` | `v_branch` | 13/14 | 92.86% |
| `board` | `igor_uart_rx.v` | `v_line` | 8/10 | 80.00% |
| `board` | `igor_uart_rx.v` | `v_toggle` | 33/44 | 75.00% |
| `board` | `igor_uart_tx.v` | `v_branch` | 4/4 | 100.00% |
| `board` | `igor_uart_tx.v` | `v_line` | 5/5 | 100.00% |
| `board` | `igor_uart_tx.v` | `v_toggle` | 33/43 | 76.74% |
| `core` | `igor_src_policy_core.v` | `v_branch` | 96/96 | 100.00% |
| `core` | `igor_src_policy_core.v` | `v_line` | 68/68 | 100.00% |
| `core` | `igor_src_policy_core.v` | `v_toggle` | 870/908 | 95.81% |
| `gate` | `igor_safety_security_gate.v` | `v_line` | 13/13 | 100.00% |
| `gate` | `igor_safety_security_gate.v` | `v_toggle` | 102/107 | 95.33% |
| `uart` | `igor_src_policy_core.v` | `v_branch` | 95/96 | 98.96% |
| `uart` | `igor_src_policy_core.v` | `v_line` | 61/68 | 89.71% |
| `uart` | `igor_src_policy_core.v` | `v_toggle` | 829/908 | 91.30% |
| `uart` | `igor_src_policy_uart.v` | `v_branch` | 46/46 | 100.00% |
| `uart` | `igor_src_policy_uart.v` | `v_line` | 46/47 | 97.87% |
| `uart` | `igor_src_policy_uart.v` | `v_toggle` | 371/517 | 71.76% |
| `uart` | `igor_uart_rx.v` | `v_branch` | 14/14 | 100.00% |
| `uart` | `igor_uart_rx.v` | `v_line` | 9/10 | 90.00% |
| `uart` | `igor_uart_rx.v` | `v_toggle` | 31/44 | 70.45% |
| `uart` | `igor_uart_tx.v` | `v_branch` | 4/4 | 100.00% |
| `uart` | `igor_uart_tx.v` | `v_line` | 5/5 | 100.00% |
| `uart` | `igor_uart_tx.v` | `v_toggle` | 30/43 | 69.77% |

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
| 0 | 66,915 |
| 1 | 6,509 |
| 2 | 3,236 |
| 3 | 1,612 |
| 4 | 858 |
| 5 | 431 |
| 6 | 185 |
| 7 | 100 |
| 8 | 52 |
| 9 | 36 |
| 10 | 4,105 |
| 11 | 27,171 |

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
