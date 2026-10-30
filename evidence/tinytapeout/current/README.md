# TinyTapeout verification and routing repair

**iSeeDesignITB | 15 October 2026 | `tt_um_wlmoi_igor_neural_logic`**

This is the fixed-model neural accelerator submission. The full FPGA DWA planner and safety/security gate are separate RTL designs. It is not accurate to describe this TinyTapeout submission as the complete robot controller.

The model contains 24 inputs, two hidden layers of 64 neurons, and four outputs. All 6020 Q8.8 model words are immutable logic. Activation storage uses flip-flops. The active submission instantiates no hard SRAM macro.

## Evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Independent fixed-point reference against RTL | PASS, 100 vectors and 400 outputs | [RTL log](rtl.log) |
| Complete model readback | PASS, 6020 words | [Pin results](pin_results.json) |
| Fixed compute schedule | 3080 cycles for every tested vector | [RTL log](rtl.log) |
| Generic synthesized netlist | PASS, one vector and four outputs | [Generic log](generic.log) |
| Submission pins through cocotb | PASS, two tests | [JUnit XML](cocotb_rtl.xml) |
| Malformed host commands | PASS, nine cases and reset recovery | [Guard results](pin_guard_results.json) |
| APPEND after COMMIT | PASS, fault is visible and outputs are zero | [Cocotb log](cocotb_rtl.log) |
| Corrected global routing | PASS, zero overflow on every layer | [Routing report](global_routing.json) |
| Actual IHP post-CTS mapped netlist, zero delay | PASS, two pin-only tests, 6020 readbacks and four outputs | [Mapped report](mapped.json), [JUnit XML](cocotb_mapped.xml), [log](cocotb_mapped.log) |
| Detailed routing | See current status | [Machine-readable status](verification.json) |
| Complete GDS DRC, LVS, extracted STA and TinyTapeout precheck | Not yet accepted by a complete corrected flow | [Machine-readable status](verification.json) |

At the 50 MHz design target, 3080 cycles correspond to 61.60 microseconds. This is inference time after the model and complete input vector have been validated. It excludes host transfer and robot actuation. The clock remains a target until complete extracted timing acceptance.

The nine host fault cases are unloaded START, early COMMIT, missing staged byte, out-of-order address, invalid address high bits, invalid input index, invalid output index, invalid diagnostic page, and undefined register. These are TinyTapeout host-interface tests. They must not be confused with the separate FPGA safety-gate fault suite.

The mapped test uses the actual IHP post-CTS netlist from [physical run 38687725982](https://github.com/sundaysiagian/peruri-iseedesign/actions/runs/38687725982), artifact `11952133725`, source commit `7ef7ab85b21b7e140da85bdc0f045a2bbca25faf`. The four current functional RTL token streams match that source. Attribution comments have the corrected team spelling. [The mapped report](mapped.json) identifies the exact netlist, cell models, pin tests, fixed-point reference and parameter images with SHA-256 hashes. It checks one complete inference vector at gate level. The separate RTL test checks 100 vectors. This is zero-delay functional simulation without an SDF timing claim.

## What was repaired

The previous physical run restricted signals to Metal2 through Metal4. Metal3 was therefore the only horizontal signal layer. The actual placed design could not route, even when a diagnostic replay used 100 congestion iterations and no reserved track capacity.

The corrected configuration allows signal routes on Metal1 through Metal4. Clock routes remain on Metal2 through Metal4. Standard-cell obstructions remain active and 10 percent track capacity is reserved. The replay of the actual post-CTS netlist produces zero global-routing overflow. See [the baseline failure](baseline_congestion.log) and [the corrected run](global_routing.log).

This change addresses routing capacity. It does not remove model parameters, bypass the neural calculation, replace the design with the older safety-gate demo, accept congestion, or disable physical checks. `GRT_ALLOW_CONGESTION` remains zero and routing DRC, KLayout DRC, LVS, and illegal-overlap errors remain enabled.

The local routing replay starts from the archived placement at 45 percent target density. The current submission configuration requests 40 percent. The archived netlist and current neural datapath compute the same fixed model. Placement, routing, extracted timing and complete physical acceptance for the current configuration still require a completed corrected flow. The first detailed-route attempt was interrupted when WSL restarted. Its saved zero-overflow checkpoint is being resumed. An intermediate routing violation count is progress information and is never reported as a clean layout.

Configuration meanings are documented in the [LibreLane routing variables](https://librelane.readthedocs.io/en/latest/reference/step_config_vars.html). The project follows the [TinyTapeout CMOS5L template](https://github.com/TinyTapeout/ttihp-verilog-template/tree/cmos5l).

## Reproduce RTL verification

Run from the repository root with Python, Icarus and the requirements installed. On this machine the working runs use Linux under WSL. The native Windows Icarus process crashes in the current execution environment, including small unrelated designs.

```bash
python -m pip install -r requirements.txt -r requirements-asic.txt -r requirements-layout.txt
python scripts/generate_neural_logic_rom.py --check
python scripts/synth_neural_logic.py
python scripts/verify_neural_logic.py --generic
python verification/run.py tt_logic
python scripts/test_neural_logic_layout.py
```

The first script reconciles the unified parameter image with all six layer exports. The Verilog testbench compares RTL inference with an independent Python reference and also checks overflow and command ownership. The cocotb tests drive and observe only the submission pins.

## Reproduce the actual mapped netlist test

Use a netlist from the same submission and the unmodified IHP functional cell models. Icarus 13 is recommended for this mapped test. This is functional zero-delay verification, with no SDF timing claim.

```bash
python scripts/verify_tinytapeout_pin_netlist.py \
  --netlist /path/to/tt_um_wlmoi_igor_neural_logic.nl.v \
  --stdcell-model /path/to/sg13cmos5l_stdcell.v \
  --udp-model /path/to/sg13cmos5l_udp.v
```

The script writes `evidence/tinytapeout/current/mapped.json` and `evidence/cocotb_tt_mapped.xml`. Future runs hash their simulation inputs before compilation and reject inputs that change during simulation. The archived run in this folder has its input hashes recorded after its successful execution, as declared in its report.

## Reproduce routing diagnostics

Use the post-CTS DEF and PDK files from the same physical-flow artifact. Input hashes are recorded in [the routing report](global_routing.json). The replay script is intended for Linux or WSL with OpenROAD installed. By default it also runs detailed routing and rejects nonzero detailed-route DRC metrics.

```bash
python scripts/replay_tinytapeout_routing.py \
  --def /path/to/tt_um_wlmoi_igor_neural_logic.def \
  --tech-lef /path/to/sg13cmos5l_tech.lef \
  --cell-lef /path/to/sg13cmos5l_stdcell.lef \
  --liberty /path/to/sg13cmos5l_stdcell_slow_1p08V_125C.lib \
  --output .runtime/current-routing
```

Use `--global-only` to isolate global routing, or `--signal-min Metal2` to reproduce the restricted-layer comparison. Neither mode counts as full physical acceptance.

The repository's TinyTapeout workflow performs the full GDS flow, precheck, gate-level test, strict metric validation and published-layout identity check after the changes are pushed. Only a successful complete corrected run can supply that acceptance. These local tests do not demonstrate fabricated silicon or a robot running from this ASIC.
