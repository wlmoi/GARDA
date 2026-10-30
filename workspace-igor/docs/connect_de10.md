# Satu script koneksi Jetson?DE10

## Pilihan termudah: satu file mandiri

Salin `tools/de10_connect.py` ke folder mana saja di **Jetson**, lalu jalankan:

```bash
python3 de10_connect.py
```

File ini sudah membawa script koneksi, codec, gateway dan fixture Q8.8.
Asset diverifikasi checksum lalu disiapkan di `.igor_de10_connect/<versi>/`
di sebelah file; tidak memerlukan clone repo lengkap di Jetson atau HPS.
Log gateway versi mandiri berada di folder cache itu dan lokasinya dicetak.
Gunakan folder yang dapat ditulis oleh akun Jetson.

## Alternatif: dari workspace lengkap

Jalankan di **Jetson**, dari workspace yang sudah berisi pembaruan Ethernet:

```bash
cd ~/igor_ws
python3 tools/connect_de10.py
```

Default menggunakan akun HPS `fpga`, interface Jetson `enP8p1s0` bila tersedia,
IP Jetson 192.168.50.1/24 dan HPS 192.168.50.2/24. Akun HPS harus benar-benar
ada. Jika akun berbeda atau console perlu dipilih:

```bash
python3 tools/connect_de10.py --user root --console /dev/ttyUSB0
```

Gunakan `root` hanya bila itu akun Linux HPS yang memang tersedia dan diizinkan
login SSH; script tidak membuat akun/password atau mengubah kebijakan SSH.
Nama /dev/ttyUSB0 di contoh harus diganti sesuai perangkat console DE10 pada Jetson.

## Yang dilakukan otomatis

1. Inventaris interface dan carrier Jetson; konfigurasi IP sementara tanpa
   menghapus IP/default route lain. Verifikasi mesin lokal Jetson sebelum mutasi.
2. Jika carrier aktif tetapi SSH alamat default belum terjangkau, periksa
   neighbor IPv4 yang sudah dikenal pada interface kabel dan subnet /24 yang
   sama. Hanya satu kandidat SSH yang dipilih; identitasnya tetap diperiksa
   setelah login. Tidak memindai Wi-Fi/subnet penuh atau menebak IP di subnet
   lain. Jika belum terjangkau, pilih FT232R console
   yang unik, atau gunakan --console. Console selalu 115200 baud.
3. Login HPS melalui prompt biasa. Identitas ARMv7/SoCFPGA diverifikasi sebelum
   mengubah IP; kernel Tegra/aarch64 Jetson tidak diterima sebagai DE10.
4. Aktifkan interface dan IP HPS, lalu mulai service SSH/sshd/dropbear yang sudah
   terpasang. Password sudo HPS diminta bila diperlukan.
5. Tunggu carrier, ping, autentikasi SSH dan verifikasi identitas HPS sekali lagi.
6. Deploy dua file gateway/protokol dari workspace ke `igor_ws` pada HOME akun
   HPS. Memerlukan tar, Python 3.8+ dan akses tulis ke folder itu.
7. Jalankan gateway pada sesi SSH, lalu uji 10 transaksi UDP secara otomatis.
8. Tampilkan status terhubung. Terminal tetap terbuka untuk menjaga gateway;
   Ctrl+C mengakhiri sesi/gateway yang dijalankan script. IP sementara tetap ada.

Default **NETWORK ONLY** memakai backend mock berstatus 6. Keberhasilan jaringan
belum berarti inferensi FPGA berhasil. Script tidak menyimpan password, tidak
mengabaikan verifikasi fingerprint SSH, tidak memprogram FPGA, dan tidak
mematikan server lain yang sudah menggunakan UDP 8080. Hentikan gateway/service
lama lebih dahulu bila ingin script ini mengelola sesi baru.

## Uji FPGA asli, masih satu perintah

Setelah link/network-only berfungsi, hentikan sesi dengan Ctrl+C. Pastikan image
UART benar, KEY1 dilepas, KEY0 sudah di-reset, dan USB-UART adapter lokal HPS
tersambung ke JP1. Kemudian:

```bash
python3 tools/connect_de10.py --hardware --baud 9600 --fpga-serial /dev/ttyUSB0
```

Jika terjadi timeout/error UART, lepas KEY1 dan reset KEY0 sebelum mencoba
ulang hardware. Script tidak dapat menekan tombol reset FPGA secara otomatis.

`--console` adalah port **di Jetson** untuk terminal Linux HPS.
`--fpga-serial` adalah port **di HPS DE10** untuk adapter lokal menuju FPGA.
Keduanya bukan link/perangkat yang sama, walaupun nama ttyUSB0 bisa kebetulan sama.
Jika adapter USB di HPS tepat satu, --fpga-serial dapat dihilangkan. Pemilihan
ambigu dihentikan, tidak ditebak. Mode hardware membutuhkan pyserial di HPS.
Expected: FPGA PASS 10/10, default input raw Q8.8 menghasilkan [-46,60,34].

## Syarat fisik dan software

- Kabel RJ45 Jetson?DE10 terpasang dan perangkat mendapat daya.
- MicroSD DE10 berisi Linux/BSP yang benar dan Linux HPS benar-benar boot.
- Untuk bootstrap pertama: USB-UART **console** DE10 disambungkan ke Jetson.
  USB-Blaster ke PC boleh tetap terpasang, tetapi bukan console Linux.
- Jetson: Python 3, iproute2, ping, OpenSSH client; pyserial untuk USB console.
- HPS: iproute2, SSH server/service dan akun login yang sudah disiapkan, tar,
  Python 3.8+. Gateway hardware juga memerlukan pyserial dan izin port serial.
- Akun harus mempunyai izin sudo/root untuk mengubah IP. Script meminta
  autentikasi normal, tidak melewati password atau memasang paket OS otomatis.

Jika masih `carrier=0` setelah bootstrap HPS, script berhenti dengan petunjuk
kabel/PHY/boot. Software tidak bisa memperbaiki kabel lepas, SD tanpa Linux,
atau layanan SSH/Python yang belum terpasang. Jangan memaksa fixed speed/duplex
sebagai pengganti perbaikan link fisik.

## Opsi diagnostik

```bash
# Hanya membaca interface; tanpa sudo, mutasi IP atau membuka console
python3 tools/connect_de10.py --check-only

# Pilih interface jika deteksi otomatis ambigu
python3 tools/connect_de10.py --interface enP8p1s0 --hps-interface eth0 --console /dev/ttyUSB0

# Paksa bootstrap console bila IP HPS salah, meskipun carrier sudah aktif
python3 tools/connect_de10.py --bootstrap-console --console /dev/ttyUSB0
```

Log gateway disimpan sebagai `igor_connect_<timestamp>_<suffix>.log` di root
workspace Jetson. Untuk log inferensi lengkap dan konfigurasi persisten, lihat
[eth_direction.md](../eth_direction.md). Script ini memakai konfigurasi IP dan
SSH gateway per sesi; tidak memasang service auto-boot.

## Validasi

`python -m unittest discover -s test -p test_connect_de10.py` memeriksa pemilihan
interface/console, penolakan identitas Jetson sebagai HPS, parsing marker serial,
password sudo, penanganan kegagalan dan mode check-only memakai fixture.
Versi mandiri juga diuji dari folder kosong tanpa repository, termasuk
pemasangan asset ulang dengan checksum yang sama. Regenerasi file mandiri
dengan `python tools/package_de10_connect.py` bila asset sumber berubah.
Ini pengujian software; bootstrap/login dan link fisik pada kedua board tetap
harus dicoba oleh operator. Tidak ada klaim perangkat fisik sudah terhubung.

## Jika carrier=1 tetapi console tidak terdeteksi

Link Ethernet sudah terbentuk; itu belum membuktikan IP HPS, boot Linux atau
SSH siap. Script terbaru melaporkan tahap tersebut secara terpisah. Periksa:

```bash
ip neigh show dev enP8p1s0
lsusb
sudo dmesg -w
```

Saat dmesg berjalan, colokkan port USB-UART console DE10 ke Jetson memakai
kabel data dan lihat apakah driver membuat ttyUSB/ttyACM. Jangan menggunakan
port USB-Blaster sebagai console. Jika tidak ada serial device sama sekali,
--console /dev/ttyUSB0 tidak akan membuat perangkat itu muncul. Periksa
konektor, kabel data dan pesan USB/driver terlebih dahulu.

Jika sudah mengetahui IP HPS pada subnet lain, berikan kedua alamat yang
sesuai dengan --hps-ip dan --jetson-ip. Jangan menganggap alamat ARP dari
Wi-Fi sebagai alamat DE10 pada kabel. Tanpa alamat HPS yang dapat dijangkau
atau console yang bekerja, script tidak dapat memasang konfigurasi pada HPS.

## Perbaikan otomatis driver USB console

Versi terbaru membaca VID/PID dari sysfs USB. Jika FT232R 0403:6001 terlihat
tetapi belum ada ttyUSB, script meminta sudo untuk `modprobe ftdi_sio`, menunggu
udev dan memeriksa port lagi. Tidak melepas driver lain atau membuat device node.
Jika hanya USB-Blaster/JTAG yang terlihat, script menjelaskan bahwa connector
tersebut bukan console. Jika FT232R tidak terlihat pada bus USB, memuat driver
secara acak tidak akan menyelesaikan enumerasi USB.

Konektor console DE10 harus masuk ke USB HOST **Jetson** agar terlihat pada
/dev Jetson. Jika console terhubung ke PC, buka console dari PC; Jetson tidak
akan melihat perangkat USB milik PC melalui kabel Ethernet. Port UART GPIO
Jetson seperti ttyTHS1 bukan pengganti USB-UART console tersebut.
