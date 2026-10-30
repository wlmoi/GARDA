# Area and timing

The supplied physical-flow log failed at OpenROAD global placement with
`GPL-0301`: utilization was 113.101%, exceeding the available 6x4 core area.
Changing placement density cannot make cells occupying more than the core fit.

The register-memory revision used 256 x 16-bit program storage with **one shared read port**,
replacing the previous 512 x 16-bit array with instruction, literal, and host
read paths. LDI fetches its literal on the context's next grant, and host DATA
readback requires software pause. Immediate push-pull/open-drain instructions
reduce the concurrent UART TX/RX + SPI + I2C demonstration from 335 words to
245 words, retaining all four contexts within the smaller storage budget.
The enhanced UART start qualifier and framing check bring the current
concurrent demo to 254 words within the same storage capacity.

Local synthesis used Yosys 0.69 via YoWASP, `synth -flatten -noabc`,
`dfflibmap`, and ABC mapping against the official IHP typical Liberty library.
The supplied core area is 902417.242 um^2. The results below are mapped cell
areas, not post-placement utilization or timing results.

| Metric | Previous RTL | Compact RTL |
|---|---:|---:|
| Program storage | 512 x 16 bits | 256 x 16 bits |
| Program read ports | 3 | 1 |
| Mapped IHP cell area | 898632.0630 um^2 | 395106.8436 um^2 |
| Mapped IHP cells | 49985 | 19493 |
| Cell area / supplied core area | 99.58% | 43.78% |

The mapped area reduction is approximately 56.0%. The compact result is below
both 100% capacity and the configured 60% placement density target, with room
for physical-flow overhead. It does not prove routing or timing closure.

Library source:
[IHP typical standard-cell Liberty](https://raw.githubusercontent.com/IHP-GmbH/IHP-Open-PDK/main/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib).
The measured file's SHA-256 is
`7677a8918689f452e80405ad16a83e744709342574f2aedcc507c2758986b396`.

To reproduce the compact synthesis estimate, provide that Liberty file and
install Yosys or `yowasp-yosys` in the Python environment:

```text
python -m tools.synth_area --register-memory --liberty build/area/sg13g2_typ.lib
```

The tool writes the synthesis script, log, mapped netlist, functional cell
models, memory structure, and metrics under `build/area/`. It exits unsuccessfully
if mapped area exceeds the 60% budget or program memory has multiple read ports.
The generated metrics and logs are local build artifacts, not committed files.

The mapped netlist passed the external-pin cocotb regression using zero-delay
functional cell models generated from the same Liberty library. This validates
functional behavior after synthesis; it is not an SDF timing simulation.

The full LibreLane/OpenROAD flow was not rerun locally: Docker's Linux engine
is unavailable. GitHub subsequently completed the Tiny Tapeout GDS build,
precheck, gate-level test, and viewer successfully on SG13G2 for commit `269b380`:
[passing physical-flow run](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/37646552561).
This CI result is separate from the local synthesis estimates above. Detailed
post-route area/timing metrics have not been extracted here; board validation
remains pending.

The current competition workflow targets CMOS5L using the official
`ihp-cmos5l` action and `ihp-sg13cmos5l` PDK. The mapping figures above use
the recorded SG13G2 library and core area. The [CMOS5L run for commit 3c099bd](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38068425041)
completed GDS generation and the viewer. The current configuration supplies
2.1 micrometer Metal4 power straps to meet Tiny Tapeout's pin-width requirement.
An isolated OpenROAD check confirms the generated strap width, and the local
CMOS5L mapped netlist passes the gate-level Makefile regression with the
official cell and UDP models. See [verification evidence](VERIFICATION.md).
The SRAM-backed revision subsequently passes full-layout precheck in the
[CMOS5L run for commit 1649be6](https://github.com/wlmoi/General-Purpose-Protocol-ASIC_JaneStreet/actions/runs/38425106175).
Detailed timing closure remains a separate qualification stage.

## CMOS5L SRAM integration estimate

A matched Yosys 0.33 comparison uses the same CMOS5L typical standard-cell
Liberty library for the register-memory and SRAM implementations. The SRAM
footprint comes from its official LEF SIZE declaration.

| Component | Area in square micrometers |
|---|---:|
| Register-memory reference mapping | 384634.2024 |
| SRAM implementation mapped logic | 58741.6914 |
| IHP 256 x 16-bit SRAM footprint | 28127.1040 |
| Combined logic and SRAM estimate | 86868.7954 |

The combined estimate is approximately 77.4% smaller than the reference and
9.6% of the supplied core area. These estimates include the macro footprint.
Placement overhead, routed timing, DRC, LVS, and precheck are full-flow checks.

```text
python -m tools.synth_area --liberty /path/to/sg13cmos5l_stdcell_typ_1p20V_25C.lib --macro-lef /path/to/RM_IHPSG13_1P_256x16_c2_bm_bist.lef
```

The tool verifies that synthesis retains exactly one SRAM instance and records
logic area and macro area separately. See [SRAM integration](SRAM.md) for
the physical configuration and supply-connectivity evidence.

## Routed timing qualification

The final metrics for commit `1649be6` record a worst setup slack of
approximately -2.637 ns at the 20 ns clock target. There are 253 setup
violations, 26 maximum-slew violations, and 11 maximum-capacitance
violations. Hold checks pass. These measurements establish the remaining
timing-repair work before qualifying 50 MHz operation across the reported
process corners. UART timing generation remains configurable for the core
clock selected after timing qualification.
