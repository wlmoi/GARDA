# GARDA real RISC-V control + Parallel16 self-test

This experiment boots the **unmodified upstream PicoRV32 CPU RTL**, reads actual RISC-V instructions from an 8 KiB boot ROM, uses 1 KiB of data RAM, and controls GARDA's 16-lane neural accelerator through the existing request/response MMIO adapter. It is a CPU integration and FPGA board self-test. It has no UART, motor output, robot safety gate, DMA or TCDM fabric.

The CPU is configured as **RV32IC**, with counters, multiplication and division disabled; the sixteen neural MAC lanes perform the multiply work. PicoRV32's upstream `maskirq`, `waitirq` and `retirq` custom instructions provide interrupt handling. This IRQ extension is not the RISC-V Privileged ISA `WFI`/machine-interrupt mechanism. The upstream README documents it.

Ibex remains a useful alternative, but its current integration requires a substantially larger SystemVerilog/FuseSoC primitive dependency closure. PicoRV32 provides an actual compact CPU and straightforward Icarus verification here. This choice does not establish minimum power or benchmark equivalence to Ibex. There is no PicoRV32 vendor power claim in this project.

## Reproduce the verified simulation

```sh
python fpga/riscv/firmware/build_firmware.py --check
python fpga/riscv/run_test.py
```

Put `iverilog` and `vvp` on PATH. The script requires only Python's standard library; it selects the correct directory for the sixteen bank files. `firmware/build_firmware.py` is a small deterministic instruction encoder, not a CPU emulator. The CPU itself executes the resulting `boot.hex`. `boot.S` shows each instruction and machine encoding. No cross compiler is required for this limited self-test firmware.

The firmware loads three independently generated fixture frames (indices 0, 1 and 17), writes all 74 inputs per frame, starts inference, and waits for the actual accelerator IRQ on input 4. The handler checks completed/fault status, the 3,556-cycle accelerator counter and all three signed Q8.8 outputs, then writes and reads them through the RAM bus. It resets the accelerator before returning from the interrupt. After three frames it writes signature `0x600d600d`; a mismatch writes `0xbad00001`.

The separate testbench checks actual instruction fetches, all **222 CPU input writes, 3 starts, 9 output reads and 3 IRQ handler entries**, the nine RAM results, and more than 9,000 clock cycles of `waitirq` with no CPU fetch request. A second run corrupts an expected output in ROM and requires the firmware to report failure. A separate fault-injection test verifies rejection of misalignment, partial MMIO write strobes, ROM writes, unmapped addresses, MMIO instruction fetches and adapter error responses. Only this separate bridge test uses forced bus stimulus; the main CPU/firmware test does not.

`cpu-regression.json` records measured simulation counters and SHA-256 hashes using canonical LF for project text. Upstream files also have exact raw-byte hashes in `vendor/picorv32/UPSTREAM.json`. The complete 236-vector/708-output adapter regression remains in `../hwpe/run_test.py`; three CPU frames do not replace it.

## Address map

| Range | Purpose |
| --- | --- |
| `0x00000000–0x00001fff` | 8 KiB read-only boot ROM and fixture constants |
| `0x10000000–0x100000ff` | GARDA HWPE register window; see [register map](../hwpe/README.md) |
| `0x20000000–0x200003ff` | 1 KiB data RAM |
| `0x30000000` | self-test signature write |

All local accesses are aligned full words. The bridge also rejects instruction fetches from MMIO/RAM and latches `bus_fault`; unknown operations cannot silently succeed. The CPU's native port has no bus-error input, so the sticky fault indicator invalidates PASS and appears on an LED.

## Isolated DE10-Nano project

```sh
python fpga/riscv/prepare_quartus.py
cd fpga/riscv/quartus
quartus_sh --flow compile garda_riscv
```

The project targets **5CSEBA6U23I7**, with the accepted DE10-Nano clock, KEY and LED pins, a 20 ns clock constraint and synchronized reset release. `prepare_quartus.py` stages exact copies of the sixteen model banks; those copies and build products are ignored by Git. The immutable firmware remains in `../firmware/boot.hex`. Either KEY button holds the self-test in reset. No hardware programming is performed by these scripts.

| LED | Meaning |
| --- | --- |
| 0 | synchronized reset released |
| 1 | firmware PASS signature accepted |
| 2 | CPU trap or sticky bus fault |
| 3 | firmware completed with a FAIL signature |
| 4 | accelerator IRQ |
| 5 | CPU IRQ acknowledgement |
| 6–7 | zero |

**Bitstream build is currently blocked:** the installed Quartus Prime Standard evaluation reports error 292037, “30-day evaluation period has expired”, before compilation. No `.sof`, fitted-area result, timing acceptance or physical-board result is claimed for this integrated design. A valid license or an applicable licensed/free Quartus installation is needed to run this project. The separate Parallel16 and CPU RTL simulation receipts remain valid within their stated scope.

This image is a diagnostic only. Connecting a CPU/accelerator to actuators requires independently verified watchdog, E-stop and command-permission interlocks. `waitirq` reduces instruction fetch activity in this simulation; it does not by itself prove clock gating, a power reduction or minimum power on silicon.

## Upstream attribution

[PicoRV32](https://github.com/YosysHQ/picorv32) is pinned to commit `ef203c2b0a3fb793280f5114941416c425c5b461`. Its unmodified RTL, README and [ISC license](vendor/picorv32/COPYING) are included under `vendor/picorv32`. Project glue, firmware encoder and self-test logic are separate GARDA files.
