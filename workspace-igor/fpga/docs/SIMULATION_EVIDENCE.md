# Bukti visual GTKWave dan kompilasi Quartus

Pemeriksaan 17 Oktober 2026. Acuan policy tetap [README workspace](../../README.md): **PPO 74→128→64→3**, bukan neural 24-input legacy. Semua gambar dan file baru berada dalam `fpga`.

**Buka galeri:** [index.html](../evidence/visual_review/index.html). Identitas gambar, hash waveform, checkpoint, perintah capture dan log tersimpan pada [index.json](../evidence/visual_review/index.json).

## Jenis gambar dan batas bukti

- **15 PNG GTKWave adalah screenshot asli**, dibuat aplikasi GTKWave v3.3.100 melalui API Tcl bawaan `Grab_To_File`. Gambar asli tidak digambar ulang, diberi overlay, atau direkayasa menjadi waveform. Sinyal bus menggunakan nama dan rentang bit dari header VCD; script menolak capture jika ada sinyal hilang atau jumlah trace yang tampil tidak sesuai.
- **Dua PNG Quartus adalah gambar ekstrak laporan asli, bukan screenshot GUI Quartus.** Gambar menyalin baris keberhasilan dari log dan angka/hash dari receipt yang diperiksa terhadap file sumber, report dan SOF. Label tersebut tertulis di gambar. Screenshot GUI Quartus belum dapat diambil karena helper Windows gagal tersambung setelah satu kali recovery; [catatan kegagalan](../evidence/visual_review/computer_use_status.json) menyimpan statusnya. Tidak ada tampilan GUI Quartus palsu.
- Seluruh waveform adalah **simulasi RTL**, bukan pembacaan pin, SignalTap board, atau video robot. Build PASS juga tidak membuktikan programming maupun pengujian fisik.

Metode native mengikuti [menu GTKWave resmi](https://gtkwave.github.io/gtkwave/ui/menu.html) dan [API Tcl resmi](https://gtkwave.github.io/gtkwave/tcl/commands.html). Native grab dapat terganggu window yang menutupi layar; gambar hasil capture sudah diperiksa secara visual. File `.gtkw` dan `.tcl` per gambar tersedia pada folder galeri untuk reproduksi.

## Mengapa simulasi dinyatakan berhasil?

Kelulusan ditentukan oleh pemeriksaan terprogram, bukan warna hijau di waveform. Testbench membandingkan hasil aktual terhadap expected/oracle, memanggil `$fatal` jika berbeda, dan runner mewajibkan exit code nol **serta** baris PASS. Hash RTL/testbench dicatat sebelum dan sesudah run; perubahan file selama run menyebabkan kegagalan. [Audit acceptance](../evidence/current_acceptance/audit.json) menghubungkan source saat ini dengan bukti policy, safety, wrapper, host, model dan LiDAR.

Policy menggunakan oracle Python integer yang menghitung dot product dengan integer tak terbatas, independen dari FSM, register dan penjadwalan alamat RTL. Sebanyak **236 vektor** memeriksa semua **192 hidden activation dan tiga output**; **8.364 kasus aktivasi** memeriksa floor/ReLU/clip/saturasi. Hasilnya **54.399 assertion core**. UART mempunyai **184 transaksi directed / 268 assertion**; decoder respons bit-level tidak memakai modul receiver DUT. Wrapper board aktual juga lulus **18 checkpoint** dengan clock simulasi 50 MHz dan divider UART 54.

Planner/gate mempunyai **111.210 pembandingan terhadap oracle**, seluruh outcome 0–11 terjangkau, serta **111 checkpoint** unit/top/UART. Checkpoint mencakup kontrol positif, fault dan recovery; bukan 111 fault semuanya nol. Lihat [summary safety](../evidence/current_safety/summary.json). Coverage ini bukan pembuktian formal semua peta, nilai analog atau interleaving temporal.

## Cara membaca screenshot

Kolom nilai dan bus pada galeri memakai **heksadesimal**: `0a` = fault 10, `0b` = fault 11, `d44c` = 54.348 siklus, `ffffffff` = 4.294.967.295. Nilai signed Q8.8 perlu ditafsirkan sebagai komplemen dua dan dibagi 256; misalnya `ffc7` = -57 = -0,22265625. Nilai pada kolom kiri sesuai marker merah, bukan selalu sisi kiri waveform.

GTKWave menampilkan waktu dalam ns; CSV policy menyimpan **ps**. Konversi **1 ns = 1000 ps**. CSV safety sudah memakai ns. Marker harus cocok dengan instance yang disebut; varian deadline/freshness bukan output instance `core` utama.

**Perbedaan delta-cycle yang penting:** beberapa testbench menulis CSV lalu mengganti `test_id`/stimulus atau memanggil `$dumpoff` pada timestamp yang sama. VCD menyimpan keadaan akhir timestamp itu, sehingga marker persis pada waktu CSV dapat menampilkan kasus berikutnya atau X dari dump-off. Capture policy UART memakai sampel stabil **1 ps sebelum waktu CSV**; core memakai **1 ns sebelum** checkpoint terakhir sebelum dump-off. Gate memakai 0,999 / 10,999 / 11,999 ns untuk PASS/absolute/delta. Script membaca VCD secara independen, menolak X/Z pada sinyal yang ditampilkan dan membandingkan nilainya dengan CSV sebelum mengambil gambar. Offset dan nilai sampel tersimpan di `index.json`.

## Titik penting planner dan gate

| Gambar | Titik / instance | Perilaku yang membuktikan kelulusan |
|---|---|---|
| [01 E-stop dan logger](../evidence/visual_review/01_planner_estop_and_logger.png) | `top.vcd`, `core`; E-stop **814535 ns**, logger **814551 ns** | Sebelum fault, kontrol positif pada 814531 ns mempunyai permit=1 dan v=15. Saat E-stop, permit/v/omega menjadi nol dan fault=2, tanpa menunggu clock logger. Pada marker logger, event_count=3 dan last_fault=2. Angka 3 mencakup riwayat test sebelumnya. Setelah E-stop dilepas, abort tertahan sampai reset. |
| [02 Peta invalid](../evidence/visual_review/02_planner_invalid_map.png) | **2931031 ns**, `core` | Write tanpa map begin menghasilkan map fault, permit/v/omega nol, fault dan last_fault=5. Peta parsial tidak boleh dipakai. |
| [03 Deadline](../evidence/visual_review/03_planner_deadline.png) | **3904291 ns**, `deadline_core` | Deadline komputasi menghasilkan fault=8, permit nol dan retained cause=8; hasil terlambat tidak diteruskan. |
| [04 Freshness peta](../evidence/visual_review/04_planner_map_freshness.png) | Batas **3945471 ns**, logger **3945491 ns**, `freshness_core` | Tepat map_age=10000 peta menjadi tidak fresh, permit nol dan fault=5. Logger menyusul pada edge berikutnya. |
| [05 Lease hasil](../evidence/visual_review/05_planner_result_lease.png) | Batas **3945511 ns**, logger **3945531 ns**, `core` | Hasil lama ditarik tepat elapsed=10000; permit nol dan fault=8. Tidak boleh mempertahankan command karena pernah sah sebelumnya. |
| [06 Versi peta](../evidence/visual_review/06_planner_map_version.png) | Commit **4759921 ns**, logger **4759931 ns** | `seq` berubah menjadi 2 sedangkan `run_map_sequence` masih 1; `result_map_matches=0`, permit nol, fault=9. Run baru pada map seq 2 memulihkan permit di 4918711 ns, dibuktikan CSV. |
| [07 Semua outcome gate](../evidence/visual_review/07_gate_all_outcomes.png) | `gate.vcd`; marker stabil **0,999 / 10,999 / 11,999 ns** | PASS meneruskan v=3 pada 0,999 ns. Setiap kondisi penolakan 1–11 menolkan enable/v/omega. Pada 10,999 ns fault `0a` menunjukkan batas absolut; pada 11,999 ns `0b` menunjukkan batas perubahan. CSV assertion masing-masing mencatat 1/11/12 ns; tepat 12 ns dump dimatikan dan VCD menjadi X. |

Sumber expected/actual: [top_checkpoints.csv](../evidence/current_safety/top_checkpoints.csv), [gate_checkpoints.csv](../evidence/current_safety/gate_checkpoints.csv), dan [cases.csv](../evidence/current_safety/cases.csv). Fault map dan gate ini adalah **profil planner terpisah**, bukan pemeriksaan costmap pada frame policy 74-input.

## Titik penting policy yang mengikuti README

| Gambar | Waktu CSV; marker UART = CSV − 1 ps | Perilaku yang diperiksa |
|---|---|---|
| [08 Inferensi selesai](../evidence/visual_review/08_policy_bit_exact_done.png) | CSV **2185415000 ps**; marker **2185414000 ps = 2185414 ns**, test 1 | Marker dipilih 1 ns sebelum dump-off: `busy=0`, `done=1`, `fault=0`, latency=`d44c` (54.348). Aktivasi dan tiga output telah dibandingkan; pemeriksaan indeks invalid selesai pada waktu CSV. `output_index=3` sengaja menghasilkan nol, bukan klaim bahwa ketiga aksi policy bernilai nol. |
| [09 CRC salah](../evidence/visual_review/09_policy_crc_reject.png) | **2958071000 ps** | Error=6, permit=0, tiga guarded residual nol, accepted=0, tidak ada respons sukses. Frame rusak tidak boleh dimuat sebagai inferensi sah. |
| [10 E-stop saat inferensi](../evidence/visual_review/10_policy_estop_inference.png) | **3494691000 ps** | Policy error=1, permit=0 dan residual nol. Inferensi dibatalkan; testbench juga memeriksa tidak ada respons sukses. Kode E-stop policy berbeda dari planner (2). |
| [11 E-stop saat TX](../evidence/visual_review/11_policy_estop_tx.png) | **7533671000 ps** | E-stop membatalkan serializer, permit nol dan error=1. Decoder independen memastikan frame sukses lengkap/CRC-valid tidak tersisa setelah pembatalan di tengah frame. |
| [12 Residual stale](../evidence/visual_review/12_policy_stale.png) | **12465731000 ps** | Permit dicabut ketika lease residual habis; error=`0b` (11), seluruh guarded residual nol. |
| [13 Counter accepted penuh](../evidence/visual_review/13_counter_accepted_max.png) | **62514331000 ps**, test 1401 | Dua transaksi valid pada kondisi batas tidak membuat counter kembali nol. Counter tetap `ffffffff`, permit valid, respons dan tiga residual tetap sesuai oracle. |
| [14 Counter rejected penuh](../evidence/visual_review/14_counter_rejected_max.png) | **63011231000 ps**, test 1404 | Sesudah CRC reject berulang lalu E-stop, counter tetap `ffffffff`; E-stop tetap membatalkan permit dan mencatat error/history. |
| [15 Reset dan pemulihan](../evidence/visual_review/15_counter_reset_recovery.png) | **64366191000 ps**, test 1406 | Reset telah menghapus kedua counter dan permit lama; transaksi baru memberi accepted=1, rejected=0 dan residual valid (-57,76,42 raw Q8.8). |

Sumber: [core_checkpoints.csv](../verification/src_policy/artifacts/core_checkpoints.csv), [uart_checkpoints.csv](../verification/src_policy/artifacts/uart_checkpoints.csv), [core.log](../verification/src_policy/artifacts/core.log), [uart.log](../verification/src_policy/artifacts/uart.log), [results.json](../verification/src_policy/artifacts/results.json). Sweep besar tertentu mematikan waveform dump; tidak mengklaim semua assertion mempunyai transisi VCD yang tersimpan.

**Residual nol bukan STOP motor.** Policy tidak mempunyai costmap atau final motor permit. Pada transaksi gagal, host integrasi memerintahkan empat RPS nol. Blending, filter dan kinematika masih host; pengujian motor/E-stop fisik tetap terbuka.

## Mengapa kompilasi dinyatakan berhasil?

| Bukti gambar | Source / hasil | Arti PASS |
|---|---|---|
| [Policy Quartus](../evidence/visual_review/quartus_source_policy.png) | Build ulang **17 Oktober 2026 08:22:09 WIB**, target `5CSEBA6U23I7`, 13 fitted pins | Synthesis, Fitter, Assembler dan Timing Analyzer sukses; full compilation 0 error / 3 warning. Setup terburuk +6,019 ns, hold +0,116 ns. SOF dihasilkan dan hash input sebelum/sesudah tidak berubah. |
| [Planner Quartus](../evidence/visual_review/quartus_planner.png) | Build tervalidasi **16 Oktober 2026 18:01:03 WIB**, target sama, 17 fitted pins | Full compilation 0 error / 9 warning; setup terburuk +0,641 ns, hold +0,094 ns. Ini laporan build planner yang ada dan masih cocok hash, bukan kompilasi baru pada 17 Oktober. |

Semua corner setup/hold/recovery/removal/minimum pulse yang dilaporkan nonnegatif; runner memeriksanya, tidak hanya teks “Timing Analyzer successful”. Fitter memuat seluruh pin lokasi dan standar 3,3 V, drive/slew eksplisit. Policy tetap 3.249 ALM / 64 M10K / 1 DSP; planner 5.048 / 131 / 10.

Warning policy berasal dari port tulis internal ROM read-only. Warning planner direview pada [BUILD_STATUS](../BUILD_STATUS.md). Tidak ada klaim “tanpa warning”, MTBF terukur, sertifikasi keselamatan atau timing pin analog yang telah diuji. Simulasi functional RTL juga bukan simulasi gate-level dengan anotasi delay.

Laporan asli: [receipt policy](../evidence/current_builds/source_policy.json), [compile policy](../fpga_de10_nano/src_policy/compile.log), [STA policy](../fpga_de10_nano/src_policy/output_files/igor_src_policy.sta.rpt), [receipt planner](../evidence/current_builds/planner.json). Source, report, SOF dan gambar terikat pada manifest rilis; hash file tidak membuktikan image sedang berjalan pada board.

## Reproduksi

Jalankan dari `fpga`:

```powershell
python scripts/run_all_checks.py --suite policy
python scripts/build_quartus.py source_policy
python scripts/capture_visual_evidence.py
python scripts/freeze_release.py --check
```

Capture memerlukan GTKWave terpasang dan PyMuPDF 1.26.5 untuk **gambar laporan**. Instalasi lokal renderer: `python -m pip install --target .runtime/evidence_tools pymupdf==1.26.5`. Capture membaca VCD/CSV hasil simulasi, bukan merekayasa data. Path GTKWave dapat diatur dengan `--gtkwave`.

Setelah perubahan source, `--check` rilis lama memang akan menolak sampai build/pengujian dan freeze baru selesai. Lihat [perbaikan tervalidasi](RTL_IMPROVEMENTS.md) dan [fungsi setiap modul](RTL_MODULE_GUIDE.md).
