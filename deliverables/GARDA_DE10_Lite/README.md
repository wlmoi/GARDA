# GARDA on the Terasic DE10-Lite

The complete GARDA FPGA design, built for the **Terasic DE10-Lite (Intel/Altera MAX 10
10M50DAF484C7G)**: DWA motion planner with 4 rollout tiles, neural core 24-64-64-4,
hardware safety gate, UART command interface, E-stop and watchdog. It comes with a local
**FPGA Control Center** that programs the board, talks to it over UART and runs a judge demo.
A VGA monitor plugged into the board shows the live safety state.

This target is separate from the DE10-Nano (Cyclone V) build. No DE10-Nano bitstream,
pin file or memory primitive is reused.

Current hardware status and the evidence for each claim: **[reports/VERIFICATION_REPORT.md](reports/VERIFICATION_REPORT.md)**.

## What is deployed

| Block | Source | Changed? |
|---|---|---|
| Planner (`garda_top`, 4 × `garda_rollout_tile`, selector, costmap banks) | `rtl/garda_core/` | no, byte-identical (SHA-256 in `rtl/CORE_SHA256SUMS.txt`) |
| Neural core 24-64-64-4 + weight ROM | `rtl/garda_core/` + `assets/neural_24_64_64_4/` | no |
| Safety gate, status logger, UART RX/TX/protocol, CRC-8 | `rtl/garda_core/` | no |
| UART top | `rtl/de10_lite/garda_lite_uart_top.v` | copy of `garda_uart_top` with **additions only** (opcodes 0x20–0x29, host E-stop, watchdog, E-stop capture). Shown cycle-identical on legacy traffic by `sim/tb_lockstep.v` |
| Board top, HEX/LED, safe-reset receiver, VGA screen | `rtl/de10_lite/` | new |

Resources (release build): see `output/build_manifest.json`, about 44 % of logic
elements, 63 % of M9K memory bits, 19 of 288 9-bit multipliers, no PLL. The full design fits, so nothing was cut down.

## Quick start

1. **Wire the UART** as in [docs/WIRING.md](docs/WIRING.md): adapter TX → JP1 pin 1,
   adapter RX → JP1 pin 2, GND → pin 12, 3.3 V levels, red 5 V wire left open.
2. **Plug in** the DE10-Lite USB cable (power + USB-Blaster) and optionally a VGA monitor.
3. Start the Control Center:
   * genuine FTDI / CP210x / CH340 adapter: `START_CONTROL_CENTER.bat`
   * clone PL2303 ("THIS IS NOT PROLIFIC PL2303"): `START_CONTROL_CENTER_WSL.bat`
     (once, as Administrator: `usbipd bind --hardware-id 067b:2303`)
   * no hardware, simulation replay only: `START_SIMULATION_VIEW.bat`
4. In the browser (http://127.0.0.1:8770):
   * **PROGRAM FPGA & RUN UART TEST**: checks Quartus, the `.sof` and the JTAG chain, asks you to
     type the target IDCODE `031050DD`, programs over JTAG, then runs the full UART test.
   * **RUN DEMO ONLY**: same tests on an already programmed board.
   * **JUDGE DEMO MODE**: full-screen narrated version (English + Indonesian).
   * Data source: **LIVE HARDWARE**, **RECORDED HARDWARE TRACE** (saved automatically
     from earlier live runs) or **SOFTWARE SIMULATION** (RTL simulation replay, clearly labelled).

The website on Vercel/GitHub Pages cannot reach Quartus or the USB-Blaster. Programming
always goes through this local bridge, which listens on 127.0.0.1 only.

## Build from source

```
python scripts/build.py --quartus D:\OldQuartus\quartus\bin64      (or BUILD.bat)
```

Needs Quartus Prime **Lite** (free, MAX 10 device support) or a licensed Standard edition.
The script stamps a BUILD_ID, which the FPGA reports over UART so the Control Center can
confirm the board runs the file on disk. It also compiles and parses fit and timing
reports into `output/build_manifest.json`. It promotes the `.sof` to `release` only if timing is met at every corner.

## Verification

```
python scripts/check_pins.py            # every QSF pin vs the DE10-Lite manual table
python scripts/run_sim.py               # RTL regressions (Icarus Verilog), ~45 min total
python host/test_host.py -v             # protocol, link states, sequences, JTAG guards, service security
```

## Folder map

```
quartus/     project (.qpf/.qsf/.sdc)            rtl/garda_core/   unmodified GARDA RTL
rtl/de10_lite/  DE10-Lite integration RTL        assets/           neural weights + golden vectors
sim/         testbenches                         host/             UART library, Quartus guard, local service
dashboard/   Control Center web UI               scripts/          build, pin check, VGA generator, sim runner
output/      .sof / .pof / build_manifest.json   reports/          Quartus reports, sim logs, verification report
docs/        wiring, protocol, known issues      logs/ traces/     UART packet logs and recorded hardware traces
```

Safety of the data and control flow (every host→motor path and its guard): [docs/SAFETY.md](docs/SAFETY.md).

Known issues: [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).
