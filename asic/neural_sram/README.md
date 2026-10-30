# Neural parameter SRAM — IHP SG13CMOS5L

> Historical implementation, no longer the active submission. The final SRAM attempt `b70b1ec` passed GDS physical acceptance and gate-level inference, but failed Tiny Tapeout power-pin precheck (56.48 um from bottom, maximum 10 um). The user requested the [full-inference no-SRAM fallback](../neural_logic/README.md), which is now selected by the root manifest. Reproduce the SRAM pin harness from commit `b70b1ec`.

Target ASIC aktif di manifest root: `tt_um_wlmoi_garda_neural_sram`. Semua **5.888 weight + 132 bias** jaringan 24→64→64→4 berada di **1 macro fisik `RM_IHPSG13_1P_2048x64_c2_bm_bist`**. Kapasitas 8.192 word × 16 bit; 6.020 word digunakan (12.040 byte), 2.172 word terakhir diblokir. Setiap parameter memakai format Q8.8 yang sama dengan ekspor FPGA.

RTL utama FPGA sebelumnya sudah memakai block RAM M10K/M9K yang diinisialisasi dari `.mem`. Target ASIC ini mengganti jalur penyimpanan parameter dengan macro SRAM eksplisit yang diprogram host setelah power-up. Datapath ASIC memakai MAC pipelined dua weight per cycle serta prefetch bias. Model numeriknya sama dengan FPGA; jalur FPGA lama tetap memakai controller 18.192-cycle untuk menjaga kompatibilitas bitstream dan benchmark historis.

**Status:** pengujian model SRAM resmi, inferensi RTL, synthesis generik, dan regresi FPGA tersedia di direktori `evidence`. Hardening CMOS5L, power-grid connectivity, DRC, integration LVS, gate simulation dengan sel PDK, precheck, dan STA belum lulus seluruhnya. Root `info.yaml` dan `src/config.json` kini membangun target SRAM pada alokasi **8x4**. Status fabrikasi menunggu laporan physical flow, precheck, gate test, dan pemeriksaan 1 parameter + 2 activation bank pada layout yang diterbitkan.

## Jalankan verifikasi

Dari root repository, dengan Python 3.11 dan Icarus Verilog:

```powershell
python scripts/verify_neural_sram_integration.py
python scripts/synth_neural_sram.py
python scripts/verify_neural_sram.py --generic
python verification/run.py neural
python verification/run.py tt_sram
```

Synthesis menggunakan runtime YoWASP Yosys proyek. Pengujian SRAM memakai dua model resmi IHP, `SIM` dan `FUNCTIONAL`, dengan hash yang diverifikasi dari [provenance.json](ihp/provenance.json). Model dan LEF disalin tanpa modifikasi dari commit PDK `2bbec755dc67ca3db0261c3d6163e15735d66710`. [Panduan pengguna yang dijadikan acuan](REFERENCE_GUIDE.md) disimpan agar kontrak asal dapat ditelusuri.

Regression memeriksa 6.020 alamat, batas bank, mask bit/byte, output hold, enable, alamat di luar rentang, retensi SRAM saat reset, upload tidak lengkap, write tidak berurutan, kepemilikan port saat START/busy, invalidasi hasil lama pada BEGIN, dan 100 vektor terhadap model integer Python dari ekspor per layer. Netlist generik diuji terpisah pada 1 vektor, semua readback, dan proteksi kepemilikan port. Latensi terukur RTL 3.080 siklus; 61,6 µs adalah perhitungan pada 50 MHz, **belum hasil STA ASIC**.

## Alamat weight dan bias

| Data | Alamat word | Jumlah |
|---|---|---:|
| W1: 24×64 | 0–1535 | 1536 |
| B1 | 1536–1599 | 64 |
| W2: 64×64 | 1600–5695 | 4096 |
| B2 | 5696–5759 | 64 |
| W3: 64×4 | 5760–6015 | 256 |
| B3 | 6016–6019 | 4 |

Row fisik = `address[12:2]`, quarter = `address[1:0]`. Setiap row 64-bit menyimpan empat word 16-bit. Selector pasangan `address[1]` memilih word 0/1 atau 2/3 untuk dua lane MAC. Write mask 64-bit hanya mengubah quarter terpilih, termasuk mask bit/byte host. Selector quarter dilatch pada edge baca dan hold pada write/disable.

## Antarmuka host pada pin Tiny Tapeout

`ui_in[0]` adalah write-enable, `ui_in[4:1]` indeks register, `ui_in[7:5]` selector baca; byte tulis berasal dari `uio_in`. Semua UIO tetap input (`uio_oe=0`); output baca tersedia di `uo_out`. Interface ini memakai register sinkron, terpisah dari opcode UART FPGA lama. Host harus menyinkronkan sinyal dengan `clk` serta memenuhi setup/hold pada rising edge; transaksi SRAM yang dilatch di situ dilaksanakan pada rising edge berikutnya. Callback transport harus menunggu rising edge tersebut sebelum mengembalikan hasil atau mengirim transaksi berikutnya.

| Register tulis | Fungsi |
|---:|---|
| 0 | Alamat host bit 7:0 |
| 1 | Alamat bit 12:8; bit 7:5 wajib nol |
| 2 | Stage byte data rendah |
| 3 | Stage byte data tinggi |
| 4 | Command: 1=BEGIN, 2=WRITE, 3=COMMIT |
| 5 | Indeks input neural, 0–23 |
| 6 | LOAD_INPUT dari kedua byte data yang telah distage |
| 7 | START; payload tidak dipakai |
| 8 | Pilih output neural, 0–3 |
| 9 | Halaman diagnostik selector 7: 0=identitas, 1–4=byte counter latensi |

| Selector baca | Nilai |
|---:|---|
| 0 | Status: bit 0 reset released, 1 ready, 2 busy, 3 done, 4 host fault, 5 neural fault, 6 loading |
| 1, 2 | Data SRAM byte rendah/tinggi; nol saat busy |
| 3, 4 | Hasil neural byte rendah/tinggi; nol sebelum valid atau saat fault |
| 5, 6 | Jumlah word yang berhasil diterima, byte rendah/tinggi |
| 7 | Identitas interface `0xA6` saat halaman 0; byte latensi low→high pada halaman 1–4 |

Urutan pemrograman:

1. Reset, kemudian BEGIN. BEGIN memblokir inferensi dan mereset kontrol neural sehingga input/hasil dari image sebelumnya tidak dipakai lagi.
2. Untuk setiap word 0–6019, tulis register 2 dan 3, lalu WRITE. Alamat bertambah otomatis. Kedua byte wajib diisi ulang untuk setiap word; alamat harus sama dengan counter upload.
3. Set alamat melalui register 0/1 dan baca kembali **semua** 6.020 word. Jika ada mismatch, hentikan proses sebelum COMMIT.
4. COMMIT hanya diterima setelah seluruh word ditulis dan tidak ada host fault. Kelengkapan dijamin hardware; kesesuaian isi terhadap image diperiksa host, tanpa CRC image di hardware.
5. Untuk setiap input, pilih register 5, stage kedua byte, lalu LOAD_INPUT. Tunggu setidaknya satu rising edge berikutnya sebelum mengubah data/indeks. Setelah 24 input, START dan poll done/fault; pilih output untuk membaca empat hasil.

[host.py](host.py) menyediakan loader dengan readback lengkap dan validasi rentang, melalui callback transport board. SRAM tidak menyimpan data setelah power-off; image harus diupload ulang setelah power-up. Reset logis mempertahankan sel memori tetapi membatalkan ready sehingga image perlu divalidasi dan dimuat ulang sebelum digunakan. Host fault bersifat sticky sampai reset atau BEGIN yang sah; neural fault dibersihkan oleh reset/BEGIN. Write/BEGIN saat START pending atau busy ditolak dan menutup validitas hasil.

## Integrasi fisik dan batas alokasi

`info.yaml` root memilih **`tt_um_wlmoi_garda_neural_sram`**, bukan wrapper safety gate. Alokasi **8x4** memiliki bounds 1724,16 x 710,64 um dari tt-support-tools pinned. Satu SRAM parameter ditempatkan N pada (900;70) um, berukuran 784,48 x 626,70 um. Upper edge + halo 6 um berada pada 702,70 um, di bawah core upper bound 706,86 um. Semua pin sinyal berada di sisi bawah menurut LEF resmi. Dua SRAM activation 236,8 x 118,78 um ditempatkan sejajar pada (320;580) dan (610;580) um, dengan jarak antar footprint 53,2 um dan upper halo edge 704,78 um. Area besar di sisi kiri tetap tersedia untuk logika dan jalur menuju SRAM. Penempatan ini harus dibuktikan oleh physical flow; bounds offline saja tidak menjamin routing.

Konfigurasi aktif [src/config.json](../../src/config.json) berisi seluruh macro views, corner, placement, suplai, dan flow steps; [config.fragment.json](config.fragment.json) menyimpan salinan integrasi dengan path relatif direktori ini. Sumber synthesis aktif adalah `src/garda_neural_sram_top.v`, `src/garda_parameter_sram.v`, `src/garda_neural_datapath.v`, `src/garda_activation_sram.v`, serta deklarasi blackbox 2048x64 dan 256x16. Regresi memeriksa salinan integrasi dan mencocokkan semua output ASIC dengan model integer independen yang juga digunakan FPGA.

Workflow root membangun physical target ini dengan PDK `2bbec755dc67ca3db0261c3d6163e15735d66710`, action `3412659307918422f3f0727917cf9b499aaca588`, dan support tools `d66cf179e7bc4d296362ab7e2e3b344dc3c4f665`. Template 8x4 pinned disimpan di direktori ini untuk pemeriksaan offline; flow mengambil template yang sama dari support tools.

Plugin root [librelane_plugin_neural_sram.py](../../librelane_plugin_neural_sram.py) menambahkan koneksi PDN dan adapter LVS. Semua 3 instance, orientasi, bounds, kolom Metal4, serta suplai VDD!/VDDARRAY!/VSS! diperiksa. Interface pins ditempatkan sebelum PDN. Kolom suplai diturunkan langsung dari LEF: 68 power dan 68 ground per macro 2048x64, serta 20 power dan 20 ground per macro 256x16.

Build GDS diikuti pemeriksaan jumlah SRAM pada **hierarki OASIS submission sebenarnya** dan nilai nol untuk error LVS, KLayout DRC, serta power grid. Viewer hanya diterbitkan setelah build, precheck dan gate-level test lulus. `test/test.py` memprogram dan membaca semua 6.020 word melalui pin submission sebelum memeriksa inferensi.

Target baru ini tidak menghubungkan output neural ke driver motor/DWA. Wrapper safety gate lama dipertahankan untuk regresi pada `src/project.v` dan `verification/test_tt_gate.py`, tetapi tidak masuk manifest GDS aktif. Layout safety gate lama tidak memenuhi acceptance SRAM dan akan ditolak checker layout.

`A_CLK=clk`, enable/write/read/mask aktif tinggi, `A_DLY=1`, dan semua BIST ditie-off sesuai panduan. SRAM dibaca pada rising edge; datapath menangkap hasil pada rising edge berikutnya, lalu melakukan dua MAC pada full cycle berikutnya. Ini adaptasi sengaja dari contoh 256x16 falling-edge dalam panduan: pipeline full-cycle menjaga target 50 MHz dengan macro 2048x64 dan 256x16. STA wajib menguji full-cycle SRAM dan MAC pada 20 ns. Corner fast flow m40C memakai Liberty SRAM m55C sesuai kontrak referensi; kesesuaian dengan shuttle masih perlu direview.

Pemeriksaan offline memastikan pin/view, nama 3 bank, halo kandidat, dan perbaikan format LVS; **bukan** bukti legalitas layout, konektivitas PDN, atau hasil LVS. Tidak ada klaim SRAM neural sudah tersambung ke jalur DWA/motor; target ini menjalankan inti inferensi dan penyimpanan parameternya.

Tiga macro menyediakan kapasitas parameter dan activation. Satu SRAM parameter menghasilkan dua weight dari row 64-bit, sementara pasangan SRAM activation dibaca paralel setiap cycle. Dua MAC memproses 5.888 weight dalam 2.944 cycle ditambah kontrol neuron, total 3.080 cycle. Menambah lane komputasi memerlukan evaluasi area, routing, dan timing baru.

Input 0..23 dan hidden activation 24..87 serta 88..151 disimpan dalam dua SRAM 256x16, dengan parity sebagai bank dan address[7:1] sebagai row. Array register input/h1/h2 dan mux baca lebarnya dihapus. Synthesis generik turun dari 2.869 menjadi 412 register bit (85,7%). Output empat word tetap register. Prefetch dua operand berikutnya menjaga latensi 3.080 cycle saat satu edge SRAM dipakai menulis hasil neuron. Read outputs harus hold pada write/disable, diverifikasi dengan model resmi.

[Rincian analisis kegagalan routing dan acceptance](../../docs/SRAM_ROUTING_ANALYSIS.md).

Clock tree menggunakan `CTS_APPLY_NDR=root_only` dan `CTS_OBSTRUCTION_AWARE=true`. CTS menerapkan kebijakan NDR 2x spacing pada trunk utama; global router dapat melonggarkannya bila congestion tetap ada. Branch memakai aturan normal, dengan buffering yang mempertimbangkan obstruction macro. Global routing tetap harus bebas overflow. Step routing menambahkan laporan koordinat congestion tanpa mengubah opsi routing atau menutupi error.

Build `74b15b5` sudah mencapai zero overflow, DRC KLayout/routing, power-grid error, serta setup/hold violation. Antarmuka SPICE macro 2048x64 kini mengelompokkan setiap bus secara contiguous menurun agar Netgen membaca seluruh 64 bit; replay layout final cocok secara unik. Pemeriksa overlap hanya menerima `obsm4`/`metal4` pada kolom suplai SRAM yang diketahui, dengan jumlah Magic asli tetap tercatat dan error lain tetap fatal. Post-GRT design/timing repair kini aktif untuk menyelesaikan sisa 46 slew dan 5 cap violation dari run tersebut. Semua acceptance fisik wajib diulang pada konfigurasi baru.

Run `e2c456a` kembali lulus routing/KLayout DRC, power grid, setup/hold, dan seluruh capacitance check. Build berhenti pada pemanggilan logging `self.info` di plugin; LibreLane memakai `librelane.logging.info`. Regression test kini menjalankan metode checker sampai menghasilkan report dan metrik, termasuk penolakan DRC/power error. Replay LVS pada extraction run ini cocok secara unik (7459 device dan 7560 net di kedua sisi). Masih ada 14 slew violation pada pin write-mask setelah RC extraction; margin repair slew diperbesar dari 25% menjadi 50% untuk mengantisipasi parasitik routing, tanpa melonggarkan limit library maupun acceptance 50 MHz. CI fisik, gate-level, dan viewer masih wajib lulus pada konfigurasi tersebut.

Run `4f99c81` berhasil membangun submission GDS dengan LVS, KLayout/routing DRC, dan power grid bersih. Pemeriksa submission tetap menolak 14 slew violation: tujuh pin mask per decoder masih langsung digerakkan `sg13cmos5l_nor2b_1`, walaupun cabang lain sudah dibuffer oleh resizer. Perbaikan terarah kini menemukan driver dari koneksi `A_BM` (tanpa nama cell hasil sintesis yang di-hardcode), mengganti hanya NOR2B minimum-drive tersebut dengan `sg13cmos5l_nor2b_2`, lalu menjalankan legalisasi dan routing ulang bawaan LibreLane. Resizer berikutnya tidak boleh mengecilkan kembali kedua driver tersebut. Replay dengan SPEF hasil routing menghilangkan seluruh slew/cap violation di ketiga corner; bukti replay terpisah dari kelulusan fisik CI yang masih harus diulang.
