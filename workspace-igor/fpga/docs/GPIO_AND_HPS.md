# GPIO sekarang, konfigurasi FPGA tanpa JTAG kemudian

**GPIO JP1 sudah digunakan untuk komunikasi UART saat RTL berjalan.** Agar
RTL mulai berjalan setelah power-on, FPGA tetap memerlukan konfigurasi dari
JTAG, perangkat konfigurasi, atau HPS. Manual DE10-Nano menjelaskan sumber
konfigurasi dan SW10 pada halaman 11–14.
[Sumber: manual Terasic](https://www.mouser.com/datasheet/2/598/DE10_Nano_User_manual_a_b-1108056.pdf).

| Kebutuhan | Metode | Kesiapan paket |
|---|---|---|
| Kirim observasi/perintah dan baca hasil | UART melalui GPIO JP1 | Sudah ada: RX pin 1/V12, TX pin 2/E8, GND pin 12/30, TTL 3,3 V |
| Konfigurasi awal tanpa kabel JTAG | HPS membaca RBF dari microSD melalui bootloader, atau loader Linux yang sesuai | Memerlukan identifikasi image HPS, bootloader, kernel dan MSEL aktual |
| Kirim bitstream ke UART/GPIO JP1 pada FPGA kosong | Memerlukan penerima/loader yang sudah hidup dan jalur konfigurasi yang didukung | Parser UART RTL saat ini memproses data aplikasi; tidak memuat bitstream |
| SPI/I2C atau bus paralel pada JP1 | Tambah RTL, kontrak protokol, pin planning dan verifikasi | Belum diimplementasikan pada kedua top saat ini |
| Host memakai GPIO untuk bit-bang JTAG | Tetap protokol JTAG pada konektor JTAG khusus | Bukan alternatif non-JTAG; wiring/adaptor harus diverifikasi terpisah |

Untuk UART, TX host masuk RX FPGA dan sebaliknya. Gunakan baud **921600 8N1**
untuk `source_policy`, atau **115200 8N1** untuk `planner`. Host GPIO harus
menyediakan UART yang memenuhi timing; bit-bang UART kecepatan tinggi dari
software biasa belum diverifikasi. Detail lengkap ada pada
[BOARD_PROGRAMMING.md](BOARD_PROGRAMMING.md). Port top saat ini mengekspos UART,
tombol, LED, dan clock; status gate planner dibaca lewat UART, bukan pin motor
eksternal yang sudah dipetakan.

## Jalur tanpa JTAG: HPS dan RBF

Terasic mendokumentasikan bootloader SD yang memuat `soc_system.rbf` pada
contoh board tertentu, halaman 64–67. Nama file dan lokasi itu milik contoh
tersebut; periksa boot script image aktual sebelum mengganti apa pun.
[Manual Terasic](https://www.mouser.com/datasheet/2/598/DE10_Nano_User_manual_a_b-1108056.pdf).

Getting Started Terasic menetapkan **SW10/MSEL[4:0]=01010** sebagai mode
**FPPx32** untuk konfigurasi dari HPS/SD pada setup yang dijelaskan. SW10
berbeda dari slide switch SW0–SW3 untuk aplikasi. Cocokkan orientasi ON/OFF
dengan gambar board dan image boot; jangan menyamakan angka biner dengan
urutan kiri/kanan tanpa membaca label.
[Getting Started, bagian 2.2](https://www.terasic.com.tw/attachment/archive/1046/Getting_Started_Guide.pdf).

RBF dapat disiapkan lokal dari SOF terverifikasi. Contoh berikut **hanya
mengonversi file di komputer**, tanpa mengakses board atau microSD:

```powershell
python .\fpga\scripts\freeze_release.py --check
New-Item -ItemType Directory -Path .\fpga\bitstreams\hps_candidate -Force
& 'D:\Quartus-Program\quartus\bin64\quartus_cpf.exe' -c -m FPP .\fpga\bitstreams\igor_src_policy.sof .\fpga\bitstreams\hps_candidate\igor_src_policy.rbf
```

Untuk planner, pilih `igor_planner.sof` dan nama keluaran yang sesuai.
Sintaks konversi diperiksa pada Quartus 25.1 lokal melalui
`quartus_cpf --help=rbf` dan `--help=configuration_mode`. Compression dan opsi
konfigurasi harus cocok dengan loader/MSEL aktual. `--hps` pada CPF adalah
opsi pemisahan peripheral/core; opsi itu tidak otomatis membuat sistem HPS
atau image Linux. RBF hasil konversi saja belum merupakan paket boot HPS.

## Pemeriksaan Linux HPS sebelum memilih loader

Image Linux board belum diidentifikasi atau diuji dalam sesi ini. Setelah
tersedia console HPS, kumpulkan informasi read-only berikut:

```sh
uname -a
cat /proc/device-tree/model
ls -l /sys/class/fpga_manager/
ls -l /sys/class/fpga_bridge/
ls -l /sys/kernel/config/device-tree/overlays/
```

Path yang tidak ada dicatat sebagai hasil diagnosis. Bila terdapat
`/sys/class/fpga_manager/fpga0/`, baca file `name` dan `state` di dalamnya.
Kernel mendefinisikan FPGA manager, bridge dan region; API pemrograman dan
device-tree overlay harus disesuaikan dengan driver/image.
[Linux FPGA Manager](https://docs.kernel.org/driver-api/fpga/fpga-mgr.html),
[Linux FPGA Region](https://docs.kernel.org/driver-api/fpga/fpga-region.html).

Paket ini tidak mengasumsikan ada file sysfs `firmware` yang writable pada
semua kernel. Belum disediakan command untuk mengganti konfigurasi live,
menulis SD atau mengubah bootloader. Langkah berikutnya setelah image dikenal:
pilih prosedur loader image tersebut, cocokkan bridges/reset/clock dan device
tree dengan desain, backup boot image, lalu rekam hash RBF, log konfigurasi
dan respons UART setelah boot. Status manager `operating` saja belum
membuktikan fungsi IGOR; ulangi verifikasi protokol dan acceptance safety
project terkait. Implementasi HPS dan uji boot ini tetap **belum diverifikasi
fisik**.
