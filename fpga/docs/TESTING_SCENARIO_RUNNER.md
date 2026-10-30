# Testing scenarios dari laptop Windows

**Pembaruan 20 Oktober 2026:** shortcut **IGOR - Testing ABC** kini memilih profil LiDAR saja bila FPGA/STM tidak tersedia. Shortcut **IGOR - LiDAR AI Live** mengulang scan dan logging 64 kandidat fitur dengan validity mask. Lihat [panduan LiDAR AI laptop](LIDAR_AI_LAPTOP.md) untuk cara pakai, hasil COM17, driver 3.4 dan batas kualitas pengukuran. Tidak ada perubahan RTL atau protokol FPGA untuk fitur ini.

Dokumen yang dikirim disimpan utuh sebagai `fpga/testing_scenario.md`. Contoh path dan link di dalam dokumen asal mengacu pada root repo/sistem pembuatnya. Sesuai klarifikasi pengguna, **Jetson dan ROS bukan prasyarat untuk runner laptop**. Semua file tambahan berada dalam `fpga/`; source referensi `src/` tidak diubah.

Klik Desktop **IGOR - Testing Scenarios** untuk menjalankan `fpga/scripts/run_testing_scenarios.py`. Tutup logger/terminal JTAG lain sebelum menjalankan suite. Board dan COM12 harus tersedia, Jetson dilepas dari pin UART, dan kabel adapter sesuai panduan mock board. Runner memprogram observer image, mengirim observasi sintetis hanya ke FPGA, dan membaca sensor STM32 secara pasif. Tidak ada perintah motor.

Pembaruan hub USB: runner kini juga menjalankan `laptop_sensor_preflight.py`. Nomor COM LiDAR dan STM ditemukan ulang berdasarkan USB VID/PID, sehingga perpindahan COM13 ke COM14 tidak memerlukan edit script. Bila lebih dari satu adapter dengan identitas yang sama ditemukan, script berhenti dan meminta pemilihan port, bukan menebak.

Shortcut **IGOR - Cek LiDAR dan STM32** mengulang hanya tahap sensor selama 15 detik. Shortcut **IGOR - Testing Scenario Logs** membuka log suite. Log sensor mandiri berada di `fpga/evidence/laptop_sensors/<timestamp>/`; pada suite, log sensor berada di subfolder `sensors/` dalam folder sesi suite.

### Pemeriksaan sensor yang benar-benar dilakukan

- LiDAR: command device-info dan validasi descriptor A1, health status, lalu scan standar 5 byte hanya setelah identitas/health lulus. Minimal lima rotasi dengan ≥80 titik valid dan cakupan sudut >300° diperlukan untuk `scan_ok`. Periode rotasi dicatat terpisah dari kesesuaian lease 150 ms. Tidak ada scan sintetis/fallback.
- STM32: capture RX pada 1.000.000 baud, resinkronisasi AA55, CRC8, hitung tipe/panjang frame, dan cari tipe `0x07` dengan enam float32 finite sesuai `mcu_driver.py`. CRC valid untuk tipe lain tidak dianggap bukti IMU. Norm percepatan dapat menghasilkan petunjuk satuan tetapi tidak menetapkan kontrak firmware/kalibrasi secara otomatis.
- Seluruh command LiDAR, snapshot inventaris port, bytes sensor dan timestamp disimpan lokal. Tidak ada paket chassis/motor yang dikirim pada preflight. `motion_permit` tetap false karena ini alat diagnosis sensor, bukan controller robot.

Protokol LiDAR mengikuti definisi primer [Slamtec SDK: command dan format measurement](https://github.com/Slamtec/rplidar_sdk/blob/master/sdk/include/sl_lidar_cmd.h). Node standar memuat flag sinkronisasi, quality, angle Q6 dan distance Q2; implementasi dikembangkan sebagai parser Python untuk tes laptop. Dua unit test decoder ditambahkan, sehingga jumlah tes software tersedia menjadi 43.

## Pemetaan tujuan dokumen ke laptop

| Tujuan | Implementasi runner | Makna hasil |
|---|---|---|
| A: rectangle 5×4 m dan empat belok kiri | `test_rectangle_route.py`: route dengan pose fixture dan command-estimated route, stale pose/scan/command, penyimpangan dan wheel frame | Membuktikan algoritma pada fixture; tidak mengukur lintasan robot fisik. |
| B: input/output inferensi | Cek model/bank/oracle, simulasi RTL 256 pola, 256 transaksi FPGA fisik via COM12/JTAG, kemudian datalogger bertimestamp | Membuktikan perhitungan Q8.8 pada pola yang diuji. Input bench sintetis, bukan pembacaan LiDAR. |
| C: fault FPGA → STOP dan latch | Dua unit test `test_laptop_scenario_contracts.py` menjalankan handler exception dari source controller dan latch bridge | Membuktikan handler software mengirim empat nol/return dan latch menolak retry. Tidak membuktikan motor fisik berhenti atau stopping distance. |
| UART | Tiga test fabric, tujuh test Q8.8, lalu baseline balasan UART COM12 yang nyata | Fixture dan physical UART diberi status terpisah; tidak ada fallback yang mengubah timeout menjadi PASS. |
| Ethernet | 16 test localhost UDP/fixture | Tidak dianggap bukti koneksi Ethernet board. Memerlukan izin localhost UDP. |
| Security auth | Nama test persis yang disebut dokumen diperiksa keberadaannya | `test/test_security_auth.py` tidak tersedia pada checkout saat implementasi; BLOCKED, bukan PASS 0 tests. |
| Sensor dan gerak fisik | Checklist unresolved dalam summary | LiDAR belum terpasang; pose, IMU units, floor trial dan cabut kabel fisik tidak dapat digantikan oleh fixture. |

Total software yang tersedia saat implementasi: 39 test repository ditambah 2 fault-contract test laptop. Dua test tambahan hanya memanggil source reference dengan fixture; tidak mengubah controller atau firmware. Harness contoh ROS dari dokumen juga diekstrak ke `fpga/scripts/igor_trace_controller.py` untuk referensi bila lingkungan ROS tersedia; runner Windows tidak menjalankannya.

## Log dan status

Setiap klik membuat folder baru `fpga/evidence/testing_scenarios/<timestamp UTC>/`. `session.json` menyimpan commit, platform dan SHA-256 dokumen. Setiap tahap memiliki `.log` sendiri; `summary.json` memuat command, exit code, jumlah unittest, durasi dan status. Folder bukti terperinci dari script RTL/FPGA/datalogger ditunjuk dalam log tahap masing-masing.

- `PASS`: tahap benar-benar selesai dengan exit code sukses; unittest harus menjalankan setidaknya satu test.
- `FAIL`: tahap gagal, termasuk physical UART timeout.
- `BLOCKED` / `NOT_RUN`: prasyarat belum tersedia atau dipilih untuk dilewati.
- Overall hanya `PASS` jika seluruh tahap PASS. Exit 1 = ada FAIL; exit 2 = belum lengkap tanpa FAIL; exit 0 = semua PASS. Ketidaklengkapan tidak disembunyikan.

Pada run awal, empat kelompok software, oracle, RTL, 256 pola board via JTAG dan datalogger lulus. Physical UART return COM12 gagal karena 0 byte balasan. Dua fault-contract test laptop ditambahkan setelah klarifikasi platform dan lulus terpisah. Simulasi/board yang lulus tidak menghapus kegagalan UART atau bukti fisik yang belum tersedia. Hasil terkini selalu dibaca dari folder sesi, bukan dari kalimat historis ini.

CLI:

```powershell
python fpga/scripts/run_testing_scenarios.py
python fpga/scripts/run_testing_scenarios.py --skip-board
```

Jangan menjalankan suite ini bersamaan dengan controller yang memiliki UART atau logger yang memiliki JTAG. `--skip-board` secara eksplisit menghasilkan NOT_RUN untuk tahap board; bukan suite lengkap yang lulus.

## Port USB dan logging waktu

**IGOR - FPGA Datalogger** membuka logger setelah image monitor diprogram. Isi lokasi manual; CSV mencatat waktu UTC/lokal dan output terakhir. **IGOR - Folder Data Logging** membuka folder sesi untuk mengakses CSV/JSONL. Lihat `FPGA_DATALOGGER.md` untuk arti setiap kolom dan keterbatasan snapshot.

- USB-Blaster diperlukan untuk membaca logger JTAG saat ini. Melepasnya menghentikan komunikasi logger; konfigurasi FPGA dapat bertahan jika board tetap mendapat daya eksternal dan tidak direset/reconfigure.
- Adapter USB-to-UART COM12 diperlukan untuk sumber input FPGA dari laptop saat ini. Melepasnya untuk memasang LiDAR menghilangkan jalur input tersebut. Logger JTAG masih bisa membaca hasil lama, tetapi itu tidak berarti ada inferensi LiDAR baru.
- Mengganti adapter dengan LiDAR tidak otomatis menghubungkan data LiDAR ke FPGA. Masih diperlukan aplikasi pembentuk 74 fitur dan jalur input yang aktif.
- Untuk mengaktifkan LiDAR, STM32, UART FPGA dan logger JTAG bersamaan tanpa mengubah RTL terverifikasi, gunakan port tambahan melalui USB hub yang memadai. Belum ada klaim acceptance gerak tanpa sensor tersebut.

Tujuan akhir A/B/C tetap memerlukan LiDAR nyata, sensor/pose sesuai skenario, operator, rekaman gerak dan stopping time/distance. Runner laptop menjalankan bagian yang bisa diverifikasi sekarang dan mempertahankan bagian fisik sebagai unresolved.
