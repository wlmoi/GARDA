# Driver CH340 untuk adapter LiDAR pada laptop

Pengujian laptop dan shortcut terbaru: [LiDAR nyata ke 64 kandidat input AI](LIDAR_AI_LAPTOP.md).

Arsip pengguna `CH34x_Install_Windows_v3_4.zip` diperiksa: SHA-256 `a48b9bf34d1cb175d8e20b0bc6ce3e5264a8724d3bf1b17f1f9e048d7fb49856`. Wrapper EXE diekstrak tanpa dijalankan; katalog driver bertanda tangan Microsoft valid. INF menyatakan 3.4.2014.08. `CH341S64.SYS` memiliki SHA-256 `DE6CA1AE927081AC622F99AB9C77B2127CBB2DF597B4123A4AA2F3DA52CD64D5`, sama dengan paket 3.4 yang sebelumnya diperiksa. Mode `User34` pada `test_ch340_legacy_driver.ps1` memilih paket tersebut. Pada 20 Oktober 2026, COM17 memakai **3.4.2014.8**, INF `oem90.inf`, ProblemCode 0. Bukti lokal: `fpga/evidence/ch340_legacy/User34_*/result.json`.

Driver mengikuti **chip USB adapter yang terdeteksi**, bukan nama sensor saja. Adapter dengan hardware ID `USB\VID_1A86&PID_7523` memakai WCH CH340/CH341 VCP. Jangan memasang driver CP210x untuk hardware ID ini. Kit Slamtec lain dapat memakai CP2102; identifikasi perangkat aktual tetap diperlukan.

## Sumber resmi

- [WCH CH341SER Windows EXE](https://www.wch-ic.com/downloads/CH341SER_EXE.html).
- [WCH CH341SER Windows ZIP](https://www.wch-ic.com/downloads/CH341SER_ZIP.html), paket ID 5 pada situs vendor.
- [Slamtec FAQ](https://wiki.slamtec.com/display/SD/RPLIDAR%2BFAQ): A1M8 memakai 115200 baud; pemeriksaan adapter, kepemilikan port dan suplai USB juga diperlukan.
- [Slamtec official SDK release](https://github.com/Slamtec/rplidar_sdk/releases/tag/release/v1.12.0): tersedia `simple_grabber.exe` untuk pemeriksaan independen.

Paket WCH yang digunakan pada pekerjaan ini: versi paket 4.0, INF `DriverVer=02/11/2026,4.0.2026.02`. Windows menormalisasinya menjadi **4.0.2026.2**. Katalog diverifikasi sebagai `Valid`, dengan penanda tangan Microsoft Windows Hardware Compatibility Publisher. Installer vendor bertanda tangan Nanjing Qinheng Microelectronics Co., Ltd. Paket hanya diambil dari vendor; tidak ada signature enforcement yang dinonaktifkan.

## Instalasi dan bukti

`fpga/scripts/install_official_ch340.ps1` memvalidasi katalog/hardware ID, mengekspor driver sebelumnya dengan `pnputil /export-driver`, lalu menginstal INF melalui `pnputil /add-driver ... /install`. Hak administrator diminta melalui Windows UAC; proses tidak melakukan reboot otomatis.

Paket dan hasil lokal berada di `fpga/evidence/ch340_driver/`:

- `CH341SER.ZIP`, metadata dan extracted package.
- `install_<timestamp>/previous_driver/`: backup driver sebelumnya.
- `install_<timestamp>/install.log` dan `result.json`: transcript dan status saat instalasi.
- `active_verification.json`: pembacaan ulang properti PnP yang aktif.
- `device_restart.log`: hasil restart adapter bila dilakukan.

Gunakan properti langsung `DEVPKEY_Device_DriverVersion`, `DEVPKEY_Device_DriverInfPath` dan `DEVPKEY_Device_ProblemCode` untuk verifikasi. `Win32_PnPSignedDriver` dapat masih menampilkan data cache segera setelah instalasi; log instalasi pertama bisa karena itu menyatakan versi lama sementara. `active_verification.json` menyimpan pemeriksaan ulang dengan metode PnP langsung. Perbandingan versi dilakukan sebagai objek version agar `.02` dan `.2` tidak dianggap berbeda.

```powershell
./fpga/scripts/install_official_ch340.ps1 -VerifyOnly
# Jika diperlukan setelah instalasi, restart hanya adapter CH340:
./fpga/scripts/install_official_ch340.ps1 -RestartOnly
python fpga/scripts/laptop_sensor_preflight.py --seconds 15
```

Script instalasi mengharapkan paket yang sudah diunduh/ekstrak ke folder bukti lokal; binary driver tidak dimasukkan ke source Git. Verifikasi versi driver dan status Windows **tidak otomatis berarti scan sensor berhasil**. `identity_ok`, `health_ok`, dan `scan_ok` diperiksa terpisah. Jangan menganggap exit code 0 dari contoh vendor sebagai scan PASS bila teksnya masih memuat kegagalan scan. Output tool vendor disimpan lokal di `fpga/evidence/slamtec_sdk/`.

Jika driver sudah aktif tetapi komunikasi sensor masih intermittent, lakukan pemutusan daya scanner sepenuhnya dan periksa suplai USB/adapter. Restart perangkat PnP tidak memutus daya 5 V scanner. Klaim pembacaan jarak hanya dibuat setelah measurement scan benar-benar diterima.

## Percobaan legacy 3.4 dari tautan pengguna

Paket yang diminta pengguna berasal dari [arsip Windows CH340 SparkFun](https://cdn.sparkfun.com/assets/learn_tutorials/5/9/7/Windows-CH340-Driver.zip), yang ditautkan dalam [panduan CH340 SparkFun](https://learn.sparkfun.com/tutorials/how-to-install-ch340-drivers/all). INF di dalam paket menyatakan `08/08/2014,3.4.2014.08`; properti PnP Windows menampilkannya sebagai **3.4.2014.8**. Katalog paket memiliki tanda tangan Microsoft Windows Hardware Compatibility Publisher yang valid.

SHA-256 arsip yang diperiksa:

```text
6956D370ECF0BCCB2D054F65CB22397D8D296FEBB9B0AE5C5BE416233E611005
```

Paket CH341SER yang tersedia melalui [tautan Hiwonder](https://docs.hiwonder.com/projects/miniAuto/en/latest/docs/resources_download.html) juga diperiksa. Paket tersebut saat pemeriksaan berisi **3.8.2023.02**, bukan 3.4. Tautan Hiwonder yang ditemukan berasal dari dokumentasi miniAuto; jangan menyebutnya sebagai bukti bahwa setiap bundel JetAuto memakai versi yang sama. Klaim umum tentang bundel historis 3.4 tidak digunakan sebagai pengganti pemeriksaan INF.

`fpga/scripts/test_ch340_legacy_driver.ps1` mendukung pilihan `Legacy34`, `Hiwonder38`, dan `Restore40`. Sebelum beralih, script memvalidasi katalog/hardware ID dan mengekspor driver aktif. Script menggunakan API Microsoft [UpdateDriverForPlugAndPlayDevicesW](https://learn.microsoft.com/en-us/windows/win32/api/newdev/nf-newdev-updatedriverforplugandplaydevicesw) dengan pemilihan versi yang diminta (`INSTALLFLAG_FORCE`); validasi keamanan dan tanda tangan Windows tetap berlaku. Paket baru tidak dihapus dari driver store, sehingga pemulihan tetap tersedia. Tidak ada reboot otomatis.

```powershell
./fpga/scripts/test_ch340_legacy_driver.ps1 -Mode Legacy34
# Pilihan pembanding dari paket Hiwonder yang sudah diverifikasi:
./fpga/scripts/test_ch340_legacy_driver.ps1 -Mode Hiwonder38
# Pemulihan versi WCH 4.0 yang sebelumnya terpasang:
./fpga/scripts/test_ch340_legacy_driver.ps1 -Mode Restore40
```

Paket harus sudah diunduh dan diekstrak di `fpga/evidence/ch340_legacy/` sebagaimana pekerjaan instalasi ini. Setiap percobaan menyimpan `install.log`, `result.json`, dan backup driver di subfolder nama mode/timestamp. `success=true` pada log ini berarti driver yang diminta sudah aktif dan kode masalah PnP nol; **bukan** berarti scan LiDAR lulus. Hasil query/scan disimpan terpisah dalam log sensor dan percobaan vendor.

Pada mode legacy, `install_official_ch340.ps1 -VerifyOnly` tetap khusus mengecek target **4.0**, sehingga dapat melaporkan false saat 3.4 sengaja aktif. Untuk hasil pergantian legacy, lihat `result.json` dari `test_ch340_legacy_driver.ps1` dan properti PnP langsung.
