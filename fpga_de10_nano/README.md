# GARDA DE10-Nano · Cyclone V 5CSEBA6U23I7

Untuk software workspace `../../src` yang memakai **74 → 128 → 64 → 3**,
gunakan **[src_policy/garda_src_policy.qpf](src_policy/garda_src_policy.qpf)** dan
[README pin planning serta arsitekturnya](src_policy/README.md).
Proyek `quartus/garda.qpf` di bawah adalah planner peta + neural legacy
**24 → 64 → 64 → 4**, dengan protokol berbeda. Jangan menukar bitstream.
Tiga file safety/protokol board sudah disamakan dengan source kanonik saat ini;
hasil kompilasi baru berada di `quartus/compile_current.log` dan
`quartus/output_files/`, sedangkan angka historis tetap merujuk bukti asalnya.

Top entity: **garda_uart_top**. Clock desain: **50 MHz**.

| Entry point | File |
|---|---|
| Quartus project | [quartus/garda.qpf](quartus/garda.qpf) |
| Programming image | [quartus/output_files/garda.sof](quartus/output_files/garda.sof) |
| Source | [rtl/](rtl) |
| ROM dan neural vectors | [assets/](assets) |
| Pin assignment | [quartus/pin_assignment.tcl](quartus/pin_assignment.tcl) |
| Host test | [host/garda_uart.py](host/garda_uart.py) |

Copy folder board ini secara utuh untuk menjaga source path dan ROM tetap tersedia. Buka QPF, pilih device/top yang sesuai, lalu gunakan Quartus Programmer untuk memuat SOF melalui JTAG.

Panduan lengkap: [Programming FPGA](../docs/FPGA_PROGRAMMING.md), [Quickstart](../docs/QUICKSTART.md), dan [Resource/timing](../docs/PERFORMANCE.md).

Host UART planner memakai **115200 8N1** dengan TTL 3,3 V. Gunakan port adapter FPGA yang sebenarnya. Reset KEY0 sebelum setiap DWA scene. ROM readback serta 100-vector neural check tersedia pada host script. Transport motor memakai project dan protocol terpisah.

Build evidence dan hash image tercantum pada [build_evidence.json](../evidence/build_evidence.json). Cakupan acceptance ada pada [Hasil dan cakupan](../docs/RESULTS_AND_SCOPE.md).
