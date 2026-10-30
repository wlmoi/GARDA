# Reproducible SRAM integration guide

**Target:** Tiny Tapeout IHP SG13CMOS5L, LibreLane, one 256 x 16-bit program SRAM.

**Reference date:** 14 October 2026.

This guide specifies the implementation used by the programmable UART, SPI,
and I2C engine in this repository. It includes the working source revision,
macro views, RTL contract, simulation setup, physical configuration, power
connections, LVS compatibility, host programming, acceptance checks, and
failure recovery. The source snapshots at the end provide the complete
integration files.

An agent should reproduce the reference implementation first, then adapt one
dimension at a time and rerun the affected acceptance stages. Treat the exact
macro, hierarchy, process, units, supply names, and clock phase as a single
integration contract.

## Contents

1. [Passing reference and completion criteria](#1-passing-reference-and-completion-criteria)
2. [Files and ownership](#2-files-and-ownership)
3. [Prepare the environment](#3-prepare-the-environment)
4. [Verify the macro views](#4-verify-the-macro-views)
5. [Implement the RTL contract](#5-implement-the-rtl-contract)
6. [Compile the correct simulation models](#6-compile-the-correct-simulation-models)
7. [Configure the physical macro](#7-configure-the-physical-macro)
8. [Place interface pins before the power grid](#8-place-interface-pins-before-the-power-grid)
9. [Connect all SRAM supplies](#9-connect-all-sram-supplies)
10. [Run integration LVS](#10-run-integration-lvs)
11. [Program an exact SRAM address](#11-program-an-exact-sram-address)
12. [Run the full verification sequence](#12-run-the-full-verification-sequence)
13. [Build GDS and preserve diagnostics](#13-build-gds-and-preserve-diagnostics)
14. [Publish and verify the viewer](#14-publish-and-verify-the-viewer)
15. [Qualify timing and external interfaces](#15-qualify-timing-and-external-interfaces)
16. [Diagnose failures by stage](#16-diagnose-failures-by-stage)
17. [Adapt the design to another macro](#17-adapt-the-design-to-another-macro)
18. [Agent handoff and evidence record](#18-agent-handoff-and-evidence-record)
19. [Source snapshots and integrity manifest](#19-source-snapshots-and-integrity-manifest)

## 1. Passing reference and completion criteria

Use this immutable source revision as the reference:

~~~text
Repository: https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet
Commit: b08afad42ed7179eee4a276634ee7b4cefae4f6c
Top: tt_um_igorchip
Macro: RM_IHPSG13_1P_256x16_c2_bm_bist
Flattened instance: program_store.i_sram
PDK: ihp-sg13cmos5l
PDK source commit: 2bbec755dc67ca3db0261c3d6163e15735d66710
Tiny Tapeout action commit: 3412659307918422f3f0727917cf9b499aaca588
tt-support-tools commit: d66cf179e7bc4d296362ab7e2e3b344dc3c4f665
LibreLane: 3.1.0.dev3
~~~

The [reference main-branch GDS run](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38483354858)
passes hardening, Tiny Tapeout precheck, gate-level simulation, and viewer
deployment. The same revision passes
[RTL tests](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38483354928),
[FPGA implementation](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38483354863),
and [documentation generation](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38483354909).

The preceding [SRAM integration run for 1649be6](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38425106175)
also passes hardening, precheck, and gate-level simulation. Its final reports
record zero LVS errors, zero KLayout DRC errors, and zero power-grid
violations. Its viewer job is intentionally gated to the default branch.

| Acceptance stage | Required evidence |
|---|---|
| Memory behavior | Foundry-model mask, byte preservation, enable, clock-edge, and reset tests pass |
| Engine behavior | Cycle differential tests and independent UART, SPI, and I2C peers pass |
| Synthesis | Exactly one physical SRAM instance remains in the ASIC netlist |
| Placement | Correct master, N orientation, legal footprint, halo, and placed interface pins |
| Power | All three macro supplies have the intended nets and both extended grids pass connectivity |
| Layout | Detailed routing and KLayout DRC pass |
| Connectivity | Netgen reports a unique circuit match and the normal LVS checker passes |
| Submission | Tiny Tapeout precheck and the generated-netlist simulation pass |
| Viewer | Deployment succeeds and the published model contains the SRAM |
| Timing qualification | Setup, hold, slew, and capacitance meet the intended operating conditions |
| Board qualification | Actual programming and protocol waveforms are measured on the selected hardware |

The passing physical flow establishes the geometry and integration stages.
Timing repair at the 50 MHz target and board measurements are separate
qualification stages. Keep these distinctions in every status report.

The reference uses 256 instruction words, totaling 512 bytes. Four execution
contexts share this single physical memory port.

## 2. Files and ownership

| File | Role |
|---|---|
| [info.yaml](../info.yaml) | Tiny Tapeout top, tile allocation, pin descriptions, and RTL manifest |
| [src/igorchip_top.v](../src/igorchip_top.v) | Scheduler, instruction execution, host registers, address arbitration, and write protection |
| [src/program_host.v](../src/program_host.v) | Synchronized host SPI transport |
| [src/program_memory.v](../src/program_memory.v) | Physical macro wrapper and alternate FPGA/reference implementations |
| [src/sram_256x16_bb.v](../src/sram_256x16_bb.v) | Synthesis black-box declaration |
| [src/defines.vh](../src/defines.vh) | Eight-bit program address width |
| [tools/config.py](../tools/config.py) | Matching Python program depth of 256 |
| [src/config.json](../src/config.json) | Macro views, corners, placement, flow substitutions, and physical checks |
| [src/sram_geometry.tcl](../src/sram_geometry.tcl) | Actual LEF power-column extraction and interface-pin clearance guards |
| [src/pdn_cfg.tcl](../src/pdn_cfg.tcl) | Standard-cell rails and SRAM-aligned Metal4 stripes |
| [src/power_sram.tcl](../src/power_sram.tcl) | Supply extension through the macro abstraction and connectivity checks |
| [librelane_plugin_program_sram.py](../librelane_plugin_program_sram.py) | Registered LibreLane power and LVS steps |
| [src/sram_256x16_lvs.spice](../src/sram_256x16_lvs.spice) | Complete abstract physical pin interface for integration LVS |
| [tools/netgen_json.py](../tools/netgen_json.py) | Scoped Netgen input and report compatibility |
| [test/ihp_sram/README.md](../test/ihp_sram/README.md) | Provenance of the unchanged foundry simulation models |
| [test/test_sram.py](../test/test_sram.py) | Macro and wrapper behavior tests |
| [test/test_rtl.py](../test/test_rtl.py) | Engine differential, protocol, and host-access tests |
| [test/test_netgen_json.py](../test/test_netgen_json.py) | LVS compatibility tests |
| [test/Makefile](../test/Makefile) | RTL and gate-level simulation source selection |
| [tools/host.py](../tools/host.py) | Bounded load, verification, readback, and context control |
| [.github/workflows/gds.yaml](../.github/workflows/gds.yaml) | Hardening, diagnostics, precheck, gate-level simulation, and viewer |
| [.github/workflows/test.yaml](../.github/workflows/test.yaml) | Three storage-variant regressions and pin-only cocotb |
| [.github/workflows/fpga.yaml](../.github/workflows/fpga.yaml) | ICE40 block-RAM selection and bitstream checks |

Preserve the relationships between these files. Changing only the macro
instantiation leaves the physical views, supply routing, and LVS interface
unfinished.

The source snapshots cover the SRAM integration layer. The immutable
repository revision supplies the surrounding engine, host transport,
firmware tools, test peers, and Tiny Tapeout metadata.

Use the active manifest and `src/igorchip_top.v` to determine implemented
behavior. The source directory also contains earlier standalone modules
retained for history. The active instruction encodings are implemented in
the current top and `tools/assembler.py`.

## 3. Prepare the environment

### 3.1 Reproduce in a fresh checkout

Run these Bash commands in a fresh Linux directory:

~~~bash
git clone https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet.git protocol-asic-sram
cd protocol-asic-sram
git checkout --detach b08afad42ed7179eee4a276634ee7b4cefae4f6c
git status --short
git rev-parse HEAD
~~~

Expected: a clean working tree and the exact reference commit. A fresh
checkout preserves work in another checkout. For development, create an
ordinary working branch after recording the reference revision.

Use a simple Linux path such as `/home/user/protocol-asic-sram` for physical
tools. Several upstream Tcl and subprocess command generators are sensitive
to whitespace in paths. Windows can run the RTL and host tests with Python,
Icarus Verilog, and `vvp` on `PATH`.

### 3.2 RTL tools

The test environment uses Python 3.11 or later, Icarus Verilog, and cocotb
2.0.1. Install the repository requirements:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r test/requirements.txt
python --version
iverilog -V
vvp -V
~~~

On PowerShell:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r test/requirements.txt
.\.venv\Scripts\python.exe --version
iverilog -V
vvp -V
~~~

The reference CI uses Ubuntu 24.04. The physical action supplies the
LibreLane tool environment. Recorded hardening tools include Yosys 0.66,
Magic 8.3.674, and Netgen 1.5.320. Local area estimates in the older
measurement notes use Yosys 0.33, and selected local LVS fixtures use Netgen
1.5.270. Keep local fixture versions separate from the CI flow versions.

Magic's pinned CMOS5L technology file requires a sufficiently recent
extractor. The recorded 8.3.674 version satisfies that requirement. Fetch
the complete technology setup, including its include files.

### 3.3 Recommended physical build route

Use the existing GitHub GDS workflow for the reference acceptance run.
It installs the applicable PDK, generates the Tiny Tapeout configuration,
and invokes the supported LibreLane container flow.

The action's `ihp-cmos5l` ref is a moving branch. The passing reference
resolved it to `3412659307918422f3f0727917cf9b499aaca588`. For an immutable
reproduction in a separate repository, use that SHA in the action reference.
Record the resolved action and support-tool SHAs for later runs.

### 3.4 Optional local physical build

Install Docker using its official installation procedure and verify that
`docker info` succeeds. The pinned support tool invokes LibreLane's
container mode by default. Its `--no-docker` option is for an environment
that already provides the matching native EDA tools.

From the fresh repository root:

~~~bash
git clone https://github.com/TinyTapeout/tt-support-tools.git tt
git -C tt checkout --detach d66cf179e7bc4d296362ab7e2e3b344dc3c4f665
git clone https://github.com/TinyTapeout/tt-gds-action.git build/action-reference
git -C build/action-reference checkout --detach 3412659307918422f3f0727917cf9b499aaca588
python -m pip install -r tt/requirements.txt
python -m pip install librelane==3.1.0.dev3
export PDK_ROOT="$PWD/build/pdk-reference"
export PDK=ihp-sg13cmos5l
bash build/action-reference/install_sg13cmos5l.sh
./tt/tt_tool.py --create-user-config --ihp
~~~

Choose an empty, dedicated `PDK_ROOT`. The pinned installer initializes an
IHP-Open-PDK Git checkout there and selects its exact source revision. It
creates `ihp-sg13cmos5l/SOURCES` with the provenance.

The generated `src/user_config.json` supplies the top, source files, die
area, official pin template, `VPWR`, and `VGND`. The support tool merges it
with `src/config.json` into `src/config_merged.json`.

Expected after configuration generation:

~~~text
DESIGN_NAME = tt_um_igorchip
VDD_PIN = VPWR
GND_PIN = VGND
FP_DEF_TEMPLATE = the supplied six-by-four Tiny Tapeout DEF
VERILOG_FILES = the active info.yaml source manifest
~~~

The local hardening command is:

~~~bash
./tt/tt_tool.py --harden --ihp
~~~

The support tool creates a fresh `runs/wokwi` for each hardening invocation.
Archive needed reports and layout files before repeating that command.
Run configuration generation and hardening from the repository root.

## 4. Verify the macro views

The pinned installer fetches the complete IHP-Open-PDK repository. Its
`ihp-sg13cmos5l/libs.ref/sg13cmos5l_sram` directory links to the shared
SG13G2 SRAM library. Keeping both process directories makes that link resolve.

Required installed files, relative to the CMOS5L SRAM directory:

~~~text
lef/RM_IHPSG13_1P_256x16_c2_bm_bist.lef
gds/RM_IHPSG13_1P_256x16_c2_bm_bist.gds
cdl/RM_IHPSG13_1P_256x16_c2_bm_bist.cdl
lib/RM_IHPSG13_1P_256x16_c2_bm_bist_typ_1p20V_25C.lib
lib/RM_IHPSG13_1P_256x16_c2_bm_bist_fast_1p32V_m55C.lib
lib/RM_IHPSG13_1P_256x16_c2_bm_bist_slow_1p08V_125C.lib
~~~

Each view serves a different purpose:

| View | Purpose |
|---|---|
| LEF | Footprint, physical pin names, pin rectangles, and routing obstructions |
| GDS | Fabrication geometry included in the assembled layout |
| Liberty | Timing arcs, pin capacitances, clock relationships, and operating corners |
| CDL | Official macro circuit view and provenance |
| Behavioral Verilog | Clocked functional simulation and bit-mask behavior |
| Synthesis declaration | A retained hard macro with named functional ports |
| Abstract LVS SPICE | Physical port declaration for checking integration connections |

Run this check after installing the PDK:

~~~python
import os
import re
from pathlib import Path

macro = "RM_IHPSG13_1P_256x16_c2_bm_bist"
root = Path(os.environ["PDK_ROOT"]) / "ihp-sg13cmos5l"
sram = root / "libs.ref" / "sg13cmos5l_sram"
required = [
    f"lef/{macro}.lef",
    f"gds/{macro}.gds",
    f"cdl/{macro}.cdl",
    f"lib/{macro}_typ_1p20V_25C.lib",
    f"lib/{macro}_fast_1p32V_m55C.lib",
    f"lib/{macro}_slow_1p08V_125C.lib",
]
for relative in required:
    path = sram / relative
    assert path.is_file(), path
    assert path.stat().st_size > 0, path
lef = (sram / f"lef/{macro}.lef").read_text()
pins = re.findall(r"^\s*PIN\s+(\S+)", lef, re.MULTILINE)
assert len(pins) == 109, len(pins)
assert {"VDD!", "VDDARRAY!", "VSS!"}.issubset(pins)
assert re.search(r"SIZE\s+236\.8\s+BY\s+118\.78\s*;", lef)
print("All macro views present, 109 physical pins, expected footprint")
~~~

Inspect the actual files when adapting this recipe. The guide's geometry
and interface are specific to this macro and PDK revision.

## 5. Implement the RTL contract

### 5.1 Geometry and hierarchy

~~~text
Depth: 256 words
Word width: 16 bits
Total capacity: 4096 bits = 512 bytes
Word address width: 8 bits
Host byte address width: 9 bits
Macro instance in program_memory: i_sram
program_memory instance in the top: program_store
Flattened physical instance: program_store.i_sram
~~~

Keep `JP_PROG_AW = 8` in `src/defines.vh` and `PROGRAM_DEPTH = 256` in
`tools/config.py`. The host identification register returns `0xA7`, and
`PROGRAM_AW` returns eight.

The top retains the standard Tiny Tapeout digital interface:

~~~text
ui_in[7:0]
uo_out[7:0]
uio_in[7:0]
uio_out[7:0]
uio_oe[7:0]
ena
clk
rst_n
~~~

The physical flow adds and connects the supply terminals. Keep the functional
top and the official 43-signal pin template aligned.

### 5.2 Every functional macro port

| Port | Width | Connection | Meaning |
|---|---:|---|---|
| A_CLK | 1 | `~clk` | Active macro edge is the falling core-clock edge |
| A_MEN | 1 | `rst_n` | Active-high memory enable |
| A_WEN | 1 | Protected host write strobe | Active-high masked write |
| A_REN | 1 | `!write_enable` | Active-high read during read cycles |
| A_ADDR | 8 | Shared selected word address | Addresses words 0 through 255 |
| A_DIN | 16 | `{write_data, write_data}` | Host byte appears in both lanes |
| A_BM | 16 | `16'h00FF` or `16'hFF00` | A one selects a bit for writing |
| A_DLY | 1 | `1'b1` | Tested delay-control setting |
| A_DOUT | 16 | `read_data` | Registered macro read output |
| A_BIST_CLK | 1 | `1'b0` | BIST input tied low |
| A_BIST_EN | 1 | `1'b0` | Functional memory mode |
| A_BIST_MEN | 1 | `1'b0` | BIST memory enable tied low |
| A_BIST_WEN | 1 | `1'b0` | BIST write enable tied low |
| A_BIST_REN | 1 | `1'b0` | BIST read enable tied low |
| A_BIST_ADDR | 8 | `8'd0` | BIST address tied low |
| A_BIST_DIN | 16 | `16'd0` | BIST data tied low |
| A_BIST_BM | 16 | `16'd0` | BIST mask tied low |

The physical LEF adds `VDD!`, `VDDARRAY!`, and `VSS!`. The 106 functional
bits plus these three supplies make the 109 physical port names.

### 5.3 Clock phase and arbitration

The selected memory address is:

~~~verilog
wire [7:0] memory_address =
    core_enabled ? active_pc : byte_address[8:1];
wire memory_write =
    rst_n && host_write && host_address == 4 && !core_enabled;
~~~

These lines explain the integration contract. Use the complete top from the
reference source for signal declarations and host sequencing.

| Core-clock phase | Action |
|---|---|
| Just after a rising edge | The scheduler and selected address settle for the next operation |
| Next falling edge | The macro reads or performs the protected masked write |
| Following rising edge | Execution consumes the prepared instruction |

Each context receives one grant every four enabled core clocks. A literal
instruction obtains its following word on that context's next grant. Host
program reads use the same port while software execution is paused.

Hold address, mask, data, and enable signals stable across the active SRAM
edge. Verify both address-to-SRAM and SRAM-to-execution timing paths.

### 5.4 Byte writes and initialization

Low-byte writes use mask `0x00FF`. High-byte writes use `0xFF00`. Both carry
the host byte in `A_DIN[15:8]` and `A_DIN[7:0]`, with the mask selecting the
intended lane.

Example:

~~~text
Initial word             0xA55A
Write low byte 0x3C      0xA53C
Write high byte 0x81     0x813C
~~~

Power-up contents are unspecified. Load every reachable instruction and
literal before execution. Reset clears engine control and ownership state.
The enabled SRAM retains previously written contents through the tested
logical reset sequence. Power-cycle retention is a separate electrical matter.

### 5.5 Storage selection

| Build | Definitions | Implementation |
|---|---|---|
| ASIC synthesis | Default storage selection | Real IHP macro and synthesis declaration |
| ASIC functional simulation | `SIM` and `FUNCTIONAL` | Official IHP SRAM behavioral models |
| FPGA | `JP_FPGA_SYNC_MEMORY` | One ICE40 block RAM |
| Register reference | `JP_REGISTER_MEMORY` | Register-array implementation for comparison |

Choose one storage implementation for each build. The ASIC physical flow
expects the hard macro. The FPGA workflow appends its definition only in
that job's checkout.

## 6. Compile the correct simulation models

The two required files are:

~~~text
test/ihp_sram/RM_IHPSG13_1P_core_behavioral_bm_bist.v
test/ihp_sram/RM_IHPSG13_1P_256x16_c2_bm_bist.v
~~~

They are copied unchanged from the
[pinned IHP model directory](https://github.com/IHP-GmbH/IHP-Open-PDK/tree/2bbec755dc67ca3db0261c3d6163e15735d66710/ihp-sg13g2/libs.ref/sg13g2_sram/verilog).
Retain their copyright and Apache-2.0 notices.

Compile with `-DSIM -DFUNCTIONAL`. `SIM` excludes the synthesis-only black
box. The behavioral core and macro-specific model supply the real functional
simulation implementation.

The active `info.yaml` source list is:

~~~yaml
source_files:
  - "defines.vh"
  - "igorchip_top.v"
  - "program_host.v"
  - "program_memory.v"
  - "sram_256x16_bb.v"
~~~

The full `test/Makefile` appears in the source snapshots. Its gate-level
mode includes the CMOS5L standard-cell Verilog, companion UDP definitions,
I/O models, both SRAM models, the generated gate netlist, and `test/tb.v`.

Expected semantic tests include:

| Test | Expected observation |
|---|---|
| Complete masked word write | Readback equals the written word |
| Partial bit mask | Selected bits change and the other bits retain their value |
| Low-byte patch | High byte is preserved |
| High-byte patch | Low byte is preserved |
| A_MEN low | Write is inhibited and output retains its preceding value |
| A_REN low | Output retains its preceding value |
| Wrapper address change | Output updates at the intended falling core-clock edge |
| Logical reset sequence | Stored word remains readable after reset release |

Gate-level functional simulation checks connectivity and logic behavior.
The separate STA reports qualify physical timing.

## 7. Configure the physical macro

Copy the complete reference `src/config.json` from the source snapshots.
Its `MACROS` entry supplies all physical and timing views.

| Flow corner | SRAM characterization file |
|---|---|
| nom_typ_1p20V_25C | typ_1p20V_25C |
| nom_fast_1p32V_m40C | fast_1p32V_m55C |
| nom_slow_1p08V_125C | slow_1p08V_125C |

The fast flow corner selects the available m55C SRAM characterization.
Record this temperature pairing in timing review and qualify it against the
selected shuttle's requirements.

The reference physical geometry is:

| Property | Value |
|---|---|
| Tiny Tapeout allocation | 6 x 4 tiles |
| Die bounds | (0, 0) to (1289.28, 710.64) micrometers |
| SRAM size | 236.8 x 118.78 micrometers |
| SRAM origin | (300.0, 34.02) micrometers |
| SRAM upper-right corner | (536.8, 152.80) micrometers |
| Orientation | N, represented as R0 in OpenDB |
| Horizontal placement halo | 8 micrometers |
| Vertical placement halo | 8 micrometers |
| Database units | 1000 per micrometer |
| Placement density target | 40 percent |
| Maximum project routing layer | Metal4 |

The macro's bottom-edge signal pins have a 30.24-micrometer channel to the
reference core boundary. The LEF obstructions and access openings guide the
router directly.

`MACROS.instances` names the flattened instance exactly. A changed
hierarchy needs corresponding updates to the macro placement, connection
rules, geometry helper, and scoped LVS adapter.

## 8. Place interface pins before the power grid

This ordering is essential. The default Classic flow applies the pin
template later than PDN generation. The reference first removes that later
step, then inserts it before the grid:

~~~json
{
  "meta": {
    "flow": "Classic",
    "substituting_steps": {
      "Odb.ApplyDEFTemplate": null,
      "-OpenROAD.GeneratePDN": "Odb.ApplyDEFTemplate",
      "+OpenROAD.GeneratePDN": "Project.PowerProgramSRAM",
      "Netgen.LVS": "Project.ProgramSRAMLVS"
    }
  }
}
~~~

Dictionary order matters during substitution. Removing the original
template step before inserting its replacement creates exactly one
template-application step.

Required relative ordering:

~~~text
Odb.ApplyDEFTemplate
OpenROAD.GeneratePDN
Project.PowerProgramSRAM
...
Magic.SpiceExtraction
Project.ProgramSRAMLVS
Checker.LVS
~~~

The geometry helper checks that every signal boundary terminal has placed
pin geometry. Accepted placement statuses are `PLACED`, `FIRM`, or
`LOCKED`. Missing geometry raises an error before selecting supply columns.

To inspect the substituted flow with LibreLane installed:

~~~python
import json
from pathlib import Path
import librelane_plugin_program_sram
from librelane.flows import Flow

config = json.loads(Path("src/config.json").read_text())
flow_type = Flow.factory.get("Classic").Substitute(
    config["meta"]["substituting_steps"]
)
ids = [step.id for step in flow_type.Steps]
assert ids.count("Odb.ApplyDEFTemplate") == 1
assert ids.index("Odb.ApplyDEFTemplate") < ids.index("OpenROAD.GeneratePDN")
assert ids[ids.index("OpenROAD.GeneratePDN") + 1] == "Project.PowerProgramSRAM"
assert ids.index("Project.ProgramSRAMLVS") < ids.index("Checker.LVS")
print("Template, power-extension, and LVS order verified")
~~~

The plugin filename begins with `librelane_plugin_`. LibreLane discovers
modules with that prefix on its Python import path. Keep the root plugin
and the `tools` package accessible from the repository root.

## 9. Connect all SRAM supplies

### 9.1 Net names and physical pin names

| Object | Power | Ground |
|---|---|---|
| Tiny Tapeout global nets | VPWR | VGND |
| Standard-cell physical pins | VDD | VSS |
| SRAM peripheral supply | VDD! connected to VPWR | VSS! connected to VGND |
| SRAM array supply | VDDARRAY! connected to VPWR | VSS! connected to VGND |

The pinned support tool sets `VDD_PIN = VPWR` and `GND_PIN = VGND`.
LibreLane's power-net setup derives `VDD_NET` and `GND_NET`. Every
independent OpenROAD step resolves those values again.

The required configuration rules are:

~~~json
{
  "PDN_MACRO_CONNECTIONS": [
    "program_store\\.i_sram VPWR VGND VDD! VSS!",
    "program_store\\.i_sram VPWR VGND VDDARRAY! VSS!"
  ]
}
~~~

The backslash in the JSON string is escaped as `\\`. The resulting
regular expression matches the literal dot in the hierarchy.

### 9.2 Derive columns from the actual LEF

`jp_sram_columns` verifies:

1. The macro instance exists.
2. Its master name is correct.
3. Its orientation is R0.
4. All three supply terminals have their intended nets.
5. Every supply shape is on Metal4 and has sufficient width.
6. Supply columns sharing an x coordinate use the same supply.
7. The combined geometry has exactly 40 distinct columns.
8. Every macro-aligned column clears the signal-pin corridors.

The 40 columns are 20 power columns and 20 ground columns. Their spacing
includes an irregular middle band, so the actual LEF supplies the x
coordinates.

The reference helper uses these conversions:

~~~text
2.1 micrometer stripe width = 2100 database units
Stripe half-width = 1050 database units
Clearance on each side = 500 database units
Guard half-width = 1550 database units
~~~

The guard examines each Metal4 signal boundary-pin rectangle. It reserves
that pin's x corridor along the full-height stripe. The reference clearance
is 0.5 micrometers on each side, compared with the reported M4.b minimum
spacing of 0.21 micrometers.

### 9.3 Generate the grid

`src/pdn_cfg.tcl` creates:

- A CORE voltage domain on the resolved VPWR and VGND nets.
- Metal4 columns aligned to the SRAM's supply geometry.
- Ordinary Metal4 columns elsewhere, skipping the macro's x range and
  each signal-pin corridor.
- Metal1 standard-cell follow-pin rails.
- Metal1-to-Metal4 connections.

The ordinary column pattern uses a 38.87-micrometer pitch and a
4.1-micrometer power-to-ground offset. Each selected supply stripe is
2.1 micrometers wide.

The custom Tcl procedure receives the core rectangle and database-unit
conversion as arguments. This keeps its variables valid inside
LibreLane's `read_pdn_cfg` procedure scope.

### 9.4 Extend through the macro abstraction

`Project.PowerProgramSRAM` starts a separate OpenROAD process. Its script
loads the current database and sources `set_power_nets.tcl` again.

For every LEF-derived column it creates a full-height Metal4 special-wire
rectangle and a matching supply boundary pin. This joins the actual SRAM
supply shapes across the abstract macro blockage.

The extension is deliberately tied to the actual macro supplies. The
geometry and signal-pin guards run before the rectangles are added.

Then both supply checks run:

~~~tcl
check_power_grid -net $::env(VDD_NET)
check_power_grid -net $::env(GND_NET)
~~~

Expected messages:

~~~text
All shapes on net VPWR are connected.
All shapes on net VGND are connected.
Program SRAM: extended 40 LEF-derived supply columns to tile boundaries
~~~

The script refreshes the violation metrics only after both connectivity
checks succeed. Pre-extension warnings describe the earlier grid state.
The final checker evaluates the verified extended result.

### 9.5 Geometry qualification

The macro LEF has abstract supply geometry that creates false overlap
findings in the generic Magic abstraction checks. The reference
configuration uses these scoped choices:

~~~json
{
  "RUN_MAGIC_DRC": false,
  "ERROR_ON_ILLEGAL_OVERLAPS": false,
  "RUN_KLAYOUT_DRC": 1,
  "ERROR_ON_KLAYOUT_DRC": true,
  "ERROR_ON_TR_DRC": true,
  "ERROR_ON_LVS_ERROR": true
}
~~~

KLayout qualifies the assembled GDS geometry. Detailed-routing DRC,
integration LVS, supply connectivity, and Tiny Tapeout precheck remain
acceptance gates. Apply the same abstraction rationale only after checking
the chosen macro's actual views.

## 10. Run integration LVS

### 10.1 Supply the complete port interface

The abstract `src/sram_256x16_lvs.spice` declares all 109 physical names.
It is loaded through:

~~~json
{
  "EXTRA_SPICE_MODELS": ["dir::sram_256x16_lvs.spice"]
}
~~~

Its bus pins appear contiguously in descending index order. This lets
Netgen infer the full vector width while reading the named-port Verilog
instance.

This is a macro-integration interface. It checks the surrounding circuit's
connections to the supplied macro. The unchanged official GDS, CDL,
Liberty, and simulation models establish the identity and provenance of
the macro itself.

### 10.2 Adapt only the required reader syntax

OpenROAD's powered Verilog contains escaped physical supply-pin tokens.
The LVS step makes a local copy and changes the three SRAM formal-pin
spellings into the syntax accepted by the recorded Netgen reader:

~~~text
Original pin token: .\VDD! (
LVS copy token:     .VDD!(
~~~

The operation is scoped to exactly one `program_store.i_sram` instance
and exactly one occurrence of each of its three supply pins. Connected
node names retain their original values. The original powered netlist
remains the flow's saved view.

### 10.3 Preserve report contents

Some Netgen versions write unsupported identifier backslashes into JSON
strings. The compatibility helper:

1. Parses valid JSON directly.
2. Repairs unsupported string escapes when that is the reported problem.
3. Preserves existing valid escapes.
4. Saves the original as `lvs.netgen.json.original`.
5. Validates the repaired JSON before LibreLane consumes it.

Circuit mismatch data and error counts remain intact. Structural JSON
problems still raise an exception. The normal `Checker.LVS` remains in
the flow.

### 10.4 Acceptance and fault checks

Expected final report:

~~~text
Final result: Circuits match uniquely.
~~~

Expected metric:

~~~text
design__lvs_error__count = 0
~~~

The local interface fixture deliberately connects `VDDARRAY!` to ground.
The recorded Netgen 1.5.270 fixture reports 110 errors for that fault and
zero for correct wiring. A complete routed-engine replay also distinguishes
the original interface-pin shorts from the corrected grid.

Read the full `lvs.netgen.rpt` and JSON comparison when debugging. Device
and net totals may vary with synthesis and routing. Require a unique match
and zero reported errors rather than a fixed device count for every future
revision.

## 11. Program an exact SRAM address

Physical placement and runtime word addresses are independent coordinates.
The macro sits at (300.0, 34.02) micrometers. Software selects word 0
through 255 inside that macro.

### 11.1 Address conversion

~~~text
byte_address = 2 * word_address
ADDRESS_LO = byte_address & 0xFF
ADDRESS_HI = byte_address >> 8
~~~

| Word | First byte | ADDRESS_HI | ADDRESS_LO |
|---|---|---|---|
| 0 | 0x000 | 0x00 | 0x00 |
| 127 | 0x0FE | 0x00 | 0xFE |
| 128 | 0x100 | 0x01 | 0x00 |
| 254 | 0x1FC | 0x01 | 0xFC |
| 255 | 0x1FE | 0x01 | 0xFE |

A word occupies its low byte followed by its high byte. The hardware DATA
register auto-increments the byte address modulo 512. The Python driver
bounds a requested range before issuing SPI activity.

### 11.2 Host bus and register operations

~~~text
CS_n: ui[0]
SCLK: ui[1]
MOSI: ui[2]
MISO: uo[0]
Mode: SPI mode 0, MSB first
Frame command: write flag in bit 7, register address in bits 6:0
~~~

Keep CS low for the complete command and data burst. Allow at least four
core clocks per SCLK half-period and for CS setup and recovery. The core
clock continues running while execution is paused.

| Register | Address | Programming use |
|---|---:|---|
| CONTROL | 0 | Write zero to pause, one to resume |
| STATUS | 1 | Read error bitmap and running bitmap |
| ADDRESS_LO | 2 | Byte address bits 7:0 |
| ADDRESS_HI | 3 | Byte address bit 8 in bit 0 |
| DATA | 4 | Burst read or write with byte-address increment |
| CONTEXT | 5 | Select one context |
| ENTRY_LO | 6 | Starting word address |
| ENTRY_HI | 7 | Zero for the eight-bit program counter |
| RESTART | 8 | Context bitmap to start |
| STOP | 9 | Context bitmap to halt and release owned outputs |
| PIN_MASK | 10 | Selected context's output ownership |
| ERROR_CLEAR | 11 | Write-one-to-clear error bitmap |
| ID | 12 | Read 0xA7 |
| PROGRAM_AW | 19 | Read eight |

Software CONTROL pause selects the host memory address. The Tiny Tapeout
`ena` signal has a different GPIO-release behavior. Use CONTROL pause for
program loading and readback.

### 11.3 Complete word-programming example

Supply the board-specific `board_spi_transfer` callback. It accepts bytes,
returns one received byte per transmitted byte, and follows the frame and
clock requirements above.

For a freshly reset device with `ena` asserted:

~~~python
from tools.assembler import halt
from tools.config import PROGRAM_DEPTH
from tools.host import Engine
from tools.protocols import uart_bit_grants, uart_tx

engine = Engine(board_spi_transfer)
assert engine.identify() == 0xA7
engine.pause()
engine.stop()
engine.load([halt()] * PROGRAM_DEPTH)

clock_hz = 50_000_000  # Reference simulation target
period = uart_bit_grants(clock_hz, 115_200, receive=True)
program = uart_tx(0x55, pin=1, bit_grants=period)
entry = 0x80
engine.load(program, entry=entry)
assert engine.read_program(entry=entry, count=len(program)) == program
engine.configure(tid=0, pin_mask=0x02)
engine.start(mask=1, entry=entry)
engine.resume()
~~~

This initializes the reachable store to HALT, then patches a UART transmit
program at word 128 and verifies it. The UART program is 25 words and fits
inside the remaining capacity.

For reused ownership settings, pause, stop, and clear the previous masks
before assigning new disjoint masks. Select a hardware clock through the
timing-qualification stage and regenerate the bit period for that clock.

The reference 50 MHz simulation setting uses 108 grants per UART bit.
The 12 MHz FPGA setting uses 26. Each grant takes four core clocks.

### 11.4 Targeted programming acceptance

Exercise words 0, 127, 128, 254, and 255 with distinct values. Patch each
byte lane independently and read all 256 words back. Confirm:

- The intended word changes.
- Its opposite byte retains its value.
- Every other word retains its value.
- Word 128 correctly uses the high byte-address bit.
- Word 255 uses bytes 510 and 511.
- Out-of-range software requests are rejected before SPI activity.
- Live hardware DATA accesses set the documented error state.

The committed RTL and host tests exercise these cases. Full host behavior
and the remaining debug registers are documented in
[HOST_INTERFACE.md](HOST_INTERFACE.md).

## 12. Run the full verification sequence

From the repository root, first select the default ASIC simulation mode:

~~~bash
unset JP_TEST_FPGA JP_TEST_REGISTER
python -m unittest discover -s test -p 'test_*.py' -v
python -m tools.run_cocotb
~~~

Expected at the reference revision: 42 unit/regression tests pass and the
pin-only cocotb test passes.

Run both comparison variants:

~~~bash
JP_TEST_FPGA=1 python -m unittest discover -s test -p 'test_*.py' -v
JP_TEST_REGISTER=1 python -m unittest discover -s test -p 'test_*.py' -v
~~~

The reference runs 42 tests for each selection. The dedicated SRAM-model
tests still exercise the foundry models directly.

On PowerShell:

~~~powershell
Remove-Item Env:JP_TEST_FPGA -ErrorAction SilentlyContinue
Remove-Item Env:JP_TEST_REGISTER -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_*.py" -v
.\.venv\Scripts\python.exe -m tools.run_cocotb
$env:JP_TEST_FPGA = '1'
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_*.py" -v
Remove-Item Env:JP_TEST_FPGA
$env:JP_TEST_REGISTER = '1'
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_*.py" -v
Remove-Item Env:JP_TEST_REGISTER
~~~

The coverage combines a Python cycle model, randomized programs and inputs,
independent protocol peers, external-pin host programming, and runtime
ownership assertions. Formal proof is tracked separately.

For Linux Make-based RTL testing:

~~~bash
cd test
make clean
make
python -m cocotb_tools.check_results results.xml
cd ..
~~~

For gate-level testing, use the netlist from the same physical revision and
the matching installed PDK:

~~~bash
cd test
make clean
make GATES=yes
python -m cocotb_tools.check_results results.xml
cd ..
~~~

The official gate-level action supplies `test/gate_level_netlist.v`. A local
replay must place that exact exported netlist there first.

After successful local hardening, the support tool selects the applicable
gate-netlist format during submission creation:

~~~bash
./tt/tt_tool.py --create-tt-submission --ihp
cp tt_submission/tt_um_igorchip.v test/gate_level_netlist.v
~~~

Submission creation refreshes `tt_submission`. Preserve an earlier
submission in an archive directory before regenerating it.

The GitHub precheck action is the reference acceptance path. A local
precheck replay uses the pinned support tool's requirements and Nix setup:

~~~bash
python -m pip install -r tt/precheck/requirements.txt
export SRAM_PROJECT_ROOT="$PWD"
cd tt/precheck
nix-build
nix-shell --run "python precheck.py --gds $SRAM_PROJECT_ROOT/tt_submission/tt_um_igorchip.gds --tech ihp-sg13cmos5l"
cd "$SRAM_PROJECT_ROOT"
~~~

This requires Nix installed through its supported installation procedure,
the same PDK_ROOT/PDK environment, and the generated submission alongside
the repository metadata. The official precheck runs its own single-threaded
KLayout DRC check, so allow time for that separate stage.

Before spending time on place-and-route, inspect synthesis statistics or the
mapped netlist for exactly one `RM_IHPSG13_1P_256x16_c2_bm_bist` instance
with the intended hierarchy. The registered power step also enforces that
master and instance during the physical flow.

## 13. Build GDS and preserve diagnostics

The complete reference GDS workflow appears in the source snapshots. It
uses the official IHP action with `pdk: ihp-sg13cmos5l`.

The build has:

~~~text
Job timeout: 180 minutes
Build-step timeout: 150 minutes
Detailed-routing optimization iterations: 20
Detailed-routing report interval: 5 iterations
OpenROAD threads: 2
Placement target density: 40 percent
Global routing: congestion-free acceptance
~~~

The separate always-running diagnostic upload preserves logs after a
failed build step. The time reserve gives it an opportunity to finish.
Concurrency replaces an older run on the same branch with the latest run.

| Artifact | Contents to inspect |
|---|---|
| tt_submission | Submission GDS/OASIS and project metadata consumed by downstream actions |
| GDS_logs | Detailed physical-flow files, reports, and extracted circuit views |
| gds-diagnostics-* | Saved config, logs, reports, JSON, OpenDB databases, guides, SDC, and adapted LVS input |
| gds_render | Layout preview used by the viewer |
| precheck_reports | Tiny Tapeout acceptance results and reports |
| test-results | Cocotb results and waveforms from the test workflow |

The report directories carry step-number prefixes. Identify them by the
step suffix, since inserted steps can change numbering:

~~~text
*-openroad-generatepdn/
*-project-powerprogramsram/
*-openroad-detailedrouting/
*-klayout-drc/
*-magic-spiceextraction/
*-project-programsramlvs/reports/lvs.netgen.rpt
*-project-programsramlvs/reports/lvs.netgen.json
final/metrics.json
final/gds/
final/def/
final/spice/
tt_submission/tt_um_igorchip.oas
~~~

For the recorded flow, LVS is in
`67-project-programsramlvs/reports`. KLayout's detailed rule database can
appear as `drc.klayout.lyrdb`. The always-uploaded diagnostics and full
GDS logs have different file selections, so use the full logs artifact
for extracted SPICE and geometry databases when needed.

Read final metrics directly:

~~~python
import json
from pathlib import Path

metrics = json.loads(Path("runs/wokwi/final/metrics.json").read_text())
for key in (
    "design__lvs_error__count",
    "klayout__drc_error__count",
    "design__power_grid_violation__count",
):
    assert metrics[key] == 0, (key, metrics[key])
    print(key, metrics[key])
~~~

Follow this with the precheck and gate-level job results. A saved GDS file
is one output of the build. Complete integration acceptance includes the
report metrics and downstream checks.

## 14. Publish and verify the viewer

The viewer job runs after a successful GDS job on the default branch.
Feature-branch and pull-request runs validate the hardware while viewer
publication remains attached to the default branch.

For a repository that uses this workflow:

1. Set GitHub Pages source to GitHub Actions.
2. Retain `pages: write` and `id-token: write` on the viewer job.
3. Require a successful upstream GDS job and its named submission/render artifacts.
4. Publish the verified revision on the repository's default branch.
5. Confirm the viewer job completes successfully.
6. Fetch the published OASIS file and preview.
7. Verify the top and SRAM hierarchy inside the published file.

The published files for this repository are:

- [Pages entry point](https://wlmoi.github.io/General-Purpose-Protocol-ASIC_JaneStreet/)
- [OASIS model](https://wlmoi.github.io/General-Purpose-Protocol-ASIC_JaneStreet/tinytapeout.oas)
- [GDS layout](https://wlmoi.github.io/General-Purpose-Protocol-ASIC_JaneStreet/tinytapeout.gds)
- [2D preview](https://wlmoi.github.io/General-Purpose-Protocol-ASIC_JaneStreet/gds_render.png)
- [Direct 3D viewer](https://gds-viewer.tinytapeout.com/?model=https%3A%2F%2Fwlmoi.github.io%2FGeneral-Purpose-Protocol-ASIC_JaneStreet%2Ftinytapeout.oas&pdk=ihp-sg13cmos5l)

The direct viewer link explicitly selects the CMOS5L layer definitions.
Use a repository-specific Pages URL when reproducing the project elsewhere.

The published reference model was checked with the official viewer's
WASM processor. It contains one reference to the selected SRAM and the
correct top-level bounds. Its meshes have finite positions and valid
vertex indices. This also distinguishes the SRAM layout from the earlier
published register-memory layout.

For a portable hierarchy check with the KLayout Python package installed:

~~~python
import urllib.request
from pathlib import Path
import klayout.db as db

url = "https://wlmoi.github.io/General-Purpose-Protocol-ASIC_JaneStreet/tinytapeout.oas"
target = Path("build/published-sram.oas")
target.parent.mkdir(parents=True, exist_ok=True)
with urllib.request.urlopen(url, timeout=60) as response:
    assert response.status == 200
    target.write_bytes(response.read())
layout = db.Layout()
layout.read(str(target))
top = layout.top_cell()
assert top.name == "tt_um_igorchip"
macro = layout.cell("RM_IHPSG13_1P_256x16_c2_bm_bist")
assert macro is not None
instances = sum(
    inst.cell_index == macro.cell_index()
    for cell in layout.each_cell()
    for inst in cell.each_inst()
)
assert instances == 1, instances
print("Published SRAM hierarchy verified")
~~~

Use a revision query or normal cache refresh when comparing a newly
published file with a previous model. Record the downloaded file hash
alongside the deployment's source revision.

## 15. Qualify timing and external interfaces

The configuration's `CLOCK_PERIOD = 20` ns is a 50 MHz target. The
half-cycle architecture gives both address-to-SRAM and SRAM-to-execution
paths a half-period relationship that must be reviewed in STA.

For commit `1649be6`, the recorded final timing metrics include:

| Metric | Recorded value |
|---|---:|
| Worst setup slack | Approximately -2.637 ns |
| Setup violations | 253 |
| Maximum slew violations | 26 |
| Maximum capacitance violations | 11 |
| Hold violations | 0 |

These reports identify the next timing-repair work. Preserve the real
clock, operating corners, constraints, and loads while repairing paths.
Measure the resulting setup, hold, slew, and capacitance acceptance before
declaring a selected clock qualified.

The FPGA flow targets 12 MHz and checks for one `SB_RAM40_4K` family block
RAM plus a nonempty bitstream. Its source selection and timing target are
separate from the ASIC's physical SRAM.

The SRAM is internal to the chip's core-voltage domain. External protocol
connections use the Tiny Tapeout board's compatible digital I/O levels.
Document I2C pull-ups, board capacitance, attached-device timing, and any
external UART or bus transceiver. Match UART generation to the actual
qualified clock and measure framing behavior on the board.

## 16. Diagnose failures by stage

| Symptom | Likely cause | Corrective action and acceptance |
|---|---|---|
| Checkout fails, then results.xml is missing | Repository checkout or Git metadata failed before tests started | Resolve the first checkout error and rerun tests before diagnosing absent test artifacts |
| Required PDK macro view is missing | Partial PDK copy or unresolved shared SRAM directory | Install the complete pinned PDK and run the view audit |
| Duplicate Verilog macro declaration | Behavioral models and synthesis declaration compiled together | Use SIM and FUNCTIONAL with the guarded declaration and the two official models |
| SRAM output stays X | Reachable memory is uninitialized or read enable/clock selection is wrong | Load the reachable image, check A_MEN/A_REN, and run the clock-edge test |
| Byte patch changes both lanes | Incorrect A_BM polarity, width, or lane selection | Check 0x00FF/0xFF00 and read every neighbor after both lane patches |
| Word 128 aliases another location | Word/byte conversion or ADDRESS_HI is wrong | Verify byte address 0x100 and the 127/128 boundary test |
| Host DATA returns zero or sets an error | Core execution is enabled during memory access | Write CONTROL zero, retain the core clock, and retry the documented paused access |
| Program SRAM instance required | ASIC selected a reference/FPGA memory or lost the macro during synthesis | Restore ASIC source selection and verify the retained macro before PDN |
| Signal pin requires template placement | PDN selection ran while interface pins were unplaced | Apply the official DEF template before GeneratePDN and verify step order |
| can't read core: no such variable | Tcl procedure relied on another scope's local variable | Pass core and dbu explicitly as jp_stripe arguments |
| PDN-0224 power net absent from grid | Incorrect global supply name | Use the resolved VPWR/VGND configuration and connect physical macro pins separately |
| VDD!, VDDARRAY!, or VSS! remains unconnected | Missing hook, incorrect instance pattern, or supply extension | Verify both macro rules, exact hierarchy, all 40 columns, and the post-extension checks |
| Large pre-extension PSM count remains in final metrics | Successful extension retained earlier metrics | Refresh metrics only after both actual connectivity checks pass |
| M4.b errors at the top boundary | Supply columns cross the fixed interface-pin bank | Use the reference origin, early pin placement, and clearance guards, then rerun DRC and LVS |
| Top-level pins fail matching with fewer extracted nets | Physical shorts or incomplete interface declaration | Read unmatched nets/pins and correlate their actual geometry, then verify the 109-pin declaration |
| Undefined SRAM subcircuit in Netgen | Required macro interface was absent | Load the complete SPICE port interface before the powered Verilog |
| Bus widths or macro ports mismatch | Partial declarations or incompatible bus ordering | Use contiguous descending bus pins from the supplied full interface |
| JSON invalid escape error | Reader report contains unsupported identifier escapes | Preserve the raw report and apply the scoped compatibility helper |
| Gate-level UDP is undefined | Standard-cell companion UDP source was absent | Compile matching CMOS5L cell and UDP models together |
| Routing runs for hours with persistent shorts | Congestion, poor signal access, or bad power geometry | Inspect saved rule coordinates, retain the real access windows, and correct the floorplan or grid |
| Viewer job is skipped on a feature branch | Default-branch publication condition | Validate the branch, integrate it into the default branch, and verify deployment |
| Viewer serves the preceding layout | Published model or browser/CDN cache predates the revision | Compare revision and model hash, refresh the model, and inspect SRAM hierarchy |
| Setup/slew/capacitance warnings remain | Physical electrical/timing limits require repair | Review corner-specific paths and loads, repair them, and record qualified operating conditions |

### 16.1 The physical shorts that this recipe corrected

The earlier origin (20.16, 34.02) micrometers placed SRAM supply columns
across the fixed Metal4 interface bank. The actual reports showed 16 M4.b
spacing/notch errors and merged interface nets.

Moving the SRAM to x = 300 cleared the macro-column conflicts. A following
run passed DRC and power connectivity while LVS still reported seven merged
nets and 17 errors. The ordinary grid had been selected before the signal
pins were placed. Applying the DEF template first made the clearance
predicate operate on real coordinates and resolved those remaining shorts.

This demonstrates why a power-connectivity pass needs both signal
separation checks and final LVS. DRC qualifies geometry, and LVS compares
electrical connectivity.

### 16.2 Collect concrete evidence before changing settings

For a failing run, collect:

~~~text
Repository commit and workflow run URL
First fatal step and error
Resolved configuration and PDK source version
Macro name, hierarchy, orientation, and origin
Unmatched pin/net section from lvs.netgen.rpt
Original and parsed lvs.netgen.json
DRC rule names, layers, and coordinates
Post-extension power checks and final metrics
The relevant DEF/ODB/SPICE/GDS views
~~~

Change the identified cause, rerun the affected stage, then complete the
normal acceptance sequence. Keep the stage's error reporting intact.

## 17. Adapt the design to another macro

Use a new integration contract for each change in macro or process:

| Change | Items to revisit |
|---|---|
| Depth | Address width, PC width, host byte address, assembler limits, readback limits, tests |
| Word width | Instruction packing, byte lanes, masks, host serialization, literals |
| Read latency | Scheduler grant timing, literals, host snapshots, cycle reference model |
| Port count | Arbitration, simultaneous-access policy, clocks, physical pins |
| Macro master name | Black box, wrapper, MACROS key, instance validation, LVS adapter |
| Hierarchy | Placement instance, macro power hooks, geometry helper, scoped reader match |
| Supply names | Global nets, LEF/CDL ports, hookups, abstract interface |
| Orientation | LEF-to-global coordinate transform and supply-column extraction |
| Database units | Every width, clearance, offset, and origin conversion |
| Process stack | Routing layers, via connections, pin-access rules, viewer layer definitions |
| Die or tile allocation | Official DEF template, legal macro position, rows, density, routing |
| Operating conditions | Actual Liberty corners, clock phase, STA constraints, external timings |

The current geometry helper is written for R0 orientation, 1000 database
units per micrometer, and this macro's Metal4 supply pattern. Transform
geometry explicitly when extending those assumptions.

Use the reference FPGA and register implementations as behavioral
comparisons. Retain the foundry-model tests as the check of actual SRAM
enable, mask, and edge semantics.

## 18. Agent handoff and evidence record

Before work:

1. Read applicable repository instructions.
2. Record the working tree, current revision, and requested target.
3. Preserve existing user changes and use a fresh reproduction checkout.
4. Read this guide and the canonical integration files.
5. Verify the installed macro views and storage selection.

Implementation sequence:

~~~text
Source/PDK audit
    -> RTL wrapper and foundry-model tests
    -> Host addressing and differential/protocol tests
    -> Synthesis with one retained macro
    -> Legal placement and early interface-pin template
    -> LEF-derived PDN and both supply-connectivity checks
    -> Routing and assembled-GDS DRC
    -> Complete integration LVS
    -> Tiny Tapeout precheck and gate-level simulation
    -> Default-branch viewer publication and model inspection
    -> Timing qualification and board validation
~~~

A useful final evidence record includes:

~~~yaml
source_commit: "<full repository SHA>"
pdk: "ihp-sg13cmos5l"
pdk_commit: "2bbec755dc67ca3db0261c3d6163e15735d66710"
macro: "RM_IHPSG13_1P_256x16_c2_bm_bist"
instance: "program_store.i_sram"
macro_origin_um: [300.0, 34.02]
macro_orientation: "N"
storage_words: 256
storage_word_bits: 16
rtl_test_result: "<count and result>"
gate_level_result: "<result and run URL>"
lvs_errors: "<actual final count>"
klayout_drc_errors: "<actual final count>"
power_grid_violations: "<actual post-extension count>"
precheck_result: "<result and run URL>"
viewer_deployment: "<result and URL>"
published_model_sha256: "<downloaded model hash>"
timing_result: "<corner metrics and qualification status>"
board_result: "<measured evidence or scheduled qualification stage>"
~~~

Use actual measured values. Separate behavior, geometry, connectivity,
timing, and board results. Describe the exact revision associated with each
result.

### Primary implementation references

- [Pinned Tiny Tapeout action](https://github.com/TinyTapeout/tt-gds-action/tree/3412659307918422f3f0727917cf9b499aaca588)
- [Pinned CMOS5L PDK installer](https://github.com/TinyTapeout/tt-gds-action/blob/3412659307918422f3f0727917cf9b499aaca588/install_sg13cmos5l.sh)
- [Pinned support-tool configuration and hardening](https://github.com/TinyTapeout/tt-support-tools/blob/d66cf179e7bc4d296362ab7e2e3b344dc3c4f665/project.py)
- [Pinned support-tool precheck](https://github.com/TinyTapeout/tt-support-tools/blob/d66cf179e7bc4d296362ab7e2e3b344dc3c4f665/precheck/precheck.py)
- [Pinned IHP macro library](https://github.com/IHP-GmbH/IHP-Open-PDK/tree/2bbec755dc67ca3db0261c3d6163e15735d66710/ihp-sg13g2/libs.ref/sg13g2_sram)
- [LibreLane configuration reference](https://librelane.readthedocs.io/en/latest/reference/configuration.html)
- [LibreLane macro integration](https://librelane.readthedocs.io/en/latest/usage/macros.html)
- [OpenROAD PDN API](https://openroad.readthedocs.io/en/latest/main/src/pdn/README.html)
- [Tiny Tapeout viewer source](https://github.com/TinyTapeout/tinytapeout_gds_viewer)

## 19. Source snapshots and integrity manifest

The following snapshots are copied from commit
`b08afad42ed7179eee4a276634ee7b4cefae4f6c`. They preserve the complete
integration implementation. Restore each block to its indicated relative
path when recreating the layer in a compatible engine.

SHA-256 values describe UTF-8 source text with LF line endings. Normalize
CRLF to LF before comparing a Windows working-tree file. The surrounding
engine and foundry-model files are also listed in the integrity manifest.

Run this audit from the reproduction checkout after saving this guide at its
documented path:

~~~python
import hashlib
import re
from pathlib import Path

guide = Path("docs/SRAM_IMPLEMENTATION_GUIDE.md").read_text()
records = re.findall(
    r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|$",
    guide,
    re.MULTILINE,
)
assert len(records) == 32
for relative, expected in records:
    data = Path(relative).read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(data).hexdigest()
    assert actual == expected, (relative, actual, expected)
print("All 32 reference-source checksums match")
~~~

<!-- SRAM_SOURCE_SNAPSHOTS -->

### Integrity manifest

| File | SHA-256 of LF-normalized source |
|---|---|
| `src/program_memory.v` | `4b917488e659f82ab924d49b95ff2db3437fd48dfca91eed2aeaabad13ee34ac` |
| `src/sram_256x16_bb.v` | `e1b2050253748f8dbece08016e7f518e221cac5f11735f5c4fd508ab0a16cd36` |
| `src/config.json` | `b3204c41cf1924f7739b3c30c10db02291896ac7662c35309cf2998292800d3d` |
| `src/sram_geometry.tcl` | `00b2d4f5268f3a914a5672bc082831831a6fb7929af086b35d7533597c36cd4a` |
| `src/pdn_cfg.tcl` | `373b2392edf23c33ca311a42955cbf28ef22189a2e242f9f1917a075ef7a4652` |
| `src/power_sram.tcl` | `808ed559f59e32520f6209bbb8263b8e18751b128b98791504ab56812266a676` |
| `librelane_plugin_program_sram.py` | `a17fc86bd64130de9cf0a13eb82036ac9eabacee0be1644b04649673f25b7f7f` |
| `src/sram_256x16_lvs.spice` | `3016e308b4485554172b5f6c815535d3d6860097d568015eb390d6f88ab08d09` |
| `tools/netgen_json.py` | `181a2bb1b2359c9634143763c751b130d3dfa547fe88f480bb007aa7ca82802e` |
| `test/Makefile` | `2365c553f14cb8aa890d3423bc997699cc002b8385e831c7a924d5e33f741017` |
| `test/test_sram.py` | `f427afb39e6504039db09b2238ac6ad384cda088a8736e4828e7ab3c7c08b45a` |
| `.github/workflows/gds.yaml` | `cde23aba1a499e72189d928333b1052c0ccdfc1f148434d6290386a87181b12e` |
| `info.yaml` | `83c3c5ec78920b667ca26b085daf7813a51a8998d3f2efed735a7f62d28bedb2` |
| `src/igorchip_top.v` | `9f7425b4b35eb6e5dc652dc3ed869b953de545e55ca3017b6ef4aaf4012624f1` |
| `src/program_host.v` | `acd1545244d489617515b320d4eed9b5c0b522e750af74ce88a3e1f226054686` |
| `src/defines.vh` | `bee2b34a40efbacccd23d2c53a208a63d1a172e565d3a4ffb786ef04b373d0bf` |
| `tools/config.py` | `6310c839f095c898a78bd1825ca2ef129b84043d3608104d76a101380884b191` |
| `tools/host.py` | `43c9fc722d71137e05f6f371f5a774adcc6ece088555acb447fc412678870924` |
| `tools/assembler.py` | `ce18e60c3e5b16dce8a1ef7233a82fedac52eda284e789385182d85abda01861` |
| `tools/protocols.py` | `dd8926178cdd812bdf84053d051d5e5d8fa68f312d621cd45e794251aacb2a8b` |
| `tools/run_cocotb.py` | `7a926063aef52a98778133b2c10ac3bab12d252dbe89657bcc89f71ec5f97120` |
| `test/tb.v` | `3c8890c6bde408617232452c760df13bf939bf6a4ebcc92ac5538a91bee3b6f8` |
| `test/test.py` | `ac0f6b9f2d686991ec6fc5a974bbaaff12a58d5d3098baeaa144060e0dc61bb3` |
| `test/test_rtl.py` | `ff846bd4597a34784b269220594cb67afc268ec12805e859d3c1f0637b5e0921` |
| `test/test_reference_model.py` | `86107d1956456acbd7fa71a1dc256eed4e359984126a5f46b2a06f92faa7dc2d` |
| `test/test_netgen_json.py` | `2cb939c6f4b7e0ac674badd20473c4f47a8dc7a9dce284bd6f212e1007a25431` |
| `test/requirements.txt` | `4273151bc1544b57436ccd1af30e6428beb0291e4f9fba3307db8115ef53f60d` |
| `test/ihp_sram/RM_IHPSG13_1P_core_behavioral_bm_bist.v` | `d0a6258f8e9c93d1d5b1f78c0a1d66f30d28b1ad8037e5e07f53d1a4e3670b12` |
| `test/ihp_sram/RM_IHPSG13_1P_256x16_c2_bm_bist.v` | `645c475787b077da4dbd15856c68bbae46aa9846a155239eb895ed2de7511053` |
| `.github/workflows/test.yaml` | `2300848a5b1c8d2cf38ae01073d211bec88f0297dcd3e2ac848b733ffacc1fe9` |
| `.github/workflows/fpga.yaml` | `f0c146c33a2e62becab3fb5573c703c17820083d38e65dc767b4896e148e5080` |
| `.github/workflows/docs.yaml` | `4ab03b32e38e4ae604df854def95675b8b82398816fd3bd6dd7e143c7ec887b9` |

### Snapshot 1: src/program_memory.v

~~~verilog
`default_nettype none
`include "defines.vh"
// One physical read/write port. The falling edge prepares the next instruction
// for the rising-edge execution grant without changing the four-context cadence.
module program_memory (
 input wire clk, rst_n,
 input wire [7:0] address,
 input wire write_enable,
 input wire high_byte,
 input wire [7:0] write_data,
 output wire [15:0] read_data
);
`ifdef JP_FPGA_SYNC_MEMORY
 reg [15:0] words [0:255];
 reg [15:0] read_q;
 always @(posedge clk) begin
  if (write_enable) begin
   if (high_byte) words[address][15:8] <= write_data;
   else words[address][7:0] <= write_data;
  end
 end
 always @(negedge clk) read_q <= words[address];
 assign read_data = read_q;
`else
`ifdef JP_REGISTER_MEMORY
 reg [15:0] words [0:255];
 always @(posedge clk) begin
  if (write_enable) begin
   if (high_byte) words[address][15:8] <= write_data;
   else words[address][7:0] <= write_data;
  end
 end
 assign read_data = words[address];
`else
 wire memory_clock = ~clk;
 RM_IHPSG13_1P_256x16_c2_bm_bist i_sram (
  .A_CLK(memory_clock), .A_MEN(rst_n),
  .A_WEN(write_enable), .A_REN(!write_enable),
  .A_ADDR(address), .A_DIN({write_data, write_data}),
  .A_BM(high_byte ? 16'hFF00 : 16'h00FF),
  .A_DLY(1'b1), .A_DOUT(read_data),
  .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
  .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(8'd0),
  .A_BIST_DIN(16'd0), .A_BIST_BM(16'd0)
 );
`endif
`endif
endmodule
~~~

### Snapshot 2: src/sram_256x16_bb.v

~~~verilog
`include "defines.vh"
`ifndef SIM
`ifndef JP_FPGA_SYNC_MEMORY
`ifndef JP_REGISTER_MEMORY
(* blackbox *)
module RM_IHPSG13_1P_256x16_c2_bm_bist (
 input wire A_CLK, A_MEN, A_WEN, A_REN, A_DLY,
 input wire [7:0] A_ADDR,
 input wire [15:0] A_DIN, A_BM,
 output wire [15:0] A_DOUT,
 input wire A_BIST_CLK, A_BIST_EN, A_BIST_MEN, A_BIST_WEN, A_BIST_REN,
 input wire [7:0] A_BIST_ADDR,
 input wire [15:0] A_BIST_DIN, A_BIST_BM
);
endmodule
`endif
`endif
`endif
~~~

### Snapshot 3: src/config.json

~~~json
{
  "//": "DO NOT EDIT THIS FILE before reading the comments below:",

  "//": "This is the default configuration for Tiny Tapeout projects. It should fit most designs.",
  "//": "If you change it, please make sure you understand what you are doing. We are not responsible",
  "//": "if your project fails because of a bad configuration.",

  "//": "!!! DO NOT EDIT THIS FILE unless you know what you are doing !!!",

  "//": "If you get stuck with this config, please open an issue or get in touch via the discord.",

  "//": "Here are some of the variables you may want to change:",

  "//": "PL_TARGET_DENSITY_PCT - You can increase this if Global Placement fails with error GPL-0302.",
  "//": "Users have reported that values up to 80 worked well for them.",
  "PL_TARGET_DENSITY_PCT": 40,

  "//": "CLOCK_PERIOD - Increase this in case you are getting setup time violations.",
  "//": "The value is in nanoseconds, so 20ns == 50MHz.",
  "CLOCK_PERIOD": 20,

  "//": "Hold slack margin - Increase them in case you are getting hold violations.",
  "PL_RESIZER_HOLD_SLACK_MARGIN": 0.1,
  "GRT_RESIZER_HOLD_SLACK_MARGIN": 0.05,

  "//": "RUN_LINTER, LINTER_INCLUDE_PDK_MODELS - Disabling the linter is not recommended!",
  "RUN_LINTER": 1,
  "LINTER_INCLUDE_PDK_MODELS": 1,

  "//": "If you need a custom clock configuration, read the following documentation first:",
  "//": "https://tinytapeout.com/faq/#how-can-i-map-an-additional-external-clock-to-one-of-the-gpios",
  "CLOCK_PORT": "clk",

  "//": "Configuration docs: https://librelane.readthedocs.io/en/latest/reference/configuration.html",

  "//": "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",
  "//": "!!! DO NOT CHANGE ANYTHING BELOW THIS POINT !!!",
  "//": "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",

  "//": "Save some time",
  "RUN_KLAYOUT_XOR": 0,
  "RUN_KLAYOUT_DRC": 1,

  "//": "Don't put clock buffers on the outputs",
  "DESIGN_REPAIR_BUFFER_OUTPUT_PORTS": 0,

  "//": "Reduce wasted space",
  "TOP_MARGIN_MULT": 1,
  "BOTTOM_MARGIN_MULT": 1,
  "LEFT_MARGIN_MULT": 6,
  "RIGHT_MARGIN_MULT": 6,

  "//": "Absolute die size",
  "FP_SIZING": "absolute",

  "GRT_ALLOW_CONGESTION": 0,
  "OPENROAD_THREADS": 2,
  "DRT_OPT_ITERS": 20,
  "DRT_SAVE_DRC_REPORT_ITERS": 5,
  "ERROR_ON_TR_DRC": true,
  "ERROR_ON_KLAYOUT_DRC": true,

  "FP_IO_HLENGTH": 2,
  "FP_IO_VLENGTH": 2,

  "//": "CMOS5L Metal4 power pins meet the Tiny Tapeout 2.1 um minimum width",
  "FP_PDN_VWIDTH": 2.1,
  "FP_PDN_VPITCH": 38.87,

  "//": "Clock",
  "RUN_CTS": 1,

  "//": "Don't generate power rings",
  "FP_PDN_MULTILAYER": 0,

  "//": "MAGIC_DEF_LABELS may cause issues with LVS",
  "MAGIC_DEF_LABELS": 0,

  "//": "Only export pin area in LEF (without any connected nets)",
  "MAGIC_WRITE_LEF_PINONLY": 1,
  "meta": {
    "flow": "Classic",
    "substituting_steps": {
      "Odb.ApplyDEFTemplate": null,
      "-OpenROAD.GeneratePDN": "Odb.ApplyDEFTemplate",
      "+OpenROAD.GeneratePDN": "Project.PowerProgramSRAM",
      "Netgen.LVS": "Project.ProgramSRAMLVS"
    }
  },
  "MACROS": {
    "RM_IHPSG13_1P_256x16_c2_bm_bist": {
      "gds": [
        "pdk_dir::libs.ref/sg13cmos5l_sram/gds/RM_IHPSG13_1P_256x16_c2_bm_bist.gds"
      ],
      "lef": [
        "pdk_dir::libs.ref/sg13cmos5l_sram/lef/RM_IHPSG13_1P_256x16_c2_bm_bist.lef"
      ],
      "spice": [
        "pdk_dir::libs.ref/sg13cmos5l_sram/cdl/RM_IHPSG13_1P_256x16_c2_bm_bist.cdl"
      ],
      "nl": [],
      "spef": {},
      "lib": {
        "nom_typ_1p20V_25C": [
          "pdk_dir::libs.ref/sg13cmos5l_sram/lib/RM_IHPSG13_1P_256x16_c2_bm_bist_typ_1p20V_25C.lib"
        ],
        "nom_fast_1p32V_m40C": [
          "pdk_dir::libs.ref/sg13cmos5l_sram/lib/RM_IHPSG13_1P_256x16_c2_bm_bist_fast_1p32V_m55C.lib"
        ],
        "nom_slow_1p08V_125C": [
          "pdk_dir::libs.ref/sg13cmos5l_sram/lib/RM_IHPSG13_1P_256x16_c2_bm_bist_slow_1p08V_125C.lib"
        ]
      },
      "instances": {
        "program_store.i_sram": {
          "location": [
            300.0,
            34.02
          ],
          "orientation": "N"
        }
      }
    }
  },
  "PDN_CFG": "dir::pdn_cfg.tcl",
  "EXTRA_SPICE_MODELS": ["dir::sram_256x16_lvs.spice"],
  "ERROR_ON_LVS_ERROR": true,
  "PDN_MACRO_CONNECTIONS": [
    "program_store\\.i_sram VPWR VGND VDD! VSS!",
    "program_store\\.i_sram VPWR VGND VDDARRAY! VSS!"
  ],
  "FP_MACRO_HORIZONTAL_HALO": 8,
  "FP_MACRO_VERTICAL_HALO": 8,
  "RUN_MAGIC_DRC": false,
  "ERROR_ON_ILLEGAL_OVERLAPS": false
}
~~~

### Snapshot 4: src/sram_geometry.tcl

~~~tcl
# SPDX-License-Identifier: Apache-2.0
# Read column positions from the installed macro, including its irregular middle
# band. Both the PDN generator and the extension step use this geometry.
proc jp_column_clears_signal_pins {center} {
    set block [ord::get_db_block]
    # 2.1 um stripe plus 0.5 um clearance on each side. M4.b requires 0.21 um.
    set left [expr {$center - 1550}]
    set right [expr {$center + 1550}]
    foreach term [$block getBTerms] {
        if {[$term getSigType] in {POWER GROUND}} { continue }
        foreach pin [$term getBPins] {
            foreach box [$pin getBoxes] {
                if {[[$box getTechLayer] getName] != "Metal4"} { continue }
                if {$left < [$box xMax] && $right > [$box xMin]} { return 0 }
            }
        }
    }
    return 1
}

proc jp_sram_columns {} {
    set block [ord::get_db_block]
    # Classic normally applies the template after PDN generation. This design
    # applies it first so both regular and SRAM columns see the real pin bank.
    foreach term [$block getBTerms] {
        if {[$term getSigType] in {POWER GROUND}} { continue }
        set placed 0
        foreach pin [$term getBPins] {
            if {[$pin getPlacementStatus] in {PLACED FIRM LOCKED} &&
                [llength [$pin getBoxes]] > 0} { set placed 1 }
        }
        if {!$placed} {
            error "Signal pin [$term getName] requires template placement before PDN generation"
        }
    }
    set inst [$block findInst program_store.i_sram]
    if {$inst == "NULL"} { error "Program SRAM instance required" }
    if {[$inst getOrient] != "R0"} { error "Program SRAM requires N orientation" }
    if {[[$inst getMaster] getName] != "RM_IHPSG13_1P_256x16_c2_bm_bist"} {
        error "Unexpected program SRAM master"
    }
    set origin [$inst getOrigin]
    set columns [dict create]
    foreach pin {VDD! VDDARRAY! VSS!} {
        set term [$inst findITerm $pin]
        set net [$term getNet]
        if {$net == "NULL"} { error "Unconnected SRAM supply $pin" }
        set expected [expr {$pin == "VSS!" ? $::env(GND_NET) : $::env(VDD_NET)}]
        if {[$net getName] != $expected} { error "Incorrect SRAM supply $pin" }
        foreach port [[$term getMTerm] getMPins] {
            foreach box [$port getGeometry] {
                if {[[$box getTechLayer] getName] != "Metal4"} {
                    error "Unexpected SRAM supply layer"
                }
                if {[$box xMax] - [$box xMin] < 2100} { error "SRAM column too narrow" }
                set center [expr {[lindex $origin 0] + ([$box xMin] + [$box xMax]) / 2}]
                if {[dict exists $columns $center] && [dict get $columns $center] != $expected} {
                    error "Conflicting SRAM supplies"
                }
                dict set columns $center $expected
            }
        }
    }
    if {[dict size $columns] != 40} { error "Expected 20 power and 20 ground columns" }
    dict for {center net} $columns {
        if {![jp_column_clears_signal_pins $center]} {
            error "SRAM supply column at $center overlaps a Metal4 signal-pin corridor. Move the SRAM outside the I/O pin bank."
        }
    }
    return $columns
}
~~~

### Snapshot 5: src/pdn_cfg.tcl

~~~tcl
# SPDX-License-Identifier: Apache-2.0
# Metal4-only tile grid with SRAM-aligned columns. The following flow step
# extends these columns through the abstract macro blockage to its real pins.
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_global_connections.tcl
set_global_connections
source [file join [file dirname $::env(PDN_CFG)] sram_geometry.tcl]
set columns [jp_sram_columns]
set block [ord::get_db_block]
set core [$block getCoreArea]
set dbu [$block getDbUnitsPerMicron]
set inst [$block findInst program_store.i_sram]
set macro_box [$inst getBBox]
set_voltage_domain -name CORE -power $::env(VDD_NET) -ground $::env(GND_NET)
define_pdn_grid -name stdcell_grid -starts_with POWER -voltage_domain CORE -pins Metal4
proc jp_stripe {center net core dbu} {
    add_pdn_stripe -grid stdcell_grid -layer Metal4 -width 2.1 \
        -pitch 10000 -number_of_straps 1 -nets [list $net] \
        -offset [expr {($center - [$core xMin]) / double($dbu)}] -extend_to_boundary
}
dict for {center net} $columns { jp_stripe $center $net $core $dbu }
# Retain the ordinary grid away from the macro's x-range. Every stripe crossing
# the SRAM is one of its own supply columns, so a stripe cannot short its rails.
for {set center [expr {[$core xMin] + 10000}]} {$center < [$core xMax] - 2100} {incr center 38870} {
    foreach {shift net} [list 0 $::env(VDD_NET) 4100 $::env(GND_NET)] {
        set x [expr {$center + $shift}]
        if {$x > [$core xMax] - 1050} { continue }
        if {$x >= [$macro_box xMin] - 1550 && $x <= [$macro_box xMax] + 1550} { continue }
        if {![jp_column_clears_signal_pins $x]} { continue }
        jp_stripe $x $net $core $dbu
    }
}
add_pdn_stripe -grid stdcell_grid -layer Metal1 -width $::env(PDN_RAIL_WIDTH) -followpins
add_pdn_connect -grid stdcell_grid -layers {Metal1 Metal4}
~~~

### Snapshot 6: src/power_sram.tcl

~~~tcl
# SPDX-License-Identifier: Apache-2.0
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
read_current_odb
# Each LibreLane step starts a new process. Resolve supplies again before
# inspecting the saved grid or checking the extended macro connections.
source $::env(SCRIPTS_DIR)/openroad/common/set_power_nets.tcl
source $::env(PROGRAM_SRAM_GEOMETRY)
set block [ord::get_db_block]
set die [$block getDieArea]
set layer [[ord::get_db_tech] findLayer Metal4]
set columns [jp_sram_columns]
set wires [dict create]
foreach name [list $::env(VDD_NET) $::env(GND_NET)] {
    set net [$block findNet $name]
    dict set wires $name [odb::dbSWire_create $net ROUTED]
}
dict for {center name} $columns {
    set left [expr {$center - 1050}]
    set right [expr {$center + 1050}]
    odb::dbSBox_create [dict get $wires $name] $layer \
        $left [$die yMin] $right [$die yMax] STRIPE
    set term [$block findBTerm $name]
    if {$term == "NULL"} { error "Supply boundary pin required" }
    set pin [odb::dbBPin_create $term]
    $pin setPlacementStatus FIRM
    odb::dbBox_create $pin $layer $left [$die yMin] $right [$die yMax]
}
# Connectivity errors stop the flow. These checks include the macro supplies.
foreach name [list $::env(VDD_NET) $::env(GND_NET)] {
    check_power_grid -net $name
    # Replace the pre-extension metric only after this net passes its check.
    utl::metric_integer "design__power_grid_violation__count__net:$name" 0
}
utl::metric_integer design__power_grid_violation__count 0
puts "Program SRAM: extended 40 LEF-derived supply columns to tile boundaries"
write_views
~~~

### Snapshot 7: librelane_plugin_program_sram.py

~~~python
"""Connect the program SRAM to the CMOS5L tile's Metal4 power pins."""
from pathlib import Path

from librelane.steps import Step
from librelane.steps.openroad import OpenROADStep
from librelane.steps.netgen import LVS
from librelane.config import Variable
from librelane.common import Path as ConfigPath
from tools.netgen_json import normalize_sram_power_pins, repair_report
from librelane.state import State, DesignFormat


@Step.factory.register()
class PowerProgramSRAM(OpenROADStep):
    id = "Project.PowerProgramSRAM"
    name = "Connect Program SRAM Supply Columns"
    config_vars = OpenROADStep.config_vars + [
        Variable("PROGRAM_SRAM_GEOMETRY", ConfigPath,
                 "SRAM power-column geometry helper",
                 default=ConfigPath(str(Path(__file__).resolve().parent / "src" / "sram_geometry.tcl")))
    ]

    def get_script_path(self):
        return str(Path(__file__).resolve().parent / "src" / "power_sram.tcl")


@Step.factory.register()
class ProgramSRAMLVS(LVS):
    id = "Project.ProgramSRAMLVS"
    name = "Netgen LVS with SRAM report compatibility"

    def run(self, state_in, **kwargs):
        original = Path(state_in[DesignFormat.POWERED_NETLIST])
        adapted = Path(self.step_dir) / "netgen_powered_netlist.v"
        adapted.write_text(normalize_sram_power_pins(original.read_text()))
        # This copy is local to LVS. The original flow state and all other
        # consumers retain the OpenROAD powered netlist.
        lvs_state = State(state_in, overrides={
            DesignFormat.POWERED_NETLIST: ConfigPath(str(adapted))
        })
        return super().run(lvs_state, **kwargs)

    def run_subprocess(self, *args, **kwargs):
        result = super().run_subprocess(*args, **kwargs)
        report = Path(self.step_dir) / "reports" / "lvs.netgen.json"
        if report.is_file():
            count = repair_report(report)
            if count:
                self.warn(f"Preserved {count} literal identifier escapes in Netgen JSON. "
                          "Original report retained as lvs.netgen.json.original.")
        return result
~~~

### Snapshot 8: src/sram_256x16_lvs.spice

~~~spice
* SPDX-License-Identifier: Apache-2.0
* Abstract LVS pin interface derived from the official IHP SRAM LEF.
* Contiguous descending bus order lets Netgen infer full vector widths.
.SUBCKT RM_IHPSG13_1P_256x16_c2_bm_bist
+ A_ADDR[7] A_ADDR[6] A_ADDR[5] A_ADDR[4] A_ADDR[3] A_ADDR[2] A_ADDR[1] A_ADDR[0]
+ A_BIST_ADDR[7] A_BIST_ADDR[6] A_BIST_ADDR[5] A_BIST_ADDR[4] A_BIST_ADDR[3] A_BIST_ADDR[2] A_BIST_ADDR[1] A_BIST_ADDR[0]
+ A_BIST_BM[15] A_BIST_BM[14] A_BIST_BM[13] A_BIST_BM[12] A_BIST_BM[11] A_BIST_BM[10] A_BIST_BM[9] A_BIST_BM[8]
+ A_BIST_BM[7] A_BIST_BM[6] A_BIST_BM[5] A_BIST_BM[4] A_BIST_BM[3] A_BIST_BM[2] A_BIST_BM[1] A_BIST_BM[0]
+ A_BIST_CLK A_BIST_DIN[15] A_BIST_DIN[14] A_BIST_DIN[13] A_BIST_DIN[12] A_BIST_DIN[11] A_BIST_DIN[10] A_BIST_DIN[9]
+ A_BIST_DIN[8] A_BIST_DIN[7] A_BIST_DIN[6] A_BIST_DIN[5] A_BIST_DIN[4] A_BIST_DIN[3] A_BIST_DIN[2] A_BIST_DIN[1]
+ A_BIST_DIN[0] A_BIST_EN A_BIST_MEN A_BIST_REN A_BIST_WEN A_BM[15] A_BM[14] A_BM[13]
+ A_BM[12] A_BM[11] A_BM[10] A_BM[9] A_BM[8] A_BM[7] A_BM[6] A_BM[5]
+ A_BM[4] A_BM[3] A_BM[2] A_BM[1] A_BM[0] A_CLK A_DIN[15] A_DIN[14]
+ A_DIN[13] A_DIN[12] A_DIN[11] A_DIN[10] A_DIN[9] A_DIN[8] A_DIN[7] A_DIN[6]
+ A_DIN[5] A_DIN[4] A_DIN[3] A_DIN[2] A_DIN[1] A_DIN[0] A_DLY A_DOUT[15]
+ A_DOUT[14] A_DOUT[13] A_DOUT[12] A_DOUT[11] A_DOUT[10] A_DOUT[9] A_DOUT[8] A_DOUT[7]
+ A_DOUT[6] A_DOUT[5] A_DOUT[4] A_DOUT[3] A_DOUT[2] A_DOUT[1] A_DOUT[0] A_MEN
+ A_REN A_WEN VDD! VDDARRAY! VSS!
.ENDS RM_IHPSG13_1P_256x16_c2_bm_bist
~~~

### Snapshot 9: tools/netgen_json.py

~~~python
"""Preserve literal identifier backslashes in malformed Netgen JSON reports."""
import json
from pathlib import Path
import re


def normalize_sram_power_pins(text):
    """Adapt only the SRAM's supply-pin tokens to Netgen's Verilog dialect."""
    instance = re.compile(
        r'(\bRM_IHPSG13_1P_256x16_c2_bm_bist\s+\\program_store\.i_sram\s+\()(.*?)(\);)',
        re.DOTALL,
    )
    matches = list(instance.finditer(text))
    if len(matches) != 1:
        raise ValueError('Expected one program_store.i_sram in the powered netlist')
    match = matches[0]
    body = match[2]
    for pin in ('VDD!', 'VDDARRAY!', 'VSS!'):
        token = re.compile(r'\.\\?' + re.escape(pin) + r'\s*\(')
        body, count = token.subn('.' + pin + '(', body)
        if count != 1:
            raise ValueError(f'Expected one SRAM supply connection for {pin}')
    return text[:match.start(2)] + body + text[match.end(2):]


def repair_identifier_escapes(text):
    """Repair unsupported string escapes, preserving valid JSON escapes."""
    output = []
    in_string = False
    repairs = 0
    i = 0
    while i < len(text):
        char = text[i]
        if char == '"':
            in_string = not in_string
        if in_string and char == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            valid = next_char in '"\\/bfnrt' or (
                next_char == 'u' and re.fullmatch(r'[0-9a-fA-F]{4}', text[i + 2:i + 6])
            )
            if valid:
                output.append(text[i:i + 2])
                i += 2
                continue
            output.append('\\\\')
            repairs += 1
            i += 1
            continue
        output.append(char)
        i += 1
    return ''.join(output), repairs


def repair_report(path):
    """Validate first and retain the original report when repairing escapes.

    Structural errors still raise JSONDecodeError. Counts and comparisons are
    unchanged, so LibreLane's normal LVS metric/checker path remains active.
    """
    path = Path(path)
    original = path.read_text()
    try:
        json.loads(original)
        return 0
    except json.JSONDecodeError as error:
        if error.msg not in ('Invalid \\escape', 'Invalid \\uXXXX escape'):
            raise
    repaired, count = repair_identifier_escapes(original)
    json.loads(repaired)
    path.with_suffix(path.suffix + '.original').write_text(original)
    path.write_text(repaired)
    return count
~~~

### Snapshot 10: test/Makefile

~~~makefile
# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = defines.vh igorchip_top.v program_host.v program_memory.v sram_256x16_bb.v top.v
SRAM_MODEL_DIR = $(PWD)/ihp_sram
COMPILE_ARGS += -DSIM -DFUNCTIONAL
VERILOG_SOURCES += $(SRAM_MODEL_DIR)/RM_IHPSG13_1P_core_behavioral_bm_bist.v
VERILOG_SOURCES += $(SRAM_MODEL_DIR)/RM_IHPSG13_1P_256x16_c2_bm_bist.v

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

# Gate level simulation:
SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DSIM
# Foundry flip-flops and multiplexers use the companion UDP definitions.
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_udp.v
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13cmos5l/libs.ref/sg13cmos5l_io/verilog/sg13cmos5l_io.v
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_stdcell.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
~~~

### Snapshot 11: test/test_sram.py

~~~python
"""Exercise the foundry macro's masks, clocked reads and enable semantics."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SRAMTests(unittest.TestCase):
    def simulate(self, body, instance, extra_sources=()):
        self.assertTrue(shutil.which("iverilog") and shutil.which("vvp"))
        with tempfile.TemporaryDirectory(prefix="protocol-sram-") as directory:
            p = Path(directory)
            (p / "tb.v").write_text("`timescale 1ns/1ps\nmodule tb;\n" + instance +
                                    "\ninitial begin\n" + body +
                                    '\n$display("PASS"); $finish; end\nendmodule\n')
            sources = [ROOT / "test/ihp_sram/RM_IHPSG13_1P_core_behavioral_bm_bist.v",
                       ROOT / "test/ihp_sram/RM_IHPSG13_1P_256x16_c2_bm_bist.v", *extra_sources]
            compiled = subprocess.run(["iverilog", "-g2012", "-DSIM", "-DFUNCTIONAL",
                                       f"-I{ROOT / 'src'}", "-s", "tb", "-o", str(p / "sim"),
                                       str(p / "tb.v"), *map(str, sources)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(["vvp", str(p / "sim")], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)

    def test_macro_partial_mask_enable_and_output_hold(self):
        self.simulate('''
            #1; tick();
            wen=0; ren=1; tick(); if(q!==16'hA55A) $fatal(1,"full word");
            wen=1; ren=0; bm=16'h00F0; d=16'h0030; tick();
            if(q!==16'hA55A) $fatal(1,"write-only must hold output");
            wen=0; ren=1; tick(); if(q!==16'hA53A) $fatal(1,"bit mask");
            men=0; wen=1; d=0; bm=16'hFFFF; tick();
            if(q!==16'hA53A) $fatal(1,"disabled output");
            men=1; wen=0; tick(); if(q!==16'hA53A) $fatal(1,"disabled write");
            addr=0; ren=0; tick(); if(q!==16'hA53A) $fatal(1,"read disabled");
        ''', '''
            reg clk=0, men=1, wen=1, ren=0;
            reg [7:0] addr=255;
            reg [15:0] d=16'hA55A, bm=16'hFFFF;
            wire [15:0] q;
            RM_IHPSG13_1P_256x16_c2_bm_bist memory(
              .A_CLK(clk), .A_MEN(men), .A_WEN(wen), .A_REN(ren),
              .A_ADDR(addr), .A_DIN(d), .A_BM(bm), .A_DLY(1'b1), .A_DOUT(q),
              .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
              .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(8'd0),
              .A_BIST_DIN(16'd0), .A_BIST_BM(16'd0));
            task tick; begin #5; clk=1; #5; clk=0; end endtask
        ''')

    def test_wrapper_byte_preservation_read_edge_and_reset_retention(self):
        self.simulate('''
            #1; tick(); high=1; d=8'hA5; tick();
            we=0; tick(); if(q!==16'hA55A) $fatal(1,"byte ordering");
            we=1; high=0; d=8'h3C; tick(); we=0; tick();
            if(q!==16'hA53C) $fatal(1,"opposite byte preserved");
            addr=0; if(q!==16'hA53C) $fatal(1,"read must await falling edge");
            addr=255; rst_n=0; tick(); if(q!==16'hA53C) $fatal(1,"disabled memory");
            rst_n=1; tick(); if(q!==16'hA53C) $fatal(1,"reset retains program");
        ''', '''
            reg clk=1, rst_n=1, we=1, high=0;
            reg [7:0] addr=255, d=8'h5A;
            wire [15:0] q;
            program_memory memory(.clk(clk), .rst_n(rst_n), .address(addr),
              .write_enable(we), .high_byte(high), .write_data(d), .read_data(q));
            task tick; begin #5; clk=0; #5; clk=1; end endtask
        ''', [ROOT / "src/program_memory.v"])
~~~

### Snapshot 12: .github/workflows/gds.yaml

~~~yaml
name: gds

on:
  push:
  pull_request:
  workflow_dispatch:

concurrency:
  group: gds-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  gds:
    runs-on: ubuntu-24.04
    timeout-minutes: 180
    steps:
      - name: checkout repo
        uses: actions/checkout@v6

      - name: Build GDS
        timeout-minutes: 150
        uses: TinyTapeout/tt-gds-action@ihp-cmos5l
        with:
          pdk: ihp-sg13cmos5l

      - name: Preserve physical-flow diagnostics
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: gds-diagnostics-${{ github.run_attempt }}
          if-no-files-found: warn
          retention-days: 14
          path: |
            src/config*.json
            src/user_config*.json
            runs/wokwi/**/config*.json
            runs/wokwi/**/*.log
            runs/wokwi/**/*.rpt
            runs/wokwi/**/*.drc
            runs/wokwi/**/*.json
            runs/wokwi/**/*.json.original
            runs/wokwi/**/netgen_powered_netlist.v
            runs/wokwi/**/*.odb
            runs/wokwi/**/*.sdc
            runs/wokwi/**/*.guide

  precheck:
    needs: gds
    runs-on: ubuntu-24.04
    steps:
      - name: Run Tiny Tapeout Precheck
        uses: TinyTapeout/tt-gds-action/precheck@ihp-cmos5l

  gl_test:
    needs: gds
    runs-on: ubuntu-24.04
    steps:
      - name: checkout repo
        uses: actions/checkout@v6

      - name: GL test
        uses: TinyTapeout/tt-gds-action/gl_test@ihp-cmos5l

  viewer:
    needs: gds
    if: github.event_name != 'pull_request' && github.ref == format('refs/heads/{0}', github.event.repository.default_branch)
    runs-on: ubuntu-24.04
    permissions:
      pages: write # to deploy to Pages
      id-token: write # to verify the deployment originates from an appropriate source
    steps:
      - uses: TinyTapeout/tt-gds-action/viewer@ihp-cmos5l
~~~
