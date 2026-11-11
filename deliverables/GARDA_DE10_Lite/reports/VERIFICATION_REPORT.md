# GARDA DE10-Lite: verification report

Status date: 2026-11-11. Each line states what was actually run and where the evidence is.
Hardware results come from the real DE10-Lite. Simulation results come from Icarus Verilog.

## Overall status

| Item | Status |
|---|---|
| FPGA | **PROGRAMMED.** Release build `0x6AF487A6`, JTAG IDCODE 0x031050DD, "Configuration succeeded" (`reports/program_final.log`) |
| Timing (release build) | **MET** at all corners: setup +1.321 / +2.985 / +12.928 ns, hold +0.332 / +0.285 / +0.151 ns. Core 45 MHz PLL (Fmax 47.84 MHz), VGA 50 MHz |
| Laptop UART (port A) | **VERIFIED ON HARDWARE** with build `0x6AF47A72`: full demo sequence PASS. The adapter later dropped off USB/IP, so the current release build has not yet been re-read over UART |
| Jetson UART (port B) | **NOT TESTED ON HARDWARE** (simulation only) |
| Board system simulation | **RERUN PENDING.** The last completed run had 57/63 checks pass and 6 fail. The fixes are in the RTL and testbench; the rerun had not finished at commit time |

## Hardware (real DE10-Lite, laptop UART at 115200 baud)

Build `0x6AF47A72`, demo sequence `RUN DEMO ONLY`, trace `traces/hw_20261111_215309.json`:

| Step | Result |
|---|---|
| Identify | PASS: interface v2, build ID read from the FPGA equals the build manifest, 45 MHz, 115090 baud |
| Safe reset | PASS: motor_enable=0, fault 5 |
| Corrupted CRC frame | PASS: rejected, link locked out, UART safe reset recovered it |
| Neural inference | PASS: 3 vectors × 4 outputs bit-exact, 18192 cycles = 404.3 µs |
| Planner | PASS: 16384-cell map uploaded (75 s), result in 7938 cycles, motor_enable=1 observed live |
| Safety intervention | PASS: E-stop while permitted, motor_enable dropped on the same clock edge (capture latency 0) |
| E-stop latch | PASS: latched, still latched after 200 ms, cleared only by deliberate safe reset |
| Link-loss watchdog | PASS: 120 ms silence > 20 ms timeout gives protective stop (fault 3) |
| Totals | 16515 frames sent, 16510 received, 5 timeouts (incl. the intentional CRC test), 0 CRC errors |

Neural command gate (opcode 0x2D) on the same build: 107/107 live FPGA inferences bit-exact against the Python
model. Outputs were clamped to [-1.00, +0.99]. A host E-stop forced Vx = Vy = ω = 0 with permit = 0.

## Simulation

| Test | Result | Log |
|---|---|---|
| Legacy UART contract (24 cases), original `garda_uart_top` | PASS | `reports/sim/legacy_uart_original.log` |
| Same test on `garda_lite_uart_top` | PASS, identical checkpoints | `reports/sim/legacy_uart_de10lite.log` |
| Lockstep equivalence vs. original top | PASS: 24.1 M cycles, 16725 frames, 12142 motor-enable cycles, 0 mismatches | `reports/sim/lockstep.log` |
| Board system test | Last completed run: 57/63. Rerun pending | `reports/sim/board.log` |
| Real 115200 baud host timing | Last completed run failed on the first IDENT. This is the arbiter reset-idle issue, fixed since then. Rerun pending | `reports/sim/baud_115200.log` |
| Python neural model vs. 400 golden outputs | 400/400 bit-exact | `host/garda_nn_model.py` |
| Host tests (protocol, link, sequences, JTAG guards, service security) | 18/18 PASS | `reports/host_tests.txt` |
| Pin assignments vs. DE10-Lite manual | PASS | `reports/pin_check.txt` |

The 6 board-test failures in the last completed run, and what changed:

1. The first frame after reset was ignored. This was an RTL arbiter bug: the idle counter started at 0. **Fixed:** the line counts as idle at reset.
2. Four checks were caused by the testbench switching between port A and port B with no gap, so the arbiter correctly treated the frames as collisions. **Fixed in the testbench:** a 40-bit pause on every port change.
3. One check, the SW3 test, ran while an earlier E-stop was still latched. **Fixed in the testbench:** a safe reset before the test.

## Not done or not verified

* The Jetson Nano on port B has not been tested on hardware.
* The current release build `0x6AF487A6` (GArdA 7-segment banner, arbiter fix) is programmed, but its UART link
  has not been read back yet. The PL2303 clone adapter dropped off USB/IP and Windows no longer listed it.
* The VGA monitor output was rendered from the RTL in simulation. It has not been checked on a physical monitor here.
* 921600 baud: RTL parameter only, not tested.
* `.pof` flash programming: not offered and not tested.
