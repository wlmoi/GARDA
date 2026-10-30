# GARDA untuk Hackathon ITS 2026

GARDA dikembangkan sebagai purwarupa AI untuk navigasi robot logistik: inferensi fixed-point, pemeriksaan lintasan, dan gerbang izin gerak yang dapat ditelusuri. Tema visual menggunakan biru, cyan, dan kuning dari gambar SENO yang disediakan pengguna.

[Situs resmi](https://hackathon-its.id/) · [Dashboard GARDA](https://garda-chip-explorer.vercel.app/) · [Mulai di sini](QUICKSTART.md)

## Masalah dan validasi

Robot harus memilih gerak saat peta, batas kecepatan, dan kondisi keselamatan berubah. GARDA menyediakan RTL serta alat demo untuk memeriksa alur keputusan. Kebutuhan rute, operator, dan penerimaan pengguna perlu divalidasi bersama calon pengguna; integrasi robot fisik mengikuti hasil pengujian perangkat.

| Prinsip program | Penerapan yang direncanakan | Bukti yang perlu dikumpulkan |
|---|---|---|
| Sustainable | Efisiensi komputasi dan aktivitas saat idle | Energi per inferensi, daya idle/aktif, kondisi pengukuran |
| AI Driven | Inferensi Q8.8 dan pengambilan keputusan | Perbandingan numerik model dengan RTL |
| Innovative | Hardware yang bisa ditelusuri di explorer 3D | Source, clock, hasil regresi, demonstrasi |
| Local | Robot logistik untuk kebutuhan calon pengguna lokal | Wawancara, co-design, dan uji rute |

## Jadwal program resmi 2026–2027

| Bulan | Tahap |
|---|---|
| September 2026 | Kick Off & Sosialisasi |
| Oktober 2026 | Ideation & Mentoring |
| November 2026 | Pengembangan Solusi |
| Desember 2026 | Finalisasi & Persiapan Demo |
| Januari 2027 | Demo Day & Business Matching |
| Februari 2027 | Networking Dinner & Awarding |

Sumber: [Hackathon ITS 2026](https://hackathon-its.id/), diperiksa 30 Oktober 2026. Jadwal di atas adalah jadwal penyelenggara; status seleksi, pendaftaran, penghargaan, dan kemitraan GARDA tidak disimpulkan darinya. Aset SENO adalah identitas pihak penyelenggara, digunakan sebagai konteks presentasi sesuai permintaan pengguna.

## Cakupan demonstrasi

- [Explorer 3D](https://garda-chip-explorer.vercel.app/): board DE10-Nano, blok logis RTL, port, dan source.
- [Animated dataflow](https://garda-chip-explorer.vercel.app/#clock-explorer): jadwal FSM Parallel8 74 → 128 → 64 → 3 dengan kontrol tiap clock, kelompok, dan layer.
- [Gerbang izin](https://garda-chip-explorer.vercel.app/#gate-demo): model perilaku JavaScript yang dibandingkan dengan RTL.
- [Verifikasi](VERIFICATION.md): hasil fungsional dan bukti fisik memiliki cakupan masing-masing.

Target daya rendah dan latensi rendah dinilai melalui pengukuran atau laporan yang dapat direproduksi. Hasil fisik SKY130, SRAM, chip art, DRC, LVS, STA, dan precheck dicatat saat flow terkait selesai.
