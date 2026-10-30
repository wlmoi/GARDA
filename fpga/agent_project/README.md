# IGOR — paket informasi project untuk agent

Mulai dari **PROJECT_CONTEXT.md**, lalu **DELIVERABLES_GUIDE.md**. Paket ini mencakup seluruh area repository, bukan hanya FPGA.

- Source commit saat pengambilan: `d38429f79463dc840b9d532b42b98d6c397db1a9`.
- 2420 file project tracked terinventarisasi; 109 dokumen disalin penuh ke arsip teks per area.
- Semua dokumen asli tetap dipertahankan. Snapshot memuat juga dokumen historis yang dapat bertentangan; aturan pemilihan bukti ada di PROJECT_CONTEXT.md.
- DELIVERABLES_ALL.md: daftar setiap file. repository_inventory.json/CSV: lokasi, peran, ukuran, SHA256 dan penanda LFS.
- Paket ZIP memuat seluruh isi paket informasi ini. Bitstream, waveform dan database fisik tetap di repository pada lokasi inventaris; tidak digandakan ke ZIP informasi agent.
- Dependency environment, cache Python dan referensi lokal peruri-iseedesign dikecualikan. Itu bukan deliverable first-party repository.
- Ini snapshot working tree. Berkas evidence yang telah berubah lokal dicatat berdasarkan byte lokal, bukan dianggap hasil baru yang sudah committed atau diuji ulang.

## Dokumen lengkap

- [DOCUMENTATION_DOCS.md](DOCUMENTATION_DOCS.md): 21 dokumen penuh.
- [DOCUMENTATION_FPGA.md](DOCUMENTATION_FPGA.md): 70 dokumen penuh.
- [DOCUMENTATION_ROOT.md](DOCUMENTATION_ROOT.md): 13 dokumen penuh.
- [DOCUMENTATION_SRC.md](DOCUMENTATION_SRC.md): 2 dokumen penuh.
- [DOCUMENTATION_TEST.md](DOCUMENTATION_TEST.md): 2 dokumen penuh.
- [DOCUMENTATION_WAYPOINT_LIST.md](DOCUMENTATION_WAYPOINT_LIST.md): 1 dokumen penuh.

## Pemakaian

Unggah ZIP atau berkas context beserta arsip dokumentasinya sebagai project knowledge. Untuk batas unggahan kecil, unggah PROJECT_CONTEXT.md dan DELIVERABLES_GUIDE.md dahulu, kemudian arsip per area sesuai kebutuhan. Source code lengkap tersedia di repository sesuai inventory; snapshot ini tidak menyisipkan seluruh kode atau binary ke prompt.

Regenerasi dari root: `python fpga/scripts/build_agent_project_pack.py`. Tidak memprogram board, menjalankan motor, mengubah RTL, atau mengganti laporan asli.
