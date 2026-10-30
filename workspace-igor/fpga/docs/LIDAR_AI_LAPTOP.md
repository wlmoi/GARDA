# LiDAR nyata ke input AI — laptop Windows

**Baseline yang disetujui pengguna, 20 Oktober 2026:** RPLIDAR A1 dengan CH340 driver **3.4.2014.8**, **Express Scan**, **115200 baud 8N1**, deteksi COM otomatis dan preprocessing 64 fitur yang telah diuji. Gunakan konfigurasi ini untuk pengujian berikutnya. Bukti validasi berasal dari commit `85454e2` dan sesi Express di bawah. Standard Scan hanya untuk diagnosis dengan pilihan eksplisit; tidak ada fallback otomatis yang menyembunyikan kegagalan Express. Kalibrasi presisi jarak/yaw dan acceptance robot lengkap tetap merupakan pengujian terpisah.

## Shortcut dan pemakaian

| Desktop shortcut | Fungsi |
|---|---|
| **IGOR - LiDAR AI Live** | Deteksi CH340, scan nyata, nilai konsol setiap sekitar 1 detik; ulang sesi 30 detik sampai Ctrl+C. |
| **IGOR - LiDAR AI Logs** | Buka log scan dan fitur. |
| **IGOR - Testing ABC** | Tes A/B/C laptop; profil LiDAR saja ketika adapter FPGA/STM tidak tersedia. |

USB LiDAR langsung ke laptop, daya scanner aktif. Tutup logger/aplikasi lain yang memiliki port serial sebelum membuka shortcut lain. COM17 ditemukan otomatis dari CH340 `1A86:7523`; nomor COM boleh berubah. Bila ada lebih dari satu CH340, pilih eksplisit:

```powershell
& "$env:LOCALAPPDATA/Programs/Python/Python311/python.exe" fpga/scripts/lidar_ai_reader.py --port COM17 --repeat --location "Robot - ruang pengujian" --yaw-deg 0
& "$env:LOCALAPPDATA/Programs/Python/Python311/python.exe" fpga/scripts/run_laptop_abc.py --lidar-port COM17
pwsh -NoProfile -File fpga/scripts/install_lidar_abc_shortcuts.ps1
```

Python 3.11 lokal, numpy dan pyserial tersedia. Launcher memilih Python tersebut, kemudian `python` PATH sebagai fallback. Tidak ada reinstall driver saat shortcut diklik.

## Transformasi dan validitas

`COM → identitas/health → capsule Express 84 byte + XOR → 32 node → rotasi lengkap → grid baru 360 bin → 64 beam depan → normalisasi /3,50 → Q8.8`.

Logger baru default **Express Scan**, setelah firmware COM17 mengembalikan descriptor `a5 5a 54 00 00 40 82`. Setiap capsule diverifikasi header, panjang dan XOR; sudut sampel memerlukan capsule berikutnya. Koreksi sudut Q3 dan interpolasi mengikuti [algoritma primer SDK Slamtec](https://github.com/Slamtec/rplidar_sdk/blob/master/sdk/src/dataunpacker/unpacker/handler_capsules.cpp). Capsule checksum rusak dibuang dan kontinuitas cache dibatalkan. Express tidak memiliki quality fisik per sampel: field quality berasal dari validitas jarak nonzero sesuai SDK, ditandai `quality_source` di node JSONL. Standard 5 byte tetap tersedia dengan `--scan-mode standard`; Express juga menjadi default preflight dan shortcut pemeriksaan sensor.

Parser mengikuti [definisi resmi Slamtec](https://github.com/Slamtec/rplidar_sdk/blob/master/sdk/include/sl_lidar_cmd.h): distance Q2 /4000 meter, angle Q6 /64 derajat. Quality nol, nonfinite dan jarak di luar 0,15–12 m tidak menjadi pengukuran grid. Sudut dibulatkan ke derajat; sampel valid terakhir pada bin menang. Grid dibuat baru setiap rotasi agar data lama tidak tertahan.

Interpolasi sama dengan `src/igor_navigation/igor_navigation/drivers/lidar_subsampler.py`, metode `subsample_from_laserscan`: wrap [-π,π), urutkan, 64 target inklusif [-90°,+90°], clip 0,15–3,50 m, float32. Controller reference membagi 3,50 sehingga domain [0,1]. Kandidat Q8.8 = `round(normalized*256)`, rentang 0–256. MAE dan error maksimum encoding input dicatat; batas pembulatan absolut ≤1/512 normalized. Ini bukan MAE output neural network.

Bin tanpa return berisi kandidat 3,50 m sesuai kebijakan fallback reference. **Fallback bukan bukti ruang kosong.** `measured_support_mask[64]` true hanya bila kedua tetangga interpolasi diukur pada rotasi ini, atau target tepat pada bin terukur. Mask konservatif; hanya satu tetangga nyata belum dihitung didukung penuh. Unit test membandingkan interpolasi dengan source reference pada grid identik. Freshness dan mask tambahan hanya berada di folder FPGA.

`--yaw-deg 0` memakai nol sudut sensor; orientasi lama menurut operator belum merupakan kalibrasi yaw presisi. Tidak menyalin offset 180° dari sistem lain secara otomatis.

64 kandidat belum observasi 74 fitur lengkap: acceleration 3, gyro 3, nominal velocity 3 dan heading 1 tidak tersedia saat hanya LiDAR terhubung. Logger tidak mengirim input ke FPGA, tidak memprogram board dan tidak menggerakkan chassis. `complete_live_observation=false`, `motion_permit=false`, `navigation_ready=false` dicatat.

## Log dan arti PASS

Setiap sesi: `fpga/evidence/lidar_ai/<UTC>/` berisi:

- `session.json`: lokasi operator, yaw dan inventaris port.
- `lidar_stream.bin`: bytes scan asli lokal.
- `lidar_scans.jsonl`: seluruh titik/rotasi, UTC, interval host.
- `lidar_points.csv`: UTC, rotasi, sudut, jarak, quality, validitas.
- `ai_features.jsonl`: UTC/lokal/lokasi, seluruh 64 jarak/normalized/Q8.8, support mask, galat encoding dan fitur yang belum ada.
- `summary.json`: status komunikasi, format fitur dan kualitas terpisah.

Konsol menampilkan RX, interval, minimum jarak, jumlah bin/fitur terukur, delapan Q8.8 pertama; seluruh 64 ada di JSONL. Lokasi adalah label operator, bukan GPS/pose. Timestamp laptop dan interval penerimaan bukan timestamp akuisisi sensor atau latensi inferensi. Ctrl+C mempertahankan rotasi yang sudah ditulis; sesi yang terputus bisa belum memiliki summary final.

`communication_ok`: identitas + health + ≥5 rotasi dengan ≥80 node dan span >300°. `feature_contract_ok`: bentuk/domain angka. Exit 0 alat LiDAR hanya meluluskan dua aspek ini. `scan_ok` terpisah: ≥5 rotasi dengan ≥80 titik jarak valid dan span >300°. Ambang 80 adalah **heuristik diagnosis proyek**, bukan spesifikasi vendor atau syarat dokumen asli. Kualitas belum terpenuhi ditandai BLOCKED pada suite A/B/C; ambang tidak diturunkan demi PASS.

## Pengujian nyata 20 Oktober 2026

**Hasil terbaru Express**, sesi UTC `20261019T184357066947Z`: 30 detik, **384 rotasi**, **384 good scans**, **102–120 titik valid/rotasi**, **0 byte resinkronisasi**, maksimum interval host **94 ms**. Identitas, health, transport, quality gate proyek dan format fitur semuanya lulus. Setiap rotasi menghasilkan 64 kandidat; **18–33 fitur** didukung penuh oleh mask dua bin terukur. Mask tetap disimpan; quality gate lulus tidak berarti seluruh 64 arah mendapat return nyata atau acceptance gerak lengkap lulus. Lima test Express mencakup checksum/truncation, jarak/sudut, koreksi Q3, wrap dan reset. Total unit test tersedia kini **53**.

Perbandingan berikut adalah baseline standard sebelum Express dipilih, bukan hasil final logger:

Driver pengguna berhasil diikat ke COM17: **3.4.2014.8**, INF `oem90.inf`, ProblemCode 0, katalog bertanda tangan valid. [Rincian driver](LIDAR_DRIVER.md).

Sesi UTC `20261019T183807511178Z`, setara 20 Oktober WIB; operator menyatakan target datar sekitar 1 m di depan robot:

| Parameter | Hasil / sumber lokal |
|---|---|
| Port | COM17, 115200 8N1; summary |
| Identitas / health | Lulus / OK; descriptor diperiksa |
| Durasi / rotasi | 30 detik / **382**; JSONL dan summary |
| Byte alignment dibuang | **0**; summary |
| Titik jarak valid per rotasi | **37–52**; summary |
| Interval host maksimum | **79 ms**; summary |
| Fitur | **382 × 64** kandidat sesuai kontrak numerik |
| Fitur didukung dua bin nyata | **0–5 dari 64** per rotasi; mask JSONL |
| Kandidat benda 0,85–1,15 m pada sektor 0–30° | **113 sampel**, median **0,95875 m**, median sudut **8,8125°**; filter titik JSONL |
| Kualitas navigasi | Belum disahkan; quality gate belum terpenuhi |

Pencarian sektor/rentang target dipilih setelah instruksi operator: bukan kalibrasi presisi atau pembuktian identitas objek. Jarak operator sekitar 1 m tidak disurvei; selisih tidak menjadi spesifikasi akurasi sensor. Uji target sekitar 15 cm sebelumnya menemukan kandidat median 0,237 m dan belum mengidentifikasi target dengan pasti.

Query sample-rate resmi menjawab `a5 5a 04 00 00 00 15 fc 01 fe 00`: standard **508 µs/sample**, express **254 µs/sample**. Query PWM accessory tidak mendapat respons; tidak ada perubahan kecepatan motor. Rotasi teramati sekitar 12,7–13,2 Hz memerlukan investigasi: [A1 resmi hingga 10 Hz](https://www.slamtec.com/en/lidar/a1/), [typical 5,5 Hz; rentang 0,15–12 m](https://www.slamtec.com/en/lidar/a1spec). Penyebab sparse return belum ditetapkan; bidang pandang, mounting, permukaan dan pencahayaan juga perlu diperiksa.

## Cakupan A/B/C

[testing_scenario.md](../testing_scenario.md) asli dipertahankan. Jika adapter FPGA Prolific `067B:2303` dan STM `1A86:55D4` tersedia, shortcut memanggil runner hardware yang sudah ada; jika tidak, profil LiDAR saja. Perubahan ini tidak mengedit RTL, pin planning, SOF atau protokol FPGA. Profil hardware lama dapat memprogram observer sesuai perilaku runner sebelumnya; tutup controller pemilik UART/JTAG dahulu.

| Aspek | Tes laptop otomatis | Acceptance fisik |
|---|---|---|
| A | 13 tes route/freshness dengan fixture | Rectangle 5×4 m, pose independen dan toleransi disepakati. |
| B | LiDAR nyata, kontrak fitur, oracle dan RTL 256 pola; tes board lama bila tersedia | Trace observasi 74 fitur nyata dan hasil inferensi sistem lengkap. |
| C | Handler fault dan latch dengan fixture | Cabut link terawasi, empat wheel zero, stopping time/distance, reconnect tanpa resume. |

53 unit test tersedia (termasuk 5 fitur LiDAR dan 5 decoder Express baru) terpisah dari tes RTL dan hardware. Nama `test/test_security_auth.py` dari dokumen tidak tersedia dan tetap BLOCKED. Tanpa FPGA/STM, tahap terkait NOT_RUN/BLOCKED; tidak ada gerakan otomatis. Exit suite 2 = belum lengkap, 1 = ada kegagalan tes, 0 = seluruh persyaratan PASS. Log suite di `fpga/evidence/testing_scenarios/<UTC>/`. Raw capture/identitas perangkat disimpan lokal dan tidak dipush.

Suite aktual melalui target shortcut pada sesi UTC `20261019T184544294342Z`: **53 unit test**, oracle dan **256 pola RTL / 768 output Q8.8** lulus; **11 tahap PASS, 0 FAIL, 10 unresolved**. Tiga sesi ulang Express terpisah menghasilkan **356/356 good scans**, seluruhnya tanpa byte resinkronisasi. Hasil keseluruhan **INCOMPLETE** karena FPGA/STM dan acceptance gerak fisik belum tersedia; bukti ada di folder sesi lokal.
