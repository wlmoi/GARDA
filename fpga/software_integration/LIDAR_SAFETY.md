# LiDAR produksi: freshness dan fail-closed

Implementasi yang diubah berada di
`software_integration/src/igor_bringup/igor_bringup/rplidar_driver_node.py`.
`../src` di root workspace merupakan referensi software asli. Gunakan overlay
ini pada workspace ROS 2 untuk integrasi hardware; jangan menganggap driver
referensi telah memperoleh perbaikan ini.

Driver produksi tidak beralih ke sensor sintetis. `mock=True` harus diminta
secara eksplisit. Tidak ada pyserial, port hilang, timeout descriptor, atau
descriptor salah menggagalkan startup. Descriptor standard-scan yang diterima
adalah `A5 5A 05 00 00 40 81`: ukuran measurement lima byte, continuous mode,
tipe `0x81`. Kontrak tersebut berasal dari
[header protokol Slamtec](https://github.com/Slamtec/rplidar_sdk/blob/master/sdk/include/sl_lidar_protocol.h)
dan [header measurement Slamtec](https://github.com/Slamtec/rplidar_sdk/blob/master/sdk/include/sl_lidar_cmd.h).

Satu scan dibentuk dari measurement di antara dua marker awal putaran.
Marker pertama memulai akuisisi dan tidak mempublikasikan scan kosong.
Measurement marker berikutnya menjadi bagian putaran berikutnya. Buffer
dibersihkan setiap putaran; bin lama tidak pernah dipakai kembali. Serial
read yang terfragmentasi ditampung, dan paket rusak ditangani dengan
resinkronisasi satu byte.

Secara default dibutuhkan minimal **180 bin sudut berbeda** dengan quality
positif dan jarak 0,15–12 m; pengulangan bin tidak menambah coverage. Jika
beberapa pengukuran masuk satu bin, yang dipakai adalah jarak terdekat.
Bin tanpa measurement valid diisi **0,15 m secara konservatif**. NaN/Inf atau
isian free-space 3,5 m tidak dipakai karena subsampler software referensi
menerjemahkan NaN/Inf menjadi jalur bebas. Threshold 180 adalah kebijakan
integrasi konservatif dan dapat diatur lewat parameter `min_scan_bins`,
bukan jaminan spesifikasi sampling A1. Kehilangan coverage frontal dapat
menghentikan robot walaupun beberapa area lain terukur bebas.

`max_scan_age_sec=0.25` membatasi umur sejak marker ray pertama berdasarkan
`time.monotonic()`. Durasi putaran juga harus positif dan tidak melebihi
batas tersebut. Stamp ROS dicatat ketika akuisisi dimulai dan disimpan saat
putaran selesai. Timer publisher **tidak mengganti stamp dengan waktu sekarang**.
Setiap nomor scan hanya diterbitkan sekali; data default, belum lengkap,
beku, telah diterbitkan, atau terlalu tua tidak menghasilkan publikasi.
Error serial menghentikan thread dan membatalkan scan yang belum dikirim.

Timer publikasi 10 Hz dan batas 0,25 s harus diuji terhadap kecepatan putaran
dan kondisi A1 fisik. Putaran lambat ditambah antrian timer dapat melampaui
budget, sehingga scan sengaja dibuang dan controller harus berhenti melalui
timeout LiDAR. Tidak ada klaim telah mengukur kecepatan/coverage sensor fisik.
Parameter ini tidak boleh diperlonggar tanpa menilai ulang stopping distance.

Metadata 360 bin memakai `angle_increment=2π/360` dan
`angle_max=359*angle_increment`, yaitu sudut ray terakhir. Durasi scan berasal
dari dua marker akuisisi. Controller overlay menggunakan metadata sudut serta
freshness monotonic callback untuk menentukan kapan motor harus dihentikan.
Freshness driver dan timeout controller sama-sama diperlukan untuk sensor
yang membeku atau terlepas.

Dari direktori `fpga`:

```powershell
python verification/run_lidar_regression.py
```

Regresi 16 test menggunakan driver produksi yang sebenarnya, dengan fixture
ROS/serial dan NumPy. Cakupannya: tidak ada auto-mock; semua tujuh byte
descriptor yang salah dan descriptor terpotong; descriptor terfragmentasi;
boot tanpa scan; coverage parsial/duplikat; range/quality/paket invalid;
putaran terlalu lama atau waktu mundur; stamp akuisisi; satu publikasi per
scan; tidak membawa bin putaran lama; sensor membeku; putus serial; serta
stream measurement terfragmentasi dengan noise dan recovery. Hasil dan
SHA-256 driver/runner ditulis ke `evidence/current_lidar/results.json`.
Ini pengujian software dengan fixture, bukan bukti HIL atau board fisik.
