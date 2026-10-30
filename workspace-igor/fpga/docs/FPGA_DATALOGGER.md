# FPGA → laptop datalogger

Setelah board diprogram dengan project `fpga/experiments/jp1_1_2_monitor/igor_jp7_monitor.qpf`, klik Desktop **IGOR - FPGA Datalogger**. Isi lokasi, misalnya `Lab ITB / meja A`, lalu Enter. Ctrl+C menghentikan logger dan menyimpan ringkasan. Launcher: `fpga/bitstreams/OPEN_FPGA_DATALOGGER.bat`. Shortcut dapat dibuat ulang dengan `fpga/scripts/install_datalogger_shortcut.ps1`.

Gunakan USB-Blaster yang sama dengan programming; tutup JTAG terminal atau aplikasi pengujian lain yang sedang memakai interface JTAG. Logger tidak membuka COM12, tidak memprogram board, tidak mereset core, tidak mengganti mode, dan tidak mengirim observasi. Logger hanya meminta snapshot dengan perintah `q`. Sumber input inferensi dapat berjalan terpisah melalui UART. Tanpa inferensi baru, logger tetap merekam status dengan label `unchanged`.

## Kolom data

| Kolom | Arti dan sumber |
|---|---|
| `timestamp_utc`, `timestamp_local` | Waktu penerimaan snapshot menurut jam laptop; format ISO 8601 dengan zona waktu. Bukan timestamp kejadian di FPGA. |
| `elapsed_s`, `read_duration_ms` | Durasi monotonic sejak logger dibuka dan waktu pembacaan snapshot. |
| `location_label` | Label lokasi yang diketik pengguna. `BELUM_DIISI` jika dikosongkan. |
| `latitude`, `longitude` | Koordinat manual opsional, kosong jika tidak diberikan. Tidak ada GPS atau deteksi lokasi otomatis. |
| `seq`, `event` | Nomor hasil FPGA dan klasifikasi hasil baru, hasil yang sudah ada saat mulai, belum ada hasil, snapshot tidak berubah, atau penghitung terputus/reset/wrap. |
| `a0`, `a1`, `a2` | Tiga hasil inferensi terakhir yang ditangkap observer saat `response_valid`, signed 16-bit Q8.8. |
| `action0_float` .. `action2_float` | Nilai Q8.8 dibagi 256 untuk dibaca manusia. |
| `cycles` | Siklus latency inferensi terakhir dari FPGA. Pada core yang diuji: 6916 siklus, setara 138,32 µs di 50 MHz. |
| `stop`, `mode`, `pin` | Status E-stop, mode I=inferensi/E=echo, dan level input UART dari snapshot FPGA. |
| `accepted`, `rejected`, `error` | Counter frame dan kode error dari wrapper FPGA. Kode disimpan sebagai angka pada CSV; tampilan console memakai heksadesimal. |
| `unobserved_results` | Jika seq maju beberapa angka, jumlah hasil di antaranya yang tidak sempat dibaca. Kosong saat awal/discontinuity karena jumlahnya tidak diketahui. |

**Action yang dicatat adalah hasil terakhir yang disimpan observer, bukan sinyal aktuator saat ini.** Hasil tersebut tetap tersimpan setelah freshness timeout atau E-stop. Baca bersama kolom `event`, `stop`, dan `error`. Contohnya, kode `0x0B` adalah result freshness timeout pada wrapper saat ini; hasil lama tetap dapat dilihat untuk audit, tetapi tidak boleh ditafsirkan sebagai izin menjalankan motor. Sumber perilaku: `fpga/rtl/igor_src_policy/igor_src_policy_uart.v` dan observer `fpga/experiments/jp1_1_2_monitor/igor_jp7_monitor.v`.

## Penyimpanan dan batas pembacaan

Setiap sesi memiliki folder lokal `fpga/evidence/datalogger/<UTC timestamp>/` berisi:

- `session.json`: lokasi, asal waktu, jalur komunikasi dan konfigurasi polling.
- `telemetry.csv`: tabel untuk Excel, satu baris per snapshot.
- `telemetry.jsonl`: data yang sama beserta teks snapshot asli.
- `summary.json`: jumlah snapshot, hasil baru, indikasi hasil terlewat, dan status berhenti/error.

CSV dan JSONL di-flush setiap baris. Log tetap lokal dan tidak otomatis diunggah. Default polling adalah 0,25 detik; waktu aktual juga mencakup respons JTAG. Observer menyediakan **snapshot hasil terakhir**, bukan FIFO seluruh hasil. Jika inferensi lebih cepat dari polling, hasil antara dapat terlewat dan ditandai melalui selisih seq; logger ini tidak mengklaim merekam setiap inferensi. Penurunan counter ditandai sebagai reset/wrap yang tidak dapat dibedakan secara pasti oleh protokol saat ini.

CLI tanpa prompt:

```powershell
python fpga/scripts/fpga_datalogger.py --location "Lab ITB - meja A"
python fpga/scripts/fpga_datalogger.py --location "Lokasi uji" --latitude -6.89 --longitude 107.61 --duration 60
```

Koordinat contoh di atas harus diganti dengan koordinat lokasi sebenarnya. Waktu dapat diselaraskan lewat pengaturan jam Windows jika perlu korelasi dengan perangkat lain; logger tidak mengukur akurasi sinkronisasi jam.
