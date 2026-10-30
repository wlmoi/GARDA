# IGOR Interactive RTL Explorer

Dashboard **iSeeDesignITB** menghubungkan model board 3D dengan RTL, ukuran bit, hierarchy, dan bukti verifikasi dari repository yang sama. Berkas implementasi berada pada [dashboard](../dashboard/README.md).

## Mulai dari folder repository

Jalankan [START_DASHBOARD.bat](../dashboard/START_DASHBOARD.bat), lalu buka [localhost:8765](http://127.0.0.1:8765). Alternatif lintas platform dari repository root:

```text
python -m http.server 8765 --directory dashboard/dist --bind 127.0.0.1
```

Pilih mode board, RTL, atau TinyTapeout. Klik blok untuk deskripsi fungsi dan source. Panel **Port & bit flow** menampilkan arah, lebar bit, signedness, dan koneksi antarmodul. Demo gerbang menyediakan kontrol kondisi yang menjelaskan mengapa izin keluar atau ditutup.

## Cakupan tiga tampilan

| Tampilan | Source utama | Top |
|---|---|---|
| DE10-Nano dan Isi RTL | [rtl](../rtl) | `igor_uart_top` |
| Planner empat tile | [igor_top.v](../rtl/igor_top.v) | Diinstansiasi oleh top UART |
| TinyTapeout aktif | [src](../src), [info.yaml](../info.yaml) | `tt_um_wlmoi_igor_neural_logic` |

FPGA memiliki 19 berkas dan 20 deklarasi modul. `igor_neural_datapath` didefinisikan pada berkas `igor_neural_core.v`. Dashboard juga menjelaskan wrapper scene alternatif yang bukan top aktif proyek Quartus.

Neural FPGA serial dan neural ASIC dual MAC memiliki implementasi berbeda. Core TinyTapeout menjalankan model tetap 24 → 64 → 64 → 4 tanpa SRAM fisik. DWA, costmap, gerbang motor, dan UART board merupakan bagian FPGA. Eksperimen TinyTapeout gerbang atau SRAM terdahulu tetap merupakan arsip.

Geometri 3D board dan susunan blok merupakan ilustrasi konseptual. Situs tidak menyamakan luas kotak dengan luas sel, penempatan GDS, atau resource ALM.

## Data yang ditampilkan

Katalog [rtl-catalog.json](../dashboard/dist/data/rtl-catalog.json) dibuat dari deklarasi source dan disertai SHA256. Snapshot pembaca source tersimpan pada `dashboard/dist/source`. Generator selalu mengambil data dari source kanonis repository.

Status [TinyTapeout](../dashboard/dist/data/tinytapeout-report.json) dihasilkan dari [laporan verifikasi kanonis](../evidence/tinytapeout/current/verification.json). Setiap tahap memiliki status sendiri. Keberhasilan RTL atau routing tidak menggantikan DRC, LVS, extracted STA, precheck, maupun validasi silikon.

Demo gerbang adalah model perilaku JavaScript yang telah dibandingkan dengan source Verilog pada **3.084 vektor** dan seluruh kode fault **0–11**. [Laporan pembanding](../dashboard/dist/data/gate-model-verification.json) mencatat hash RTL dan model. Demo tidak mengirim perintah ke perangkat fisik.

Angka kernel DWA **7.938 siklus** dan neural FPGA **18.192 siklus** memiliki batas pengukuran masing-masing. Target 50 MHz pada ASIC bukan klaim hasil timing signoff. Power Analyzer FPGA **506,69 mW** merupakan estimasi vectorless dengan keyakinan rendah, bukan daya seluruh board atau robot.

## Memperbarui setelah mengubah RTL atau evidence

Dari repository root:

```text
python dashboard/scripts/prepare_data.py
node --check dashboard/dist/app.js
node --check dashboard/dist/scene.js
node --check dashboard/dist/gate-model.js
python dashboard/tests/validate_dashboard.py
python dashboard/tests/verify_gate_model.py
python scripts/create_manifest.py
python scripts/validate_repository.py
```

Jalankan pembanding gerbang saat RTL gerbang atau model perilakunya berubah. Simpan hasil tes bersama snapshot yang sesuai. Jika hanya evidence TinyTapeout berubah, `python dashboard/scripts/update_evidence.py` memperbarui status tampilan. Jalankan `prepare_data.py` juga untuk memasukkan evidence terbaru ke ZIP unduhan.

Tinjau perubahan, lalu commit seluruh source, evidence, distribusi, dan `evidence/RELEASE_MANIFEST.json` bersama. Generator ZIP memakai nama terurut dan timestamp tetap sehingga input identik memberikan hash identik.

## Publikasi Vercel

Gunakan [New Project pada tim wlmois-projects](https://vercel.com/new?teamSlug=wlmois-projects), lalu impor repository ini.

| Pengaturan | Nilai |
|---|---|
| Root Directory | Repository root, `./` |
| Framework Preset | Other |
| Install Command | Dilewati |
| Build Command | Dilewati |
| Output Directory | `dashboard/dist` |
| Environment variables | Tidak diperlukan |

[vercel.json](../vercel.json) menerapkan pengaturan tersebut. [Dokumentasi resmi Vercel](https://vercel.com/docs/project-configuration/vercel-json) menjelaskan `framework: null`, install kosong, dan output directory. Semua aset, source snapshot, dan unduhan statis telah disiapkan sebelum deployment.

[.vercelignore](../.vercelignore) membatasi file unggahan CLI. Vercel hanya memublikasikan distribusi `dashboard/dist`, sehingga folder `.runtime`, `.venv`, source kerja, dan metadata Git tidak menjadi konten web. Tidak ada backend, telemetri robot langsung, atau akses COM yang disamarkan sebagai fitur web.

Sesudah deployment, periksa tiga mode 3D, pencarian modul, port & bit flow, source viewer, status evidence, demo gerbang, dan tiga unduhan. Nama tim harus tampil **iSeeDesignITB** pada desktop dan ponsel.


## Publikasi GitHub Pages

Workflow `dashboard-pages.yml` menyusun situs dari `dashboard/dist` dan menjadi satu-satunya jalur deployment GitHub Pages. Source Pages menggunakan **GitHub Actions**. Push pada `main` menerbitkan dashboard tanpa menunggu build fisik. Workflow juga berjalan manual dan setelah workflow fisik TinyTapeout berhasil.

Semua URL aset dashboard relatif terhadap halaman, sehingga situs dapat berjalan pada path project seperti `https://sundaysiagian.github.io/peruri-iseedesign/`. File `.nojekyll` disertakan pada distribusi. Publikasi Pages ini merupakan frontend yang sama dengan distribusi Vercel.

Workflow fisik menghasilkan artifact `igor-physical-viewer` setelah GDS, precheck, dan gate-level test berhasil. Pembentuk Pages memeriksa hash source serta konfigurasi sebelum memasukkan layout tersebut ke situs. Viewer tersedia pada `layout/`, sedangkan OASIS dan GDS memiliki alias pada root untuk verifikasi. Layout dari source berbeda ditolak. Jika belum ada artifact yang memenuhi pemeriksaan, halaman layout menjelaskan statusnya dan dashboard tetap tersedia.

Hash source Verilog pada katalog dan bukti model gerbang menormalkan CRLF menjadi LF. Dengan demikian checkout Windows dan Linux memverifikasi source yang sama. Berkas bitstream dan ZIP tetap memakai hash biner tanpa normalisasi.
