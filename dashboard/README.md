# GARDA RTL Explorer

**iSeeDesignITB** memvisualisasikan RTL GARDA yang sudah ada melalui model 3D DE10-Nano, blok FPGA, dan neural core TinyTapeout. Setiap modul memiliki source Verilog, port, arah data, ukuran bit, hierarchy, dan bukti yang dapat dibuka.

## Jalankan di laptop

1. Jalankan `START_DASHBOARD.bat` pada folder ini. Python 3 harus tersedia.
2. Buka [localhost:8765](http://127.0.0.1:8765).
3. Pilih **DE10-Nano**, **Isi RTL**, atau **TinyTapeout**.
4. Seret model untuk memutar, gulir atau cubit untuk memperbesar, lalu gunakan **Reset** untuk mengembalikan kamera.
5. Klik blok atau nama modul di kanan. Pencarian menerima nama modul maupun sinyal.
6. Buka **Port & bit flow** untuk arah, lebar bit, signedness, dan source asli.

Jalankan melalui HTTP. Pembukaan langsung dengan `file://` tidak dapat memuat modul JavaScript dan data JSON dengan benar. Three.js, font, source snapshot, dan unduhan sudah tersedia lokal. Tidak perlu `npm install` untuk menampilkan dashboard.

## Yang dapat dijelajahi

| Bagian | Cakupan |
|---|---|
| DE10-Nano | Model prosedural board, Cyclone V SoC, GPIO, clock, LED, dan periferal |
| Isi RTL | 20 deklarasi modul pada 19 berkas Verilog FPGA asli |
| TinyTapeout | Empat modul neural aktif 24 → 64 → 64 → 4 dengan dua MAC |
| Jadwal Parallel8 | Visualisasi 6.916 clock FPGA untuk 74 → 128 → 64 → 3; model edukasi |
| Demo gerbang | Model JavaScript dibandingkan dengan RTL Icarus pada 3.084 vektor |
| Bukti | Angka kernel, hasil Quartus, status simulasi dan implementasi fisik |
| Unduhan | Source Verilog, proyek Quartus portabel dan `.sof` historis, source dan test TinyTapeout |

Top FPGA adalah `garda_uart_top`. Planner berada di `garda_top`. Inferensi neural FPGA serial memerlukan 18.192 siklus dan merupakan jalur terpisah dari DWA.

Top ASIC aktif adalah `tt_um_wlmoi_garda_neural_logic`. Jadwal inferensinya 3.080 siklus. Target 50 MHz setara 61,6 µs secara aritmetis, dengan kelayakan timing fisik mengikuti laporan signoff. Model tetap 6.020 kata 16 bit direalisasikan sebagai logic ROM dan aktivasi memakai register. Tidak ada SRAM fisik pada top aktif. Core TinyTapeout ini memuat inferensi neural, sedangkan DWA dan gerbang motor merupakan desain FPGA tersendiri.

## Folder dan sumber kebenaran

```text
GARDA/
├── rtl/                       Source FPGA kanonis
├── src/                       Source dan config TinyTapeout kanonis
├── evidence/tinytapeout/       Bukti verifikasi dan implementasi fisik
├── dashboard/
│   ├── dist/                  Seluruh situs publik siap deploy
│   │   ├── source/            Snapshot source untuk pembaca Verilog
│   │   ├── data/              Katalog dan status berbasis evidence
│   │   ├── downloads/         Proyek Quartus, SOF, source TinyTapeout
│   │   ├── assets/            Foto referensi, font, lisensi, mark
│   │   └── vendor/            Three.js dan lisensi MIT
│   ├── scripts/               Generator katalog dan paket
│   └── tests/                 Validasi distribusi dan model gerbang
└── vercel.json                Deploy repo root → dashboard/dist
```

Edit source utama di `../rtl` atau `../src`, lalu regenerasi snapshot. Jangan mengembangkan salinan `dist/source` sebagai fork RTL.

Dari folder dashboard:

```text
python scripts/prepare_data.py
node --check dist/app.js
node --check dist/scene.js
node --check dist/gate-model.js
python tests/validate_dashboard.py
python tests/verify_gate_model.py
```

`prepare_data.py` membangun ulang katalog, hash source, snapshot, ZIP deterministik, dan status evidence. Seluruh path berasal dari lokasi repository sehingga folder boleh dipindahkan atau di-clone. Font dan lisensi disimpan lokal. Regenerasi tidak mengambil file dari folder video atau komputer asal.

Pengujian gerbang memerlukan Node.js dan Icarus Verilog. Windows menggunakan Icarus Linux melalui WSL bila WSL tersedia. Linux memakai Icarus pada PATH. Hasil 3.084 vektor tercatat pada `dist/data/gate-model-verification.json`. Browser menjalankan model perilaku JavaScript yang diuji terhadap RTL, bukan simulator Verilog dan bukan pengendali motor.

Bukti TinyTapeout berikut merupakan hasil revisi historis dan tidak membuktikan hasil setelah rebranding atau signoff SKY130. Status TinyTapeout dibaca dari `../evidence/tinytapeout/current/verification.json`. Simulasi RTL, netlist generik, netlist sel IHP, global routing, detailed routing, DRC, LVS, dan timing signoff tetap memiliki status masing-masing.

## Deploy Vercel

Impor repository melalui [Vercel, tim wlmois-projects](https://vercel.com/new?teamSlug=wlmois-projects). Gunakan **Root Directory = repository root**, **Framework Preset = Other**, serta **Output Directory = dashboard/dist**. Root `vercel.json` melewati install dan build karena distribusi statis sudah disertakan. Tidak ada environment variable atau backend yang diperlukan.

Vercel menyajikan hanya `dashboard/dist`. File `.vercelignore` juga membatasi unggahan CLI ke distribusi dan konfigurasi. Folder runtime, virtual environment, Git, dan file kerja tidak menjadi konten situs. Seluruh path aset relatif sehingga deployment preview dan production memakai struktur sama.

Panduan menyeluruh tersedia pada [INTERACTIVE_EXPLORER.md](../docs/INTERACTIVE_EXPLORER.md).

## GitHub Pages

Workflow `dashboard-pages.yml` memublikasikan `dashboard/dist` sebagai GitHub Pages. Aktifkan Source **GitHub Actions** pada Settings → Pages. URL aset relatif mendukung path project repository. Panduan publikasi dan cakupan situs ada pada [Interactive Explorer](../docs/INTERACTIVE_EXPLORER.md).

## Board dan UART

| Fungsi | Pin FPGA | Koneksi |
|---|---|---|
| Clock | V11 | 50 MHz |
| UART RX | V12 | JP1 pin 1 |
| UART TX | E8 | JP1 pin 2 |
| UART host GARDA | 115200 baud | 8N1, frame 8 byte, CRC8 |

UART GPIO memakai TTL 3,3 V dengan TX adapter ke RX FPGA, RX adapter ke TX FPGA, serta ground bersama. Protokol host planner 115200 baud berbeda dari protokol STM 1 Mbps. Proyek buzzer referensi memiliki penggunaan E8 berbeda. Ikuti QSF proyek yang diprogram.

Model 3D merupakan ilustrasi penjelas arsitektur. Posisi dan luas blok bukan floorplan GDS atau pengukuran luas silikon. Geometri board bukan CAD mekanik resmi Terasic. Perangkat USB STM memerlukan jalur USB host HPS atau bridge yang benar.

## Referensi dan lisensi

- [Repository GARDA](https://github.com/wlmoi/GARDA)
- [Produk DE10-Nano dari Terasic](https://www.terasic.com.tw/cgi-bin/page/archive.pl?Language=English&CategoryNo=167&No=1046)
- [Referensi interaksi GEMBOK](https://gembok-dashboard.vercel.app)
- [Konfigurasi Vercel resmi](https://vercel.com/docs/project-configuration/vercel-json)
- Three.js r170, MIT. Lisensi pada `dist/vendor/THREE_LICENSE.txt`.
- DM Sans dan Montserrat, SIL Open Font License. Lisensi pada `dist/assets`.
- Foto board memiliki atribusi Terasic pada tampilan dan digunakan sebagai referensi produk.

