# Implementation status

The integrated top is `tt_um_igorchip` in `src/igorchip_top.v`,
with `src/program_host.v` providing its synchronized mode-0 SPI transport.
It implements four deterministic round-robin contexts; host-loadable 256 x
16-bit storage; X/Y and receive registers; full-byte cycle waits and pin waits;
conditional branches; masked push-pull/open-drain GPIO; synchronized inputs;
halt, stop/restart, status, and sticky errors. GPIO activity is no longer
modified by the earlier hardening activity accumulator.

The host can load/read back all 512 program bytes, configure disjoint output
ownership, and start contexts at different entry points. Live program writes
and ownership changes are rejected. Reset halts execution and releases pins.
HALT preserves outputs and host STOP releases them. Program storage uses the
IHP RM_IHPSG13_1P_256x16_c2_bm_bist SRAM macro. Reset retains stored words.
The host loads reachable firmware before execution. Its shared read port prepares
data on the falling core-clock edge. Host readback
requires software pause and literal loads consume two context grants.

Firmware and regression coverage demonstrate UART TX/RX with start-bit
qualification and framing status, SPI mode-0 byte
transfers, and single-master I2C writes with ACK/NACK and stretching. A packed
four-context program demonstrates concurrent operation. See [protocol scope](PROTOCOLS.md).

Python tools provide validated assembly encoders, a cycle model, a transport-
independent host driver, and demo-image generation. Tests compare RTL state
against the model every execution clock and independently inspect serial
waveforms. The CI test workflow runs both stdlib regressions and the pin-only
cocotb test. See [verification status](VERIFICATION.md) for actual run results.

Legacy standalone modules (`thread.v`, `host_if.v`, `prog_mem.v`, `dm.v`,
`gpio.v`, `bit_engine.v`, `edge_units.v`, `fifo.v`, and `timing.v`) remain
unconnected and are not in the Tiny Tapeout source list.

Local CMOS5L synthesis reports 58741.6914 um^2 of mapped logic plus a
28127.1040 um^2 SRAM footprint, totaling 86868.7954 um^2. This is approximately
77.4% smaller than the comparable 384634.2024 um^2 register-memory mapping.
Full-layout area and timing qualification are the next measurements.
See [area results](AREA_TIMING.md).

GitHub passed GDS hardening, precheck, gate-level simulation, and the viewer
on SG13G2 for commit `269b380`:
[passing Tiny Tapeout run](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/37646552561).
Detailed post-route area/timing metrics are not recorded here.

The current workflow follows the competition's CMOS5L template with
`TinyTapeout/tt-gds-action@ihp-cmos5l`, `pdk: ihp-sg13cmos5l`, and matching
CMOS5L gate-level simulation models. Commit `1649be6` passes SRAM-backed
GDS hardening, Tiny Tapeout precheck, and gate-level simulation:
[passing CMOS5L SRAM run](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38425106175).
The final metrics record zero LVS errors, KLayout DRC errors, and power-grid
violations. The viewer publishes from the default branch.

The FPGA workflow selects a falling-edge synchronous program read using
JP_FPGA_SYNC_MEMORY. It maps the same 256-word program store into one ICE40
block RAM while retaining rising-edge execution and the host register map.
The 42-test regression suite covers SRAM, FPGA, and register-memory variants.
SRAM bit-mask and byte-write tests use the official IHP behavioral models.
The mapped SRAM design passes the pin-only gate-level test. Local OpenROAD
checks confirm connected SRAM supply columns. See [SRAM integration](SRAM.md).

Next verification milestones include timing closure at 50 MHz, formal proof, board testing,
streaming FIFOs, automatic pin-wait timeouts, trace capture, and advanced
protocol modes. The linked CI result applies to that commit; later RTL changes
must pass the flow again.
