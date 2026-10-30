# Acuan implementasi GARDA Hackathon ITS 2026

Acuan pengguna: `GARDA.pdf`, 28 halaman, diterima 30 Oktober 2026.
SHA-256: `8767bf83316af70125ad315795873ace7453b1ef226f8a6e97cd91bd09c42eed`.

Produk utama adalah **GARDA: Gerbang AI Robot Deterministik & Aman**, tim iSeeDesignITB: host ROS 2 mengolah sensor, policy PPO di FPGA mengusulkan tiga koreksi, gerbang keselamatan membatasi keluaran, dan STM32 mengendalikan motor dengan watchdog.

| Kebutuhan proposal | Implementasi / bukti repository | Batas verifikasi |
|:--|:--|:--|
| PPO 74 → 128 → 64 → 3; Q8.8, akumulator 40 bit, delapan MAC | [Parallel8](../fpga/experiments/parallel8/README.md), core dan ROM bank di folder yang sama | Core utama proposal; core serial dan TinyTapeout berbeda |
| 6.916 clock: FC1 3.616, FC2 3.104, FC3 196 | [Model jadwal](../dashboard/dist/clock-explorer.js), regresi Parallel8 | 138,32 µs memakai referensi 50 MHz; tidak mencakup UART |
| UART 921.600 baud, 153 byte request / 11 byte response, CRC-8 | [Integrasi Jetson](../fpga/experiments/parallel8/JETSON_UART.md), wrapper board Parallel8 | Varian `parallel8_9600` terpisah; bukan baud acuan proposal |
| E-stop, validasi 74 input, watchdog 2 ms, masa berlaku hasil 20 ms | Core dan wrapper Parallel8 serta regresi safety | Perlu uji ulang saat bitstream atau interface berubah; bukan sertifikasi keselamatan |
| 3.303 ALM, 64 M10K, 8 DSP | [Bukti kompilasi historis](../fpga/experiments/parallel8/artifacts/acceptance.json) | Snapshot fitted Quartus, bukan hasil mapping baru atau luas ASIC |
| 50,36 mW dinamis / 476,18 mW total FPGA | [Laporan daya](../fpga/experiments/parallel8/artifacts/power/typical/igor_src_policy.pow.summary) | Estimasi vectorless, confidence Low; bukan watt board terukur |
| Explorer 3D dan animasi tiap clock | [Website GARDA](https://garda-chip-explorer.vercel.app/#clock-explorer) | Animasi edukasi model FSM, bukan simulator HDL atau telemetri langsung |
| TKT 4 menuju TKT 5 dan 100 lintasan pilot | Proposal, Lampiran G | Target validasi lapangan; tidak dianggap sudah selesai |

## Perubahan setelah proposal

Pengguna meminta **Parallel16** dan integrasi CPU **RISC-V** setelah penyerahan PDF. [Varian Parallel16](../fpga/experiments/parallel16/README.md) mempertahankan model 74 → 128 → 64 → 3 dengan 16 MAC: 1.808 + 1.552 + 196 = **3.556 clock** (71,12 µs pada referensi 50 MHz). Angka FPGA fitted, daya, dan uji fisik Parallel8 pada PDF tidak berpindah otomatis ke varian baru. [Rancangan integrasi RISC-V/HWPE](RISCV_HWPE_ARCHITECTURE.md) menjelaskan status dan gerbang validasinya.

## Jalur yang harus dibedakan

- **Parallel8 FPGA** adalah implementasi utama proposal. Latensi 6.916 clock hanya berlaku pada core ini.
- **DWA** adalah planner/eksperimen terpisah; angka 7.938 clock tidak menggantikan latensi policy PPO.
- **TinyTapeout neural 24 → 64 → 64 → 4** memakai dua MAC, 6.020 kata dan 3.080 clock. Regresinya tidak membuktikan model utama Parallel8.
- **ASIC I/O IHP historis** pada proposal berbeda dari build neural IHP yang sedang berjalan. Metrik GDS, DRC, LVS dan daya wajib terikat ke desain, PDK, dan revisi masing-masing.
- **SKY130 dengan SRAM dan chip art SENO** tetap arah pengembangan yang diminta pengguna. Build IHP tidak membuktikan keberhasilan port SKY130.
- Wrapper DMA di `src/igor_pipeline/fpga_pl` masih prototipe serial: bukan jalur demo Parallel8 siap pakai.

## Penerimaan perubahan

Setiap perubahan model, banking, FSM, atau clock perlu regresi numerik dan jadwal baru. Build fitted FPGA, pengukuran board, uji navigasi dan signoff ASIC harus dilaporkan terpisah. Status run terbaru dapat diperiksa pada [GitHub Actions GARDA](https://github.com/wlmoi/GARDA/actions).
