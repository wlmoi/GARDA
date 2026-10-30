# Deliverables, acceptance dan runbook

Seluruh path relatif root repository. Daftar file lengkap berada di DELIVERABLES_ALL.md dan inventory JSON/CSV; isi dokumen lengkap ada di DOCUMENTATION_*.md. Status di sini merujuk bukti tersimpan, bukan hasil menjalankan ulang semua pekerjaan pada tanggal snapshot.

## Paket deliverable yang sudah tersedia

| Kelompok | Artefak utama | Cara menilai kesiapan |
|---|---|---|
| Software ROS | `src/`, `waypoint_list/`, launch/config/package.xml | build dan runtime sesuai final_docs; hardware device tetap harus diperiksa |
| Model dan numerical reference | weights/config/MEM, integer oracle, provenance scripts | cocokkan SHA, dimensi model, urutan bobot, format dan fixture |
| Core cepat | `fpga/experiments/parallel8/` | acceptance PASS, QSF source, STA positif 50 MHz |
| Baseline core | `fpga/rtl/igor_src_policy/`, board src_policy | 54.348 cycles; jangan dianggap varian <0,16 ms |
| Legacy planner/neural | `fpga/rtl/`, project quartus legacy | fungsi dan namespace fault berbeda; receipt per profil |
| Ready-to-open project | Parallel8 QPF/QSF/SDC, baseline dan legacy QPF | pilih varian yang cocok SOF; cek tool/device/pin |
| Ready-to-program | `fpga/bitstreams/igor_src_policy_parallel8.sof`, CDF, BAT | chain fisik terdeteksi dan hash accepted; SOF volatile |
| Pin planning | QSF, pin_assignment.tcl, board README | clock/reset/KEY/UART/LED fitted; JP1 bukan physical ASIC pinout |
| UART host | bridge, tests dan `docs/direct_uart_runbook.md` | nominal 921600, fixture exact Q8.8, CRC dan timeout |
| Ethernet/HPS | `src/igor_pipeline/`, `eth_direction.md`, `docs/connect_de10.md` | network-only terpisah dari backend inference; Linux + adapter diperlukan |
| Safety | gate RTL, host safety, FAULT_CODES, current_safety | error/status/zero-output harus cocok scope gate dan actuator host |
| Simulation | testbench, VCD/FST, GTKWave sessions, logs | assertions PASS + timestamp/signal relevan; gambar saja bukan oracle |
| Coverage | `fpga/evidence/rtl_coverage/` | native counters dan functional denominator; gaps transparan |
| Physical programming | current_programming receipt/logs | programming success terpisah dari UART function |
| Physical system | `docs/ethernet_validation/`, final_docs | 98/98 UART, wheels/sensors dan zero-motion pipeline; moving mission belum lengkap |
| Resource/timing | fitted summaries, STA, metric evidence CSV | profil/build/source identity sama, corner/unit jelas |
| FPGA power | Parallel8 artifacts/power; power.md | estimasi confidence Low, bukan rail measurement |
| ASIC | root RTL/info.yaml/config, IHP SRAM, imported GL/physical reports | protocol engine; semua sign-off gates perlu bukti sendiri |
| Visuals | PNG/SVG/native draw.io, source-bound provenance | editable bus widths dan FSM sesuai RTL |
| Publikasi/bisnis | Bennaya, CHIP_ADVANTAGES, achievements, tutorials | verified claim dipisah target, contoh dan asumsi biaya |
| CI | `.github/workflows/` | konfigurasi ada; status remote run harus dicek untuk commit tertentu |
| Knowledge agent | folder ini + ZIP | master context, full docs, exhaustive inventory dan hashes |

## CI dan reproduksi

Workflow executable: `test.yaml` menjalankan root unit/cocotb, cycle-model FPGA dan register reference; `rtl-verification.yml` menjalankan policy/UART/wrapper/safety dan pekerjaan terkait; `quartus-src-policy.yml` berisi alur Quartus; `fpga.yaml`, `gds.yaml`, `docs.yaml` melayani build FPGA, physical IHP/precheck/GL/viewer dan dokumentasi sesuai isi workflow. Template di `fpga/ci/` bukan otomatis workflow aktif.

Contoh perintah dari root untuk membaca/mereproduksi pekerjaan yang relevan:

```text
python fpga/verification/src_policy/run.py --check
python fpga/verification/run_board_wrapper.py
python tools/check_uart_rtl.py
python -m unittest discover -s test -p "test_*.py" -v
python fpga/scripts/check_igor_fsm.py
python fpga/scripts/build_agent_project_pack.py
```

Sebagian test menulis evidence; gunakan working tree bersih atau branch kerja dan review diff. Pilih command Parallel8 dari README experiment untuk core cepat: command baseline tidak otomatis memverifikasi source Parallel8. Cocotb memerlukan requirements, Icarus dan make sesuai workflow; Quartus build memerlukan Cyclone V support/tool/license. GDS memerlukan toolchain dan PDK IHP yang sesuai, tidak digantikan oleh simulator FPGA.

Untuk programming, baca `fpga/docs/BOARD_PROGRAMMING.md`, `FPGA_PROGRAMMING.md`, `fpga/bitstreams/README.md` dan script `program_fpga.ps1`. Hubungkan power/JTAG, identifikasi chain, pilih FPGA bukan HPS, verifikasi SOF accepted. Untuk physical UART tanpa motor, ikuti direct_uart_runbook. Perintah launch robot yang mengaktifkan driver motor membutuhkan persiapan hardware dan acceptance sensor/STOP; tidak dijalankan oleh pembuatan paket ini.

## Acceptance berikutnya: deliverables yang mungkin diperlukan

Item berikut adalah kebutuhan lanjutan, bukan klaim sudah selesai:

- Robot: repeated inference under ROS load, freshness contract sesuai sensor aktual, complete four-wheel STOP evidence, measured-pose mission 5×4 m, retry/fault recovery, telemetry dan timestamp sinkron.
- Performance: physical start/done capture, sustained throughput end-to-end, latency distribution/p99, host-load/thermal scenarios; simpan clock, baud, fixture, instrument dan raw log.
- Power: representative workload VCD/SAIF + post-fit activity mapping/confidence, rail-current measurement idle/active, voltage/temp dan uncertainty; pisahkan fabric, HPS, board dan motor.
- RTL improvement: bit-accurate oracle, weights/bias range audit, accumulator overflow bounds, banking/scheduling/width alternatives, synthesis/place-route dan regression per kandidat; accepted image tetap tersedia.
- ASIC NN: mapped neural top, library/corners/memory macros, constraints, physical implementation, extracted timing/power dan test pada netlist yang sama. Angka ASIC protocol engine tidak mengisi kekosongan ini.
- Tapeout: reproducible source/netlist/GDS identity, DRC/LVS/antenna, setup/hold semua corner, electrical DRV, legal placement, precheck, gate-level/SDF sesuai flow, reviewed waivers, IO/power/test plan dan shuttle submission evidence.
- Security: threat model, misuse/fault matrix, CRC vs authentication distinction, reset/timeout/illegal-state/replay tests sesuai protokol, logs traceable; certification memerlukan proses dan audit tersendiri.
- Business: dated official shuttle quote, kurs IDR, packaging/PCB/testing/shipping/tax, NRE vs unit-cost, yield/volume assumptions, delivery milestones dan customer use cases.
- Release: per-profile source-bound receipt, clean reproducible build, binary SHA, pinout, programming instructions, license/dependency inventory, CI run URLs dan hardware acceptance summary.

## Kelengkapan snapshot dan keterbatasan

Generator mengambil semua dokumen Markdown/RST tracked first-party tanpa meringkas atau menghapus isinya, lalu menambahkan katalog seluruh file project tracked. Inventory mencatat byte working tree sehingga modifikasi lokal evidence tercakup sebagai snapshot, bukan commit baru. File external, untracked, dependency environments, cache, reference repo lokal dan binary payload tidak diunggah sebagai teks penuh. Source/binary tetap ditemukan melalui path dan hash inventory.

ZIP ini adalah paket pengetahuan portable, bukan backup clone Git/LFS, bukan toolchain installer dan bukan archive fabrikasi. Untuk reproduksi source/binary lengkap gunakan checkout commit beserta Git LFS dan dependency yang ditentukan. Agent dapat memakai context ringkas terlebih dahulu dan mengambil isi dokumen penuh per area saat diperlukan.
