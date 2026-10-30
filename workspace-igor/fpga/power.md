# IGOR Chip — estimasi daya dan efisiensi desain

**IGOR Chip menunjukkan profil daya yang menarik untuk pengembangan
pengendali protokol industri yang ringkas dan hemat energi.** Laporan ASIC
post-route mencatat total daya **2,037372 mW** pada kondisi Typical.

Dokumen ini merangkum hasil desain **`tt_um_igorchip`**, PDK
**`ihp-sg13cmos5l`**, dari arsip implementasi yang diberikan pengguna.
Angka pada tabel merupakan **estimasi EDA post-route**.

## Estimasi daya ASIC

| Kondisi analisis | Internal | Switching | Dynamic | Leakage | Total |
|---|---:|---:|---:|---:|---:|
| Typical · 1,20 V · 25°C | 1,663574 mW | 0,3237679 mW | **1,9873419 mW** | 0,0500292 mW | **2,037372 mW** |
| Fast · 1,32 V · −40°C | 2,068604 mW | 0,4088668 mW | **2,4774708 mW** | 0,1845691 mW | **2,662040 mW** |
| Slow · 1,08 V · 125°C | 1,351240 mW | 0,2528204 mW | **1,6040604 mW** | 0,01664386 mW | **1,620704 mW** |

**Dynamic = internal + switching.** Total mencakup kontribusi sequential,
combinational, clock dan macro yang dilaporkan tool. Kontribusi clock dan
macro sudah termasuk dalam total.

Pada Typical, rincian total berdasarkan group adalah:

| Group | Total estimasi |
|---|---:|
| Sequential | 1,063457 mW |
| Combinational | 0,05888026 mW |
| Clock | 0,5526024 mW |
| Macro | 0,3624343 mW |

Nilai group berasal dari report yang dibulatkan. `final/metrics.json`
menyimpan total Typical dengan presisi lebih tinggi:
**2,0373715087771416 mW**.

## Mengapa hasil ini menarik?

- **Daya tingkat miliwatt.** Ketiga profil analisis melaporkan total
  sekitar **1,62–2,66 mW**, memberikan dasar kuantitatif untuk perencanaan
  budget energi pengendali digital.
- **Implementasi ringkas.** Die sekitar **0,916214 mm²**, dengan satu
  macro SRAM **256×16 bit** untuk penyimpanan program.
- **Empat context eksekusi.** Satu engine dapat menjalankan pekerjaan
  protokol yang dibagi ke empat context dengan state terpisah.
- **Proteksi operasi pada hardware.** Kepemilikan pin, kontrol penulisan
  program, status error dan kontrol output enable diimplementasikan di RTL.
- **Hasil dapat ditelusuri.** Setiap angka mempunyai sumber report,
  lokasi baris atau JSON pointer, serta identitas SHA256.

## Cara memperoleh angka power

Flow implementasi memakai library daya, hasil pemetaan sel, parasitik
interkoneksi dan kondisi analisis untuk menghasilkan `report_power`.
Laporan sumber menggunakan **Watts**; konversinya:

```text
P_mW = P_W × 1000
P_dynamic = P_internal + P_switching
P_total = P_dynamic + P_leakage
```

Sumber tabel adalah tahap **56-openroad-stapostpnr**, baris `Total` **16**
pada masing-masing `power.rpt`:

- [Typical](evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/56-openroad-stapostpnr/nom_typ_1p20V_25C/power.rpt).
- [Fast](evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/56-openroad-stapostpnr/nom_fast_1p32V_m40C/power.rpt).
- [Slow](evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/56-openroad-stapostpnr/nom_slow_1p08V_125C/power.rpt).

## Bukti verifikasi dan rekaman lengkap

Pengujian gate-level yang dilampirkan mencatat **PASS** untuk
`test_project`, dengan durasi simulasi **74.821 ns**.
[results.xml](evidence/asic_import/gatelevel_test_results/raw/results.xml)
dan [waveform FST](evidence/asic_import/gatelevel_test_results/raw/tb.fst)
menyediakan bukti hasil uji tersebut.

Rekaman numerik implementasi tersedia lengkap:

- [199 metrik final beserta sumber/baris/SHA](evidence/asic_import/gds_diagnostics_1/final_metrics.csv).
- [201.365 leaf value JSON dari seluruh tahap dan konfigurasi](evidence/asic_import/gds_diagnostics_1/all_json_values.csv).
- [60 baris group power lintas tahap/corner](evidence/asic_import/gds_diagnostics_1/all_power_reports.csv).
- [Inventaris 614 anggota arsip](evidence/asic_import/gds_diagnostics_1/archive_inventory.csv).
- [Ringkasan numerik berpresisi penuh](evidence/asic_import/gds_diagnostics_1/summary.json).

## Profil prototipe FPGA Parallel8

Prototipe neural **PPO 74→128→64→3** pada DE10-Nano mempunyai karakterisasi
tersendiri: **0,13832 ms** per inferensi core, **3.303 ALM**, **64 M10K**,
dan **8 DSP**. Estimasi Quartus Typical adalah **50,36 mW dynamic** dan
**476,18 mW total**, berlabel **confidence Low / HPS Off** pada report.

Sumber: [README Parallel8](experiments/parallel8/README.md) dan
[Power Analyzer summary](experiments/parallel8/artifacts/power/typical/igor_src_policy.pow.summary).
Identitas desain tetap dicantumkan pada setiap tabel agar hasil ASIC
`tt_um_igorchip` dan prototipe neural Parallel8 mudah digunakan secara tepat.

## Narasi untuk presentasi

> IGOR Chip menggabungkan estimasi daya Typical sekitar **2,04 mW**,
> empat context eksekusi, penyimpanan program SRAM, dan proteksi operasi
> I/O langsung di hardware. Hasil ini menjadikannya prototipe yang
> menarik untuk pengembangan pengendali protokol industri dengan fokus
> pada efisiensi energi, kendali akses pin, dan integritas operasi.
> Hasil uji gate-level yang dilampirkan berstatus **PASS**, dengan data
> implementasi dan power yang dapat ditelusuri ke laporan sumber.
