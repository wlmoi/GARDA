# Area: Parallel8 core, UART, and Tiny Tapeout

Analysis: 19 October 2026. All FPGA figures below are for the **Parallel8 921600-baud implementation**, not the baseline serial core. Physical ASIC figures come from the imported IHP CMOS5L Tiny Tapeout reports. Calculations and source hashes: [parallel8_area.json](../evidence/area_analysis/parallel8_area.json). Reproduce from repository root: `python fpga/scripts/report_parallel8_area.py`.

**Primary FPGA visual evidence: [18 original Quartus GUI screenshots](../evidence/quartus_gui/README.md)**, captured through Computer Use on 19 October 2026. See [actual core/UART hierarchy](../evidence/quartus_gui/04_core_uart_resources.jpg), [memory capacity](../evidence/quartus_gui/06_memory_dsp_capacity.jpg), [timing](../evidence/quartus_gui/09_multicorner_timing.jpg) and [native Power Analyzer](../evidence/quartus_gui/12_power_summary_maximum.jpg). No reconstruction or annotation was applied to the screenshot bytes.

Earlier [browser report-reader images](../evidence/parameter_screenshots/README.md) remain document visualizations, not native GUI proof. ASIC areas and calculated percentages are outside the Quartus GUI evidence scope; their original source metrics and derivations remain below.

## 1. Pure core versus core with UART

The Fitter's **Resource Utilization by Entity** table isolates the core hierarchy inside the accepted board build. These are post-fit hierarchical attributions, not a separately fitted standalone-core experiment. Fractional ALMs are Quartus allocation/packing estimates; physical devices do not contain fractional ALMs.

| Scope | ALMs needed | Device ALM utilization | Combinational ALUTs | Registers | M10K | DSP |
|---|---:|---:|---:|---:|---:|---:|
| **Pure neural core**, including its parameter memory and activations | **2,402.7** | **5.7330%** | **2,324** | **4,747** | **64** | **8** |
| Core + UART policy interface, parser, buffering and guards | **3,300.7** | **7.8757%** | **3,359** | **6,272** | **64** | **8** |
| Complete fitted board top, including reset/KEY/LED glue | **3,303.0** | **7.8812%** | **3,364** | **6,277** | **64** | **8** |
| UART policy/interface overhead, by subtraction | **898.0** | **2.1427 percentage points** | **1,035** | **1,525** | **0 additional** | **0 additional** |

Sources: [board row, line 1411](../experiments/parallel8/output_files/igor_src_policy.fit.rpt:1411), [UART policy row, line 1412](../experiments/parallel8/output_files/igor_src_policy.fit.rpt:1412), [core row, line 1413](../experiments/parallel8/output_files/igor_src_policy.fit.rpt:1413). The table's note says the number outside parentheses includes sub-entities; the parenthesized number is the entity alone. Therefore the core is **2,402.7**, not its parenthesized 2,293.1: excluding activation children would undercount the core.

Denominator: 41,910 ALMs on the selected 5CSEBA6U23I7. Example: `2402.7 / 41910 × 100 = 5.7330%`. The FPGA is comfortably within its reported resource capacities for this fitted design; memory and DSP are separate capacity constraints.

### What “UART” includes

The complete interface overhead is more than a serial shift register: observation/frame buffering, CRC, parser, range checking, load/start/output sequencing, fault handling, timeout and lease logic are included in the policy hierarchy.

The actual byte-level UART receiver is **38.3 ALMs, 63 ALUTs, 63 registers**; the transmitter is **21.5 ALMs, 39 ALUTs, 33 registers**. Together those two leaves account for **59.8 ALMs**, 102 ALUTs and 96 registers. Source: [receiver line 1438](../experiments/parallel8/output_files/igor_src_policy.fit.rpt:1438), [transmitter line 1439](../experiments/parallel8/output_files/igor_src_policy.fit.rpt:1439).

The remaining approximately **838.2 ALMs** of the 898.0 difference belong to surrounding interface/control logic and hierarchical allocation effects. The policy's exclusive reported value is 838.0 ALMs; small differences arise from rounded hierarchical packing attribution. Do not describe all 898 ALMs as the UART serializer itself.

## 2. LUT/logic and SRAM percentages on FPGA

Cyclone V uses **ALMs and ALUTs**. A generic “LUT count” is ambiguous; use the exact names and counts above. ALMs include packing of logic and registers; ALUTs are not an independent additional area to add to ALMs.

| Resource class | Used by core | Capacity / denominator | Utilization |
|---|---:|---:|---:|
| Logic capacity | 2,402.7 ALMs | 41,910 ALMs | **5.7330%** |
| Block-memory capacity | 64 M10Ks | 553 M10Ks | **11.5732%** |
| Configured memory bits | 524,288 bits = 64 KiB | 5,662,720 bits | **9.2586%** |
| Multiplier capacity | 8 DSP blocks | 112 DSP blocks | **7.1429%** |

These percentages have different denominators: **5.7330% + 11.5732% is not a valid total silicon-area percentage**. M10K count and configured memory bits are also two views of the same memory, not two extra resources. Source capacities: [Fitter summary](../experiments/parallel8/output_files/igor_src_policy.fit.summary:8).

Within the *complete design's ALM-needed allocation*, the core accounts for **72.7430%**, the UART policy overhead **27.1874%**, and board glue approximately **0.0696%**. This answers how logic resources are distributed; it does not include a physical weighting for M10K or DSP silicon.

For a literal packing view, the full Fitter report also lists 4,113 ALMs used in final placement: 1,044 shared logic/register ALMs, 1,295 logic-only ALMs and 1,774 register-only ALMs. The headline 3,303 ALMs needed includes dense-packing recoverability and unavailable-ALM adjustments. Do not confuse placement occupancy with ALMs needed. Source: [Fitter lines 487–495](../experiments/parallel8/output_files/igor_src_policy.fit.rpt:487).

The 64 KiB is configured on-chip parameter **ROM implemented in FPGA SRAM-based block memory**. It contains 18,051 active 16-bit parameters (36,102 bytes) plus bank/layout padding. UART does not add M10K blocks. The core's other input/hidden/accumulator storage is reflected in registers and logic; it must not be called another fabricated SRAM macro without a corresponding ASIC mapping.

## 3. Tiny Tapeout physical area and SRAM split

Imported design: **`tt_um_igorchip`**, IHP **`ihp-sg13cmos5l`**, project allocation **6×4 tiles**. The measured rectangle is authoritative for this imported layout; the generic approximate tile dimensions in `info.yaml` are not a substitute for final die/core measurements.

| Physical category | µm² | mm² | % of allocated die |
|---|---:|---:|---:|
| **Allocated user-design die rectangle** | **916,214** | **0.916214** | **100.0000%** |
| Placeable core rectangle | 902,417 | 0.902417 | 98.4941% |
| Mapped standard cells | 69,830.8 | 0.0698308 | **7.6217%** |
| One 256×16 SRAM macro | 28,127.1 | 0.0281271 | **3.0699%** |
| **Standard cells + SRAM footprint** | **97,957.9** | **0.0979579** | **10.6916%** |

Source keys: `design__die__area`, `design__core__area`, `design__instance__area__stdcell`, `design__instance__area__macros` in [final metrics](../evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/final/metrics.json:85). The 6×4 setting is in [info.yaml](../../info.yaml:14). The macro contains **4,096 bits = 512 bytes**. Area converts as `mm² = µm² / 1,000,000`.

If the denominator is **only standard-cell + SRAM footprint**, the split is **71.2865% standard cells** and **28.7135% SRAM**. If the denominator is the **placeable core rectangle**, combined footprint is **10.8551%**. Always state the denominator beside the percentage.

An ASIC does not contain FPGA LUTs after standard-cell mapping. “Logic area” here includes combinational cells, flip-flops, clock/repair buffers and other standard cells; it is not purely combinational LUT logic. The report separately lists 34,493.6 µm² multi-input combinational cells and 19,742.5 µm² sequential cells; these are already within the standard-cell total.

The report's larger `design__instance__area = 895,165 µm²` includes substantial physical fill-cell area (797,207 µm²). It must not be presented as 895,165 µm² of functional compute. Conversely, 10.69% functional footprint does not mean every remaining square micrometre can be allocated freely: routing, power, macro placement and physical-only cells impose constraints. The allocated rectangle is this user block's layout, not the entire multi-project shuttle wafer or package die.

## 4. Requested “assume both are the same” scenario

For an **illustrative common-area budget**, assume the entire FPGA core+UART logic maps to the imported ASIC's 69,830.8 µm² standard-cell budget, and assume both use that imported single SRAM footprint. Allocate logic according to fitted ALM ratios:

```text
Core logic share = 2402.7 / 3300.7 = 72.79365%
Core logic budget = 69830.8 × 2402.7 / 3300.7
                  = 50832.3880 µm² = 0.0508323880 mm²
UART policy logic budget = 69830.8 − 50832.3880
                         = 18998.4120 µm² = 0.0189984120 mm²
Assumed SRAM budget = 28127.1 µm² = 0.0281271 mm²
Assumed core + SRAM budget = 0.0789594880 mm²
Assumed core + UART + SRAM budget = 0.0979579 mm²
```

**These are conditional budget allocations only. They are not synthesized neural-core ASIC area estimates and do not verify that both implementations are equivalent.** ALM ratios cannot supply the missing standard-cell multiplier/register/mux mapping, and the two designs have different functions and memory capacities. The physical report verifies the protocol-engine footprint, while the FPGA report verifies neural-core FPGA resources.

This scenario is useful for explaining how one would distribute a fixed logic budget. Its assumed one-macro memory is incompatible with the full parameter capacity if implemented using the same writable SRAM macro. Use the capacity calculation below before making a fit claim.

## 5. Capacity-based ASIC memory estimate from FPGA resources

The imported SRAM has a measured footprint of 0.0281271 mm² for 512 bytes. Under a simple **replication of this same SRAM macro**:

| Storage policy | Required bytes | 512-byte macros | Memory footprint only |
|---|---:|---:|---:|
| Preserve allocated FPGA parameter capacity | 65,536 | **128** | **3.6002688 mm²** |
| Store only active weights/bias, densely packed | 36,102 | **71** | **1.9970241 mm²** |

Formula: `N = ceil(bytes / 512)`; `A_memory = N × 0.0281271 mm²`. Both exceed the imported 0.916214 mm² block before adding neural logic. The dense 71-macro case is a capacity-only estimate: lane banking, synchronous read timing and addressing may require a different allocation. Neither figure includes logic, routing, macro spacing, power or clock overhead.

This does not prove the neural network can never fit a different ASIC implementation. Fixed-weight ROM, larger/different-density macros, compressed weights, narrower validated parameters or logic synthesis can change area substantially. It shows why one 512-byte macro cannot validate a 64-KiB parameter-memory claim. Those alternatives require their own mapped implementation and numerical regression.

## 6. What is verified and what remains an estimate

- **Verified from existing fitted report:** core-only and UART hierarchy resources, M10K/DSP allocation, and all arithmetic ratios shown for FPGA.
- **Verified from imported physical report:** actual Tiny Tapeout block rectangle, mapped standard-cell and SRAM footprints for its recorded protocol-engine design. This area analysis makes no new tapeout sign-off claim.
- **Conditional estimate:** same-footprint illustrative allocation and same-macro replicated memory area. Neither is physical validation of a neural ASIC.
- **To verify neural ASIC area:** map the same Parallel8 arithmetic/model/interface to the chosen IHP library and memory implementation, report core-only and core+UART area separately, then place/route and compare identical source/netlist/GDS identities. DSP operations must become real ASIC cells/macros rather than disappear from the estimate.

Recommended wording for the project: **“The Parallel8 neural core occupies 2,402.7 fitted ALMs, 64 M10K blocks and 8 DSPs; the complete UART policy interface raises logic utilization to 3,300.7 ALMs without additional block RAM or DSP. A separate IHP Tiny Tapeout physical implementation provides a traceable reference footprint of 0.0979579 mm² for standard cells plus SRAM within a 0.916214 mm² allocated block.”**
