# SRAM routing failure and corrective architecture

Historical analysis: the root manifest now selects the [full-inference logic fallback](../asic/neural_logic/README.md). SRAM sources and run evidence are preserved; they are not the current chip.

The physical target is the neural inference core `tt_um_wlmoi_igor_neural_sram`, on the pinned Tiny Tapeout CMOS5L 8x4 template. FPGA, motor and legacy safety-gate RTL are separate regressions and are excluded from this chip's active synthesis manifest.

`GRT-0102 Start extra iteration n/50` is a bounded attempt to remove routing overflow. Another batch can begin after the router relaxes clock NDR rules. It is not an RTL inference loop. Both failed runs ended at `GRT-0116` because routing overflow remained.

| Physical build | Metal3 overflow | Total overflow | Wirelength (um) |
|---|---:|---:|---:|
| [Two 4096x16 banks, a945372](https://github.com/sundaysiagian/peruri-iseedesign/actions/runs/38594927507) | 28,328 | 28,882 | 1,890,928 |
| [Twelve 512x16 banks, f4d7496](https://github.com/sundaysiagian/peruri-iseedesign/actions/runs/38597710971) | 32,056 | 33,311 | 2,189,217 |

The twelve-bank diagnostics show 2,869 sequential standard cells, 17,452 standard cells before timing repair, and 23,474 afterward. Hold repair inserted 3,114 buffers. Standard-cell area grew from 275,611 to 353,656 um^2. Inputs and both hidden activation vectors were register arrays, with wide indexed read muxes feeding two MACs. SRAM obstructions leave fewer usable signal tracks around these cells. Extra parameter banks added clocks, selection logic and macro halos without removing the activation registers. This is a major congestion contributor inferred from the mapped circuit and failed routing reports; the revised physical run must confirm the improvement.

Pre-extension `GeneratePDN` warnings are retained in the flow's warning summary. The subsequent `Project.PowerNeuralSRAM` step connected the macro rails and reported zero power-grid violations. These initial warnings are separate from the later global-routing failure. Neither previous run reached final DRC, LVS or routed timing qualification.

The first activation-SRAM architecture stored all 6,020 parameter words in six 1024x16 SRAMs and all 152 input/hidden activation words in two 256x16 SRAMs. Both stores deliver an even/odd pair on rising clock edges. Two MACs consume a weight pair and an activation pair per cycle. Two operands are prefetched before the neuron-output store, and SRAM read outputs hold during that write, preserving the 3,080-cycle schedule.

That revision retained all eight required SRAMs in generic synthesis and reduced register storage from 2,869 to 413 bits. No inferred parameter/activation array remains. Four outputs and transient pipeline/control state remain registers. The 50 MHz target is unchanged; 61.6 us is the latency calculation at that target, pending physical timing acceptance.

Acceptance requires all three currently specified SRAMs with their correct types in the reachable submission hierarchy; zero global-routing overflow, detailed-routing/KLayout DRC, integration LVS and power-grid errors; zero setup/hold/slew/cap violations at the configured corners; pin-level gate simulation and Tiny Tapeout precheck. The viewer deploys only after these checks pass and its downloaded OASIS hash matches that run's submission.

## Eight-macro result and clock/pin-access correction

[Build 1d4fbed](https://github.com/sundaysiagian/peruri-iseedesign/actions/runs/38644401439) reached routing with 7,049 standard cells, 88,729.6 um^2 standard-cell area, 583 inserted hold buffers, and zero post-extension power-grid errors. Wirelength fell to 926,676 um; global routing still failed with Metal2/3/4 overflow counts 3,092/15,447/158 (18,697 total). Average routing-resource usage was only 27.05%. Final routed timing, DRC and LVS were not reached.

The placed DEF has two rows of 336.46-um SRAMs at y=10 and y=359, leaving a 12.54-um gap below the second row. All signal pins are actually on the lower face of each macro. Standard cells cluster around this gap and the vertical corridors. This is evidence of a local pin-access/channel bottleneck; low average usage does not establish routeability.

The next revision used two 4096x16 parameter macros plus the same two 256x16 activation macros. This removed the narrow lower-face access corridor of the second row, six-to-one bank read muxes, and four parameter-clock sinks. Generic register storage was 411 bits; the runtime parameter address map and 3,080-cycle two-MAC schedule remained unchanged.

NDR is a non-default routing rule. The previous CTS command explicitly used `-apply_ndr half`: increased spacing on the upper half of clock-tree branches. A `GRT-0273 Disabled NDR` warning means the router is falling back to default rules for a congested clock net; it does not disable the clock. The fatal failure is the remaining `GRT-0116` overflow. [OpenROAD documents 2x-spacing NDR strategies](https://openroad.readthedocs.io/en/latest/main/src/cts/README.html) and [LibreLane exposes the corresponding configuration](https://librelane.readthedocs.io/en/latest/reference/step_config_vars.html).

The revised clock configuration applies a main-trunk NDR policy (`root_only`) and enables obstruction-aware CTS buffering. The global router can still relax that NDR when congestion persists. The normal routing capacity margin is retained. A routing wrapper adds congestion location reports while preserving all original arguments, errors, antenna handling and acceptance checks. A failing routing report remains a failing build; root-only NDR still requires setup/hold/slew/cap qualification.

## Four-macro result and lower-face access channel

[Build 27275d2](https://github.com/sundaysiagian/peruri-iseedesign/actions/runs/38647197627) still failed global routing, but total overflow fell to 5,936 (Metal2/3/4: 710/5,201/25) and wirelength to 762,213 um. The coordinate report contains 5,144 markers: 5,422 weighted overflow units have centers inside macro footprints, and 5,442 occur on zero-capacity edges. The placed DEF confirms zero standard-cell origins inside the SRAMs. The remaining problem is routes crossing blocked macro regions, rather than illegally placed cells.

The earlier description of opposing signal-pin faces was incorrect. Parsing every official LEF signal-pin rectangle shows all 114 signals of each 4096x16 macro on local y=0..0.26 um; all 106 signals of each 256x16 macro are also on its lower face. The revised weight-macro origins are y=80 um, providing a wider lower access corridor. Their 618.3-um height plus 6-um halo ends at 704.3 um, within the approved 706.86-um core bound. Target placement density is 45% to allow more logic near the lower interface. Clock period, process stack, NDR strategy and strict routing/DRC/LVS acceptance remain unchanged.

## Single packed parameter SRAM and complete Igor inference

[Build a1b7ff2](https://github.com/sundaysiagian/peruri-iseedesign/actions/runs/38649494420) still failed routing with 5,844 overflow units and 762,357 um wirelength. Widening the lower access channel alone therefore did not resolve the obstruction crossings.

The current architecture replaces both 4096x16 macros with one official `RM_IHPSG13_1P_2048x64_c2_bm_bist` from the same pinned PDK. Its 2,048 rows each hold four 16-bit words: capacity remains 8,192 words, of which all 6,020 weights and biases are runtime-programmable. The local row is address[12:2], and address[1:0] selects a masked quarter write. A latched address[1] selects either the lower or upper pair for the two MAC lanes. No coefficient quantization, constant-ROM substitution, or upload-interface change is required. Tests check every word and pair, individual bit/byte masks and preservation of adjacent quarters.

The 784.48 x 626.70 um parameter macro is placed at (900,70), with its halo ending at y=702.70 inside the core. Two activation SRAMs are placed at (600,180) and (600,340). This leaves a broad area to the left of the parameter macro for compute logic and routing, instead of splitting that logic between two tall obstructions. There are three physical SRAMs in total, one for all parameters and two for activation pairs. Generic synthesis retains the exact three masters and uses 412 register bits. The 3,080-cycle schedule and 50 MHz target remain unchanged; the new physical run must prove congestion-free routing and timing.


## Packed-SRAM physical result and activation spacing

[Build b9be124](https://github.com/sundaysiagian/peruri-iseedesign/actions/runs/38652219598) passed all six offline integration tests on Linux, synthesis retention, 100-vector RTL regression and generic-netlist simulation. Global routing reduced wirelength to 483,386 um and overflow to 76. Every congestion marker is within x=601.2..831.6 and y=277.2..363.6 um, around the two activation SRAMs and the gap between their original rows. The large parameter SRAM region has no remaining overflow markers. Post-CTS setup worst slack is +7.47 ns and power-grid errors are zero, while 154 hold violations remain at that intermediate stage; these are not final timing acceptance.

The current physical correction aligns both activation SRAMs at y=580 um, x=320 and 610 um. Their lower signal-pin faces now open toward the broad compute area below, with 53.2 um between footprints. Their upper edges plus 6-um halo reach 704.78 um within the 706.86-um core limit. The parameter position and all RTL remain unchanged. Routing capacity margins, NDR policy and strict congestion/DRC/LVS/timing checks remain enabled. The next build must prove that this local obstruction correction resolves the remaining overflow.

## Routed result and final integration corrections

[Build 74b15b5](https://github.com/sundaysiagian/peruri-iseedesign/actions/runs/38653087038) reached zero global-routing overflow, zero detailed-routing DRC, zero KLayout DRC and zero power-grid errors. Final setup and hold violations were zero at all three configured corners. The actual assembled GDS contains one 2048x64 parameter macro and two 256x16 activation macros. Remaining acceptance failures were 252 Magic LEF-abstraction overlaps and 195 LVS errors; electrical limits additionally showed 46 slew and 5 capacitance violations.

The newly generated 2048x64 abstract SPICE interface had copied the interleaved physical LEF pin order. Its first data port was bit 32, so Netgen inferred a 33-bit bus for each of five 64-bit interfaces. Five missing groups of 31 nodes explain the 155-net discrepancy. The corrected interface groups every bus contiguously from its highest bit down to bit 0, preserving exactly the same 355 physical pin names. Integration tests now enforce ordering and contiguity as well as pin-set equality. Replaying the original extracted SPICE and powered netlist with the corrected interface produces a unique match: 6,548 devices and 6,636 nets on both sides. The old interface and a VDDARRAY-to-ground fault still fail comparison. This replay uses local Netgen 1.5.270 with the pinned PDK models and LibreLane 3.1.0.dev3 setup script; the next CI run must confirm its pinned tool result.

All 252 Magic feedback rectangles are `obsm4`/`metal4` overlaps within an intended SRAM footprint and the exact 2.1-um extended supply stripes: 166 on the parameter macro and 44/42 on the activation macros. This is the LEF abstraction issue described in section 9.5 of the supplied guide. A scoped replacement checker requires zero assembled-GDS DRC, routing DRC and power-grid errors first, then verifies every feedback type, scaled coordinate, macro identity, footprint and supply column. Unrecognized overlaps fail. The original Magic count remains intact, with separate qualified and unqualified counts; the generic error setting remains enabled. Normal LVS and physical precheck remain mandatory.

Post-GRT design repair and timing repair were disabled in the previous resolved configuration. They are now enabled at all three corners, with a 150-um signal-wire limit and 25-percent slew/capacitance repair margins. Timing repair preserves inserted buffers. The 0.064-pF macro output limit and all timing/electrical acceptance thresholds remain unchanged. A new physical run must demonstrate zero residual electrical violations and repeat routing, DRC, LVS and setup/hold acceptance.
