# Status sign-off ASIC pada branch audit

Branch kerja: **`work/asic-signoff-audit`**. Source RTL dan bitstream yang
sudah ada tidak diubah oleh impor/audit ini. `main` tidak di-commit/push.
Semua keluaran baru berada di `fpga/`.

## Bukti yang lulus

- **Functional gate-level test PASS:** satu `test_project`, tanpa elemen
  failure/error/skipped pada [results.xml](../evidence/asic_import/gatelevel_test_results/raw/results.xml).
  Wall time **1,663216114 s**, simulation duration **74.821 ns**, random seed
  **1792151866**. Durasi test tersebut bukan latency inferensi.
- Arsip GL menyediakan **tb.fst**; konversi ke VCD berhasil,
  dengan **31.409 deklarasi sinyal**. Ini pembacaan hasil pengguna, bukan
  klaim menjalankan ulang gate-level simulation di mesin lokal.
- Laporan fisik mencatat routing DRC **0**, KLayout DRC **0**, LVS errors
  **0**, antenna violations **0**, serta hold violations **0**.

## Yang belum boleh dilabel PASS

| Pemeriksaan | Nilai dari ZIP GDS | Status bukti |
|---|---:|---|
| Slow-corner setup slack | **−2,6372718089 ns** | Timing belum closed pada target 20 ns |
| Slow-corner setup TNS | **−258,6047076344 ns** | Belum nol |
| Setup violation paths | **253** | Belum nol |
| Max slew violations | **26** | Belum nol |
| Max capacitance violations | **11** | Belum nol |
| Max fanout violations | **58** | Perlu repair/review constraint |
| Illegal overlap metric | **42** | Perlu review fisik/waiver yang sah |
| Tiny Tapeout precheck | Tidak disertakan | Belum dibuktikan |
| Netlist/GDS hash pengikat ZIP GL ke ZIP GDS | Tidak disertakan | Korelasi revisi belum dibuktikan |
| SDF annotation pada tes GL | Tidak disertakan | Tidak ada klaim timing simulation |

Sumber angka: [199 metrik final](../evidence/asic_import/gds_diagnostics_1/final_metrics.csv),
[post-route summary](../evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/56-openroad-stapostpnr/summary.rpt),
serta [raw metrics](../evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/final/metrics.json).
Config sumber mengatur `ERROR_ON_ILLEGAL_OVERLAPS=false` dan
`RUN_MAGIC_DRC=false`. Laporan manufacturability yang mengatakan antenna,
LVS dan DRC passed tidak menghapus pelanggaran setup/DRV/overlap di atas.

GL functional PASS dan physical sign-off adalah pemeriksaan berbeda. Tidak
boleh mengganti nilai report menjadi nol, mematikan checker untuk memperoleh
label PASS, atau menganggap satu tes GL mencakup semua path fisik.

## Temuan untuk perbaikan berikutnya

Path setup pertama pada slow corner berawal dari **program_store.i_sram**
melalui **A_DOUT[14]**, lalu decode/logic ke register **_7289_**. SRAM memakai
clock terbalik; launch **10 ns**, capture target **20 ns**. Pada path itu
data arrival dilaporkan **22,939928 ns**, sehingga tersedia hanya setengah
periode untuk SRAM clock-to-Q, routing dan logic sebelum setup capture.
Lihat [max.rpt](../evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/56-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt).

Arah eksperimen yang memerlukan regresi: memendekkan decode/path tersebut
atau menambah staging fetch/execute dengan context tag yang benar; buffering
dan placement untuk slew/cap/fanout; review lokasi/rule overlap macro SRAM.
Mengubah pipeline dapat mengubah cadence empat context, branch, literal,
wait dan host readback, sehingga tidak dilakukan hanya untuk membungkam STA.
Menurunkan clock target juga bukan perbaikan sah untuk klaim 50 MHz tanpa
mengubah spesifikasi dan menguji ulang flow.

Source referensi lokal `src/igorchip_top.v`, `program_host.v`,
`program_memory.v`, `defines.vh`, `sram_256x16_bb.v` serta `info.yaml`
menunjukkan **IgorChip Programmable Protocol Engine**, empat thread dan
SRAM 256×16. Nama top cocok dengan konfigurasi arsip. Ini bukan bukti bahwa
hasil power **2,037372 mW** adalah hasil neural Parallel8 74→128→64→3;
kesetaraan desain/revisi harus dibuktikan tersendiri.

Workflow yang ditempel pengguna dicatat sebagai
[referensi YAML](../ci/gds_user_reference.yml), tanpa mengaktifkan workflow
atau deployment baru. Konfigurasi: Ubuntu 24.04, timeout job **180 menit**,
timeout build **150 menit**, retensi artifact **14 hari**, action branch
`ihp-cmos5l`, PDK `ihp-sg13cmos5l`, checkout v6, upload-artifact v7.
Precheck/GL/viewer tergantung job GDS; definisi dependency bukan bukti PASS.

## Syarat menutup status menjadi sign-off PASS

1. Kunci revisi RTL, PDK `ihp-sg13cmos5l`, library/macro, flow dan constraint.
2. Jalankan ulang implementation flow pada source yang sama dengan pengujian.
3. Buktikan timing/DRV memenuhi spesifikasi pada seluruh corner; selesaikan
   overlap atau sertakan waiver yang diterima pihak shuttle/foundry.
4. Simpan precheck, DRC/LVS/antenna, PDN dan gate-level results beserta SHA
   netlist/layout dan status job. Jangan mengandalkan YAML workflow saja.
5. Pastikan regresi fungsional tetap lulus, lalu bandingkan PPA dengan run asal.

Pada audit lokal ini, command ASIC flow/PDK belum tersedia pada PATH Ubuntu,
dan daemon Docker tidak aktif. Belum ada physical rerun baru yang dapat
diklaim PASS. Source referensi tetap dipertahankan; laporan impor tetap utuh.
