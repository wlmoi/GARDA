# IHP SRAM integration

For the complete reproduction procedure, exact configuration and source
snapshots, use the [SRAM implementation guide](SRAM_IMPLEMENTATION_GUIDE.md).

The ASIC stores firmware in one **RM_IHPSG13_1P_256x16_c2_bm_bist** macro.
Its 256 words of 16 bits provide 512 bytes, matching the existing host address
map and four-context scheduler. UART, SPI, and I2C firmware use the same storage.

## RTL and programming

[src/program_memory.v](../src/program_memory.v) connects the real macro.
[src/sram_256x16_bb.v](../src/sram_256x16_bb.v) supplies its synthesis declaration.
The instance becomes `program_store.i_sram` after flattening.

| Signal | Connection |
|---|---|
| A_CLK | Inverted core clock |
| A_MEN | rst_n |
| A_ADDR | Selected context PC or paused host word address |
| A_WEN | Protected host DATA write strobe |
| A_REN | Read when the write strobe is clear |
| A_DIN | Host byte replicated into both byte lanes |
| A_BM | 0x00FF for low-byte writes or 0xFF00 for high-byte writes |
| A_DLY | Logic one |
| BIST inputs | Logic zero |

Falling-edge reads prepare instructions for rising-edge execution, preserving
the existing four-clock context cadence. Masked writes preserve the other byte.
Reset halts execution and retains memory contents. Load every reachable
instruction and literal before starting a newly powered device.

`JP_FPGA_SYNC_MEMORY` selects one ICE40 block RAM. `JP_REGISTER_MEMORY` selects
the register-array reference. The host interface and instruction set remain
consistent across these implementations.

## Physical views and placement

The configuration uses the installed PDK's SRAM LEF, GDS, CDL, and three
Liberty views. Tiny Tapeout's pinned IHP revision is
`2bbec755dc67ca3db0261c3d6163e15735d66710`. Its CMOS5L SRAM directory links
to the shared SG13G2 SRAM library.

The macro footprint is **236.8 by 118.78 micrometers**. Placement uses
orientation N at **(300.0, 34.02)** with an eight-micrometer placement halo.
This creates a 30.24-micrometer channel between its bottom-edge signal pins
and the core boundary. The installed LEF defines routing obstructions and
pin-access openings. The flow uses these shapes directly.
The standard Tiny Tapeout top-level interface and six-by-four tile allocation
remain in the project manifest.

The nominal views use typical 1.20 V at 25 C and slow 1.08 V at 125 C.
The flow's fast m40C corner selects the available SRAM fast 1.32 V m55C
characterization. Review this temperature pairing alongside full-flow timing
qualification for the selected shuttle. Both memory input and execution paths
have a half-cycle timing budget.

## Power integration

The macro exposes VDD!, VDDARRAY!, and VSS! on Metal4. Both positive supplies
connect to VPWR and ground connects to VGND. Tiny Tapeout generates these
global supply names through VDD_PIN and GND_PIN. The standard-cell pins
VDD and VSS connect through the flow's global rules. The PDN scripts read
VDD_NET and GND_NET from LibreLane, keeping the grid and connectivity
checks aligned with its resolved supply configuration.

[src/sram_geometry.tcl](../src/sram_geometry.tcl) reads the supply-column
positions from the installed LEF, including the irregular middle band.
[src/pdn_cfg.tcl](../src/pdn_cfg.tcl) aligns 2.1-micrometer Metal4 stripes
with the macro and retains the ordinary standard-cell grid elsewhere.

The root LibreLane plugin inserts `Project.PowerProgramSRAM` immediately
after `OpenROAD.GeneratePDN`. [src/power_sram.tcl](../src/power_sram.tcl)
extends the 20 power and 20 ground columns through the macro abstraction
to the tile boundaries. Supply-connectivity errors stop the flow.

The SRAM LEF contains an abstract supply bar that can trigger the generic
overlap checker and Magic's abstract-macro DRC. The configuration disables
those checks and enables **KLayout DRC** for the assembled geometry.
LVS, power connectivity, and Tiny Tapeout precheck remain part of the flow.
This configuration follows the supplied guide's distinction between abstract
LEF supply geometry and the physical macro GDS.

## Verification evidence

- The complete 42-test SRAM regression passes, including differential execution
  and independent UART, SPI, and I2C waveform checks.
- Two dedicated SRAM tests use unchanged official IHP behavioral models and
  check masks, byte preservation, enables, output hold, edge timing, and reset.
- The mapped SRAM netlist passes the pin-only gate-level Makefile regression
  with official CMOS5L cell models and Tiny Tapeout Icarus 13.
- A real-LEF OpenROAD fixture passes both supply-connectivity checks after
  executing the repository's PDN and SRAM power scripts.
- The FPGA implementation rebuilds through routing and bitstream packing.

The local fixture validates supply geometry and connectivity. Commit `1649be6`
passes complete-chip LVS, KLayout DRC, Tiny Tapeout precheck, and gate-level
simulation in the [official CMOS5L SRAM run](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38425106175).
Final LVS, DRC, and power-grid error counts are zero. Timing closure at the
50 MHz target and board validation remain the next qualification stages.

## References

- [Tiny Tapeout memory guidance](https://tinytapeout.com/specs/memory/)
- [Pinned IHP SRAM library](https://github.com/IHP-GmbH/IHP-Open-PDK/tree/2bbec755dc67ca3db0261c3d6163e15735d66710/ihp-sg13g2/libs.ref/sg13g2_sram)
- [OpenROAD PDN generation](https://openroad.readthedocs.io/en/latest/main/src/pdn/README.html)
- [Area measurements](AREA_TIMING.md)
- [Verification details](VERIFICATION.md)

## Routing runtime and diagnostic artifacts

The previous build reached detailed routing and the hosted runner's six-hour
limit with about 4000 remaining spacing and short violations. The revised
floorplan gives the SRAM signal pins a wider escape channel and retains
the LEF's access windows. A 40% placement target spreads standard cells,
and global routing requires a congestion-free result before detailed routing.

Detailed routing uses two explicit threads and up to 20 optimization
iterations. DRC reports are saved every five iterations. The normal detailed
routing, KLayout DRC, LVS, and Tiny Tapeout precheck acceptance checks
continue to qualify the result. A finite search budget preserves useful
failure reports for the next correction.

The GDS build step has a 150-minute limit inside a 180-minute job, reserving
time for the separate diagnostic upload. The gds-diagnostics artifact includes
logs, routing reports, configuration, guides, and OpenROAD databases even
when the build step fails. New runs replace older runs on the same branch.
Successful builds provide the submission and viewer artifacts as usual.

## LVS interface

[src/sram_256x16_lvs.spice](../src/sram_256x16_lvs.spice) provides an abstract
109-pin interface derived from the official LEF. Contiguous descending bus
order enables Netgen vector inference. EXTRA_SPICE_MODELS loads this view
before the powered top-level netlist. This checks integration wiring around
the foundry macro.

The plugin replaces Netgen.LVS with Project.ProgramSRAMLVS and retains the
normal Checker.LVS. A local input copy normalizes only the SRAM's escaped
VDD!, VDDARRAY!, and VSS! pin tokens for Netgen's Verilog reader. All nodes,
connections, and original flow netlists are preserved.

When Netgen emits unsupported identifier escapes in its JSON report, the
compatibility handler retains the raw file as lvs.netgen.json.original and
repairs the escape encoding before the standard metrics parser runs.
Structural errors and circuit mismatches continue to fail validation.
Diagnostic artifacts include the original JSON and adapted LVS input.

Local Netgen interface checks pass for correct wiring and reject an array
supply connected to ground. Complete-chip LVS remains part of the official
physical-flow acceptance checks.

## Signal-pin clearance

Run 38401026075 placed SRAM-aligned power columns across the fixed Metal4
signal-pin bank. The actual reports showed 16 M4.b spacing/notch violations
at the top edge and signal nets merged into VPWR and VGND during extraction.

The macro origin is now (300.0, 34.02) micrometers. Its supply columns are
outside the fixed I/O bank. The shared geometry helper checks every Metal4
signal boundary-pin rectangle with 0.5-micrometer clearance. A conflicting
macro location stops the flow. Ordinary grid columns skip these corridors.

Run 38420015169 cleared the power-grid checker and KLayout DRC. Its remaining
LVS shorts exposed a flow-order dependency. Classic applied the official DEF
template after PDN generation, so the signal pins had no coordinates when
the ordinary columns were selected. The configuration now applies that
template immediately before PDN generation. The geometry helper requires
placed signal pins before calculating either set of supply columns.

After extension, both supply checks must pass before the step refreshes
the power-grid violation metrics. The earlier failed grid describes the
pre-extension geometry. The final checker reads the verified extended result.

The old position fails the local guard. The new position passes with the
complete mapped engine and all 43 Tiny Tapeout pins. Program word addresses
remain 0 through 255, independent of the macro's layout origin.
