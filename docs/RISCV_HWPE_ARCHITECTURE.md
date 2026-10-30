# GARDA RISC-V dan neural HWPE

Integrasi GARDA: William Anthony. Keputusan desain awal, 30 Oktober 2026.

## Keputusan awal

Gunakan **PicoRV32 upstream** sebagai prosesor kontrol prototipe yang dapat diuji pada tool tersedia; Ibex `small` tetap kandidat pembanding. Target inferensi terbaru memakai **Parallel16 74 → 128 → 64 → 3** (permintaan pengguna setelah proposal); Parallel8 tetap baseline, bukan dieksekusi ulang oleh CPU. Nonaktifkan cache dan FPU pada kandidat awal; gunakan register file khusus FPGA untuk prototipe FPGA. Pertahankan gerbang keselamatan independen dari firmware.

CPU menulis 74 fitur Q8.8, memulai pekerjaan melalui MMIO, lalu menunggu event HWPE dengan instruksi custom `waitirq` PicoRV32. HWPE mengerjakan ROM bank-paralel dan menghasilkan tiga residual. Gerbang keselamatan memeriksa validitas/usia hasil, watchdog dan E-stop sebelum aktuasi. Adapter MMIO sendiri bukan CPU; integrasi CPU, ROM dan bus berada di `fpga/riscv`.

**Ini pilihan kandidat, bukan bukti daya paling rendah.** Bandingkan energi per keputusan lengkap pada 50 keputusan/detik beserta daya idle, bukan hanya mW saat aktif. Biaya CPU, interconnect, SRAM, UART dan clock harus ikut dihitung.

## Pilihan implementasi prototipe

Integrasi RTL prototipe memakai **PicoRV32 upstream** sebagai CPU RISC-V nyata dengan sumber dan lisensi ISC dipertahankan. Pilihan ini mengutamakan integrasi bus native yang dapat direproduksi pada simulator yang tersedia; bukan kesimpulan bahwa PicoRV32 selalu lebih hemat dari Ibex. Ibex tetap kandidat pembanding. Penantian event pada firmware PicoRV32 memakai instruksi custom `waitirq`, **bukan** instruksi standar WFI. Tidak boleh mengganti nama CPU upstream menjadi IP buatan sendiri.

Dokumentasi dan sumber primer: [PicoRV32](https://github.com/YosysHQ/picorv32). Status CPU dan hasil boot-to-HWPE mengacu pada receipt di folder `fpga/riscv`, terpisah dari uji adapter.

## Kandidat yang ditinjau

| Kandidat | Kesesuaian GARDA | Konsekuensi |
|:--|:--|:--|
| Ibex `small` | Kontrol MMIO, validasi paket, event/interrupt; datapath neural tetap khusus | Integrasi bus, memori, interrupt dan firmware masih harus divalidasi |
| CV32E40P | DSP software, hardware loop dan ekstensi MAC/SIMD; jalur PULP | Fitur DSP CPU bisa menduplikasi MAC HWPE; wajib bandingkan energi workload nyata |
| PULPissimo | Platform SoC yang mendukung CPU dan HWPE, bukan CPU tersendiri | Acuan integrasi TCDM, peripheral control dan event; bukan bukti otomatis cocok pin/board GARDA |

Dokumentasi Ibex menyediakan konfigurasi supported sebagai fokus verifikasi. RV32E/no-multiply merupakan eksperimen lanjutan bila pengurangan register/fitur menguntungkan firmware dan telah diverifikasi, bukan asumsi bahwa varian terkecil selalu paling hemat energi.

## Implementasi eksperimen

[Adapter neural MMIO](../fpga/hwpe/README.md) menghubungkan request/response dengan core Parallel16 aktual. Regresi mencakup semua 236 vektor acuan, 708 keluaran signed, 3.556 clock, backpressure, command invalid, busy-start, fault, abort dan reset. [Receipt](../fpga/hwpe/mmio-regression.json) mengikat hasil simulasi ke hash adapter, testbench, core, enam belas bank ROM dan fixture. Ini belum menginstansiasi CPU, interconnect TCDM, DMA, board top atau safety gate lengkap.

## Batas referensi HWPE

Pengguna menegaskan ketiga modul `drc_fsm.sv`, `drc_streamer.sv`, dan `drc_top.sv` dipakai sebagai **referensi pola integrasi**, bukan fitur audio GARDA. Pola yang relevan: kontrol terpisah dari datapath, ready/valid dengan backpressure, streaming memori dan notifikasi selesai. Parameter threshold, attack/release dan makeup gain tidak masuk ke model neural.

Adapter GARDA baru merupakan kode integrasi orisinal. IP CPU, HWPE-Stream atau komponen pihak ketiga tetap mempertahankan nama implementasi, atribusi, lisensi dan revision pin masing-masing. Author integrasi tidak menggantikan author IP tersebut.

## Penghematan daya yang akan diuji

- Tahan register/datapath saat idle memakai clock-enable FPGA; jangan membuat clock dengan gerbang AND kombinasi.
- Jangan menjalankan CPU dalam polling loop ketika tersedia event/`waitirq` (PicoRV32) atau interrupt/WFI (CPU standar yang mendukungnya).
- Isolasi operand MAC yang tidak digunakan; ROM hanya dibaca pada fase yang diperlukan.
- Gunakan bank memori yang memungkinkan port baca paralel; ukur pengaruh depth FIFO terhadap stall dan switching.
- Pastikan abort/reset mengosongkan hasil lama, dan jangan membekukan safety timer/E-stop bersama datapath neural.

## Gerbang sebelum SOF dan bukti Quartus

1. Simulasi bit-exact terhadap model dan vektor aktual, 74 input / tiga output, batas Q8.8, fault/abort, MMIO dan backpressure.
2. Integrasi CPU nyata, firmware boot, decode alamat, error bus, interrupt, shared-memory ownership dan seluruh jalur keselamatan.
3. Full Quartus compile pada Cyclone V 5CSEBA6U23I7 dengan assignment pin dan SDC aktual; periksa clock, setup/hold, unconstrained paths dan semua critical warning.
4. Analisis daya berbasis aktivitas representatif pada workload yang sama; laporkan confidence dan pemisahan estimasi/pengukuran.
5. Baru terbitkan `.sof` baru, hash source/firmware/SOF, laporan build dan screenshot **dari Quartus yang benar-benar menjalankan build tersebut**. Screenshot bukan pengganti laporan. Bitstream lama tidak boleh diberi label HWPE baru.

## Sumber primer

- [Ibex configurations](https://ibex-core.readthedocs.io/en/latest/02_user/configuration.html)
- [Ibex integration dan register-file FPGA](https://ibex-core.readthedocs.io/en/latest/02_user/integration.html)
- [CV32E40P extension reference](https://github.com/openhwfoundation/cv32e40p/blob/master/docs/source/instruction_set_extensions.rst)
- [CV32E40P sleep unit](https://docs.openhwfoundation.org/projects/cv32e40p-user-manual/en/cv32e40p_v1.2.1/sleep.html)
- [PULPissimo architecture dan HWPE support](https://github.com/pulp-platform/pulpissimo)
- [HWPE-Stream interface dan streamer IP](https://github.com/pulp-platform/hwpe-stream)
