# Verification

The local stdlib suite has passed 42 tests using Python 3.11 and Icarus Verilog
with ASIC SRAM. CI also selects FPGA block RAM and the register-memory
reference implementation:

```text
python -m unittest discover -s test -p "test_*.py" -v
```

Fourteen tests cover model/host behavior: round-robin and halt; all supported
branch conditions and signed offset boundaries; 255-grant waits; enable
freezing; literal wrap; masked open-drain updates; rejected encodings;
demo size/ownership; RTL/tool geometry consistency; literal pause/restart;
host frame endianness; readback/transport failures; UART baud selection and
firmware period bounds; and explicit firmware error signaling.

Eighteen RTL regressions use `test/integration_tb.v`. Each simulation loads and
reads back all 256 program words through the external SPI pins, including
high byte-address bits and wraparound. No hierarchical memory writes are used.
Execution is compared every clock against `tools/reference_model.py`: scheduler
slot, all PCs, X/Y, receive registers, wait counters, halted/errors, output
values, and output enables. The input synchronizer pipeline is modeled too.

RTL cases cover randomized programs with reproducible seed 20261007, four
contexts, randomized external pins and `ena` pauses; branch/literal boundaries;
UART TX wire decoding and UART RX reception; SPI MOSI edge decoding and MISO
reception; I2C address/data/ACK wire decoding with physical SCL stretching;
NACK-to-STOP; all four protocol contexts concurrently; live-write protection;
stop/restart/reset; and overlapping-mask rejection and reassignment; rejected live memory reads
and out-of-range host addresses. Immediate GPIO operations are also included
in randomized differential tests.

Simulation safety invariants check known outputs, disabled output release,
output enables confined to owned pins, and pairwise-disjoint ownership. These
are runtime assertions, not formal proofs. Randomized differential testing
checks model consistency but is not exhaustive; independent wire-level checks
help catch shared model/RTL misunderstandings.

Expanded UART cases check idle arming, short start-pulse recovery, low stop-bit
framing status through the host, 0x00/0xFF/0x55/0xAA patterns, programmable pins,
start phases, RX grant counts from 4 to 256, and TX counts from 3 to 257.
An independent peer varies its bit period from 424 to 440 clocks against a
432-clock receiver. The firmware sets a sticky error and halts on a low stop.

Set JP_TEST_FPGA=1 when running the stdlib suite to compile with
JP_FPGA_SYNC_MEMORY. Set JP_TEST_REGISTER=1 to select the register-memory reference. CI runs all three variants and compares each against the same
cycle model, covering host readback, literals, reset, protection, and the
concurrent UART/SPI/I2C demo.

## Local FPGA implementation evidence

The complete Tiny Tapeout FabricFox wrapper passed synthesis, placement,
routing, and bitstream packing for ICE40UP5K on 2026-10-11. The local build
used Yosys 0.33, nextpnr-ice40 0.6, seed 10, the official FabricFox v2 pin
constraints, and a 12 MHz timing target. The packaged routing tool used a
workspace-relative device-database lookup.

| Metric | Local routed result |
|---|---:|
| Logic cells | 2460 / 5280, approximately 46% |
| Program block RAM | 1 / 30 |
| Post-route clock estimate | 17.25 MHz |
| Timing target | 12 MHz, passed |
| Packed bitstream | 104090 bytes |

Logs, the JSON netlist, routed ASC, and packed binary are local artifacts
under `build/fpga-check/`. CI uses Tiny Tapeout's official FPGA action and
OSS CAD Suite, providing a separate build result for its tool versions.
The workflow checks that the bitstream is present and the netlist contains
exactly one program block RAM.

Protocol timing on an FPGA uses its supplied core clock. At 12 MHz, 26 grants
per UART bit gives approximately 115385 baud. Use uart_bit_grants with the
actual clock when generating a program for a board.

`test/test.py` is a pin-only cocotb test that programs the chip, reads memory
back, runs a GPIO program, rejects a live write, and releases pins on STOP.
The CI workflow runs the stdlib suite before the existing cocotb flow. A
matching gate netlist can use that pin-only test without hierarchical accesses.
The local pin-only cocotb test passed with cocotb 2.0.1 and Icarus Verilog 12.0
using `python -m tools.run_cocotb` (the Python runner does not require Make).

The locally mapped IHP netlist also passed the pin-only cocotb test using
zero-delay functional cell models generated from the mapping Liberty library:

```text
python -m tools.run_cocotb --netlist build/area/compact.v --cell-models build/area/compact-cells-functional.v
```

GitHub subsequently passed the Tiny Tapeout SG13G2 GDS build, precheck, gate-level
test, and viewer for commit `269b380`:
[physical-flow and gate-level results](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/37646552561).
The [RTL test workflow](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/37646552427)
also passed for that commit. These results establish CI success for the linked
revision; current workflow badges show later runs.

Formal properties have not been proved. SRAM layout sign-off, SDF timing
simulation, and board testing remain pending. See [area evidence](AREA_TIMING.md)
for the distinction between local mapping estimates and the physical-flow run.
The current ASIC workflow targets the competition's CMOS5L template and
matching gate-level models. The [CMOS5L CI run](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38068425041)
completed GDS generation and the viewer for commit `3c099bd`. The following
local checks validate the simulation and power-grid updates on 2026-10-11.

The current RTL was mapped with Yosys 0.33 against the CMOS5L typical 1.20 V,
25 C Liberty library. Its pin-only cocotb regression passed through
`GATES=yes make` and the results checker, using cocotb 2.0.1, Python 3.12,
and Tiny Tapeout's Icarus 13 package. The models match the action's pinned
[PDK revision](https://github.com/IHP-GmbH/IHP-Open-PDK/tree/2bbec755dc67ca3db0261c3d6163e15735d66710).
The Makefile includes `sg13cmos5l_udp.v` alongside the standard-cell and
IO models, providing the foundry flip-flop and multiplexer primitives.
These results cover functional gate-level behavior. SDF timing qualification
is a separate milestone.

Before SRAM integration, an isolated OpenROAD power-grid check used the official CMOS5L technology
and cell LEFs, the six-by-four tile dimensions, a 38.87 micrometer pitch,
and the configured 2.1 micrometer Metal4 width. The generated LEF contains
33 full-height straps on each supply at 2.1 micrometers, matching the
[Tiny Tapeout power-pin width requirement](https://github.com/TinyTapeout/tt-support-tools/blob/d66cf179e7bc4d296362ab7e2e3b344dc3c4f665/precheck/tech_data.py).
Logs, the mapped netlist, and result reports are local artifacts under
`build/cmos5l-check/`. The SRAM revision uses the LEF-aligned supply grid described below.
Full-layout routing, DRC, and precheck qualification follow in the next CI run.

Streaming traffic, parity, additional SPI modes, I2C reads/arbitration, and
board electrical timing are development milestones.

## SRAM integration checks

Two additional regressions use the unchanged official IHP behavioral models.
They exercise bit-mask writes, byte preservation, address 255, output hold,
memory enable, read enable, falling-edge reads, and reset retention. Together
with the twelve model tests and seventeen RTL tests, the protocol and memory suite contains 31 tests. Eight additional regressions
cover SRAM LVS input adaptation and Netgen JSON report compatibility.

The SRAM-backed mapped netlist passed the pin-only gate-level Makefile test
with Tiny Tapeout Icarus 13 and the official CMOS5L standard-cell models.
An OpenROAD fixture using the real SRAM LEF, Liberty, standard-cell LEFs,
and tile dimensions executed the repository PDN scripts. Both supply-net
connectivity checks passed, including VDD!, VDDARRAY!, and VSS!.

The fixture validates macro supply geometry and connectivity. The complete
placed and routed SRAM layout receives DRC, LVS, timing, and Tiny Tapeout
precheck qualification in the next physical-flow run.

The PDN supply-name regression uses LibreLane's actual set_power_nets.tcl
and set_global_connections.tcl with the Tiny Tapeout VPWR/VGND defaults,
the real SRAM, and a legally placed IHP inverter. Procedure-scoped PDN
generation and both supply-connectivity checks pass. The local OpenROAD
fixture adapts only the newer global_connect verbosity option to its older
command interface. This check exercises the standard-cell VDD/VSS pins and
all SRAM supplies together.

The PDN generation and SRAM extension checks also pass as two separate
OpenROAD processes with an ODB save and reload between them. The extension
process starts with VDD_NET and GND_NET absent and resolves them through
LibreLane's set_power_nets.tcl. Both supply checks pass after extension,
covering the same process boundary used by the GitHub flow.

## SRAM routing diagnosis on 2026-10-13

The supplied GitHub log reached detailed-routing iteration 47 with about
4000 spacing and short violations, then the six-hour hosted job limit.
The updated configuration moves the SRAM away from the bottom boundary,
uses an eight-micrometer placement halo, and uses the installed LEF's
routing obstructions and pin-access windows. Standard-cell placement targets
40% density.

A standalone OpenROAD check uses the complete Yosys-mapped design, inserted
tie cells, the official six-by-four DEF pin template, and the real CMOS5L
and SRAM physical libraries. The updated placement and both supply checks
pass. Global routing handles 4559 nets with zero overflow on Metal2,
Metal3, and Metal4. The standalone harness removes an empty synthetic
constant net created by its Verilog reader before detailed routing.

This check provides routing evidence for the revised floorplan. The official
flow also performs CTS, timing repair, extraction, assembled-layout DRC,
LVS, and Tiny Tapeout precheck. Those stages qualify a completed GDS build.

The standalone detailed-routing probe reached its early repair iterations,
with 5815 violations after the initial iteration. It was stopped during the
first repair iteration. It uses an older local OpenROAD and omits the
official flow's CTS and timing-repair stages, so it establishes pin access
and a partial routing result. Detailed-routing DRC closure and completed
GDS qualification remain requirements for the updated official build.

## SRAM LVS interface and report checks

The supplied run 38393577062 reached Netgen LVS in about 22 minutes. Netgen
created a placeholder SRAM cell and reported top-level pin mismatches. Its
JSON report also contained an invalid identifier escape, which interrupted
LibreLane's metrics parser.

The committed SPICE pin interface names all 109 physical LEF ports. Bus pins
use contiguous descending indices so Netgen can infer the full vector widths.
It is loaded before the powered top-level netlist through EXTRA_SPICE_MODELS.
The project LVS step adapts the SRAM's three escaped supply-pin tokens to
Netgen's input dialect in a separate file. The original powered netlist
remains available to every other flow step.

The JSON compatibility handler repairs unsupported identifier escapes,
preserves the original malformed report, and validates the repaired JSON.
Structural report errors still fail. LibreLane's existing mismatch metrics
and Checker.LVS remain active.

A real Netgen 1.5.270 fixture derived from the pinned SRAM LEF matches all
109 pins with zero LVS errors. Deliberately connecting VDDARRAY! to ground
produces 110 LVS errors. The scoped adapter also processes a real OpenROAD
powered netlist. Eight Python regressions cover supply-token isolation,
missing and duplicate instances, valid escapes, invalid escapes, preserved
mismatch data, and structural JSON failures.

These checks validate the SRAM interface and report handling. Complete-chip
LVS, routed timing, and Tiny Tapeout precheck qualify the updated official run.

An end-to-end fixture executes Project.ProgramSRAMLVS through LibreLane
Step.start with the real Netgen subprocess. Correct wiring reports zero
errors and the supply fault reports 110. Both runs preserve the original
powered-netlist reference in the returned flow state.

## Targeted SRAM programming and physical pin safety

The [official CMOS5L run for commit 1649be6](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38425106175)
passes GDS generation, Tiny Tapeout precheck, and gate-level simulation.
The final reports record zero LVS errors, zero KLayout DRC errors, and zero
power-grid violations. Netgen reports a unique circuit match. The same
revision passes RTL, FPGA, and datasheet workflows. Viewer publication runs
on the default branch.

A local replay of the complete routed engine reproduces the original
interface-pin shorts and passes LVS after selecting power columns with
placed pins. Its corrected layout and schematic each contain 5,330 devices
and 5,305 nets, with zero LVS errors.

The flow applies the official DEF template before PDN generation. Native
OpenROAD checks require placed signal pins, reject the original unplaced
interface, and verify zero overlaps between supply-pin rectangles and all
43 template signal pins. Both extended supply networks pass connectivity.

The 42-test suite includes host word readback and range checks before SPI
activity. An external-pin RTL regression patches word addresses 0, 127,
128, 254, and 255, changes individual bytes, and checks all 256 words
for preservation of untouched data.

The full reports from run 38401026075 identify boundary power-column shorts
and 16 M4.b errors. The updated geometry guard rejects that placement. A
new OpenROAD fixture includes all 43 official DEF signal pins and the complete
mapped engine. Both supply checks pass, and exported post-extension metrics
record zero power-grid violations.
