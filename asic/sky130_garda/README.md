# GARDA — rancangan migrasi SKY130 dan chip art SENO

Status: persiapan; belum menjadi layout atau GDS siap fabrikasi.

## Temuan pada referensi PRISM

Arsip PRISM memakai IHP SG13CMOS5L, macro SRAM fisik, model simulasi, LEF/GDS/Liberty, penempatan macro, serta plugin khusus untuk menghubungkan jalur daya ke macro. Chip art memakai layer Metal4 IHP (50/0) dan marker nofill (50/23), dengan area dan exclusion yang ditentukan berdasarkan floorplan. Angka layer, aturan DRC, lokasi, pitch daya dan macro tersebut khusus IHP; tidak boleh disalin sebagai konfigurasi SKY130.

## Kondisi GARDA saat ini

`info.yaml` memilih top neural berbasis logic ROM dan register, bukan SRAM fisik. `.github/workflows/gds.yaml` memilih IHP; `src/config.json` memiliki layer dan corner IHP. Penggantian nama PDK saja tidak menghasilkan desain SKY130 yang valid. Nama top dan modul lama masih dipakai sebagai kontrak RTL serta oleh tes dan pemeriksaan artefak; mengganti seluruh token tanpa memperbarui dependensi akan merusak flow.

## Tahapan implementasi

1. Tetapkan target shuttle atau chip mandiri, kapasitas dan penggunaan SRAM, serta pilih macro SKY130 yang menyediakan GDS, LEF, Liberty, model simulasi dan panduan LVS yang sesuai.
2. Buat wrapper RTL GARDA untuk antarmuka macro tersebut; sesuaikan polaritas, timing baca/tulis, masking dan reset; jalankan tes perilaku terhadap model referensi.
3. Buat konfigurasi SKY130 terpisah beserta manifest source, corner, power grid dan penempatan macro. Alokasikan area chip art sejak floorplan, berikan obstruction sebelum routing, dan jaga jarak terhadap power grid dan pin.
4. Konversikan gambar SENO menjadi geometri monokrom pada layer SKY130 yang sah dan tempatkan teks GARDA; tetapkan dimensi aktual setelah ukuran chip dan floorplan diketahui. `seno-garda-concept.png` adalah pratinjau grafis, bukan geometri manufaktur.
5. Jalankan physical flow dari source dan validasi DRC, LVS, konektivitas power, timing, pengujian gate-level, serta precheck target terhadap GDS yang memuat artwork. Periksa tampilan hasil dari GDS itu sendiri.
6. Ganti identitas dan nama top yang terlihat ke GARDA secara menyeluruh pada flow baru, termasuk manifest, source, testbench, pemeriksaan dan viewer, sambil menjaga keterlacakan artefak historis.

## Masukan yang belum ditentukan

Target Tiny Tapeout atau chip mandiri/Caravel; penggunaan dan kapasitas SRAM; ukuran area chip; macro SKY130 beserta seluruh views. Tidak ada GDS final yang dihasilkan atau diklaim lolos pemeriksaan pada tahap ini.

## Dasar desain dipilih dari RTL yang ada

Pengguna memilih chip SKY130 mandiri dan akan memberikan draft ukuran chip kemudian. Kandidat awal adalah jalur neural SRAM yang sudah ada: 6.020 word parameter Q8.8 dan 152 word aktivasi, dengan pembacaan dua operand per siklus. Implementasi historis menggunakan satu macro IHP 2048x64 untuk parameter serta dua macro IHP 256x16 untuk aktivasi. Kapasitas, pemetaan, timing, write-mask, dan jumlah macro SKY130 harus disesuaikan terhadap views yang dipilih dan diuji; tidak menganggap macro IHP kompatibel.

Sumber awal: `src/igor_neural_sram_top.v`, `src/igor_parameter_sram.v`, `src/igor_activation_sram.v`, dan `src/igor_neural_datapath.v`. Root manifest masih memilih desain logic ROM dan register tanpa SRAM. Pengujian `python scripts/verify_neural_sram_integration.py` pada keadaan saat ini menghasilkan 7 sukses, 1 gagal dan 1 error: manifest tidak memilih top SRAM, dan konfigurasi aktif tidak mempunyai `meta.substituting_steps` IHP yang diharapkan tes historis. Ini bukan validasi SKY130. Jangan mengaktifkan kembali plugin atau macro IHP pada alur SKY130.

Contoh library macro SKY130 yang dapat dievaluasi adalah OpenRAM sky130_sram_macros (https://github.com/VLSIDA/sky130_sram_macros); pemilihan ukuran dan kelengkapan views harus diperiksa bersama target fabrikasi. Karena draft ukuran belum tersedia, floorplan, ruang untuk SENO, PDN, serta penempatan dan kelayakan routing belum dapat ditetapkan. Pembuatan GDS final dan klaim kelulusan fisik menunggu parameter tersebut dan toolchain SKY130 lengkap.
