# UART Q8.8 ? validasi integer

FPGA saat ini menggunakan 9600 baud, 8N1, 50 MHz.
Signed Q8.8 memakai 16 bit two's complement dengan 8 bit pecahan:
raw integer / 256 = nilai desimal. Contoh -46 = 0xFFD2 = -0.1796875.
Hex16 menampilkan word; UART mengirim little-endian (0xFFD2 -> d2 ff).

Domain input RTL: 64 LiDAR raw 0..256, lalu 10 fitur raw -256..256.
Domain output: tiga residual raw -256..256. Paket tetap TX153/RX11 byte CRC8.
Nilai domain ini lebih sempit daripada seluruh rentang representasi signed16.
Baud harus sesuai image FPGA; pilih 921600 hanya jika image lama diprogram.

## 1. Validasi offline, tidak membuka UART

Dari root igor_ws:

```bash
python3 src/igor_pipeline/scripts/uart_validate_q88.py
```

Expected: PASS offline 16 kasus. Data expected berasal dari model integer
independen, disertai hash model. Script mengecek tipe integer, domain,
endianness, panjang paket, CRC8 dan expected RX. Ini bukan uji hardware.

## 2. Test 50 frame input tetap

```bash
python3 src/igor_pipeline/scripts/uart_test.py --baud 9600 --iter 50 --jsonl uart_fixed.jsonl
```

Default input: [205] sebanyak 64, lalu [0] sebanyak 10. Tidak memakai konversi
float dalam jalur pengiriman. Default expected: [-46, 60, 34].

```text
PASS | Q8.8=[-46, 60, 34] | HEX16=['0xFFD2', '0x003C', '0x0022'] | decimal=[-0.1796875, 0.234375, 0.1328125]
Frames sent: 50 | received: 50 | dropped: 0
Validation passed: 50/50
```

Gunakan --dump-hex untuk menampilkan paket TX/RX lengkap.
Untuk input sendiri, --obs-q88 input.json harus berupa array 74 integer.
Tambahkan --expected-q88=-46,60,34 jika ingin membandingkan numerik.
Input custom tanpa expected hanya memvalidasi transport; bukan kebenaran model.

## 3. Validasi hardware 16 pola, ulang 3 kali (48 transaksi)

Lepas KEY1 dan tekan/lepas KEY0 sebelum test. Gunakan satu proses UART.

```bash
python3 src/igor_pipeline/scripts/uart_validate_hardware_q88.py --baud 9600 --repeat 3 --output uart_matrix.jsonl
```

Expected: Q8.8 hardware: 48/48 PASS. Nol, batas domain, alternating,
ramp dan random deterministik dibandingkan secara exact dengan oracle.
Tidak ada fallback mock. Timeout, CRC salah, atau beda satu LSB => FAIL.
9600 baud memerlukan minimal sekitar 8.2 detik untuk 48 transaksi.

## 4. Periksa ulang log dengan oracle

```bash
python3 src/igor_pipeline/scripts/uart_validate_q88.py --capture uart_fixed.jsonl --expected-frames 50
python3 src/igor_pipeline/scripts/uart_validate_q88.py --capture uart_matrix.jsonl --expected-frames 48
```

Validator mendecode ulang raw RX dan CRC, lalu membandingkan hasilnya dengan
fixture berdasarkan input; tidak sekadar mempercayai label PASS dalam log.
Log kosong, frame duplikat/hilang, mismatch atau CRC salah => exit 1.
Capture input custom di luar 16 fixture ditolak: generate oracle baru dahulu.
File JSONL tidak ditimpa; pakai nama baru setiap run.

## Memperbarui oracle (di workspace lengkap)

`python tools/generate_uart_q88_vectors.py` membuat 16 fixture dari model JSON
menggunakan perhitungan integer independen. Regenerasi bila model berubah,
lalu cocokkan juga dengan bobot image FPGA yang diprogram.
`python tools/package_uart_q88.py` memperbarui installer dan ZIP.
Perubahan script ini tidak mengubah RTL atau memerlukan programming FPGA.
