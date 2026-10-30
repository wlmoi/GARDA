# Active Tiny Tapeout full neural inference target

`info.yaml` selects `tt_um_wlmoi_igor_neural_logic` on 8x4 CMOS5L tiles. Full 24-64-64-4 Q8.8 inference remains on chip. All 6,020 weights/biases are immutable standard-cell logic; input/hidden activations use flip-flops. There are no SRAM macros in the active target.

The host verifies the fixed model, commits it, loads 24 inputs, and starts the two-lane MAC pipeline. A mismatched model, incomplete verification/inputs, overflow, and conflicting host commands are rejected. The measured schedule is 3,080 cycles (61.6 us at the 50 MHz target, pending routed timing qualification). The model cannot be reprogrammed after fabrication.

[Implementation and tests](../asic/neural_logic/README.md), [register datasheet](info.md), and [active configuration](../src/config.json) document the fallback. It was selected because SRAM integration kept delaying completion: the last SRAM build passed GDS and gate-level inference but failed supply-pin precheck. [Archived SRAM implementation](../asic/neural_sram/README.md).

Acceptance requires the correct full-inference top and no reachable SRAM, zero routing/KLayout DRC/LVS/power-grid/illegal overlap errors, and zero setup/hold/slew/cap violations at the configured corners. Precheck and actual gate-level tests must pass before viewer deployment; the published OASIS hash must match that run. A passing historical safety-gate layout is insufficient.

```sh
python scripts/generate_neural_logic_rom.py --check
python scripts/synth_neural_logic.py
python scripts/verify_neural_logic.py --generic
python verification/run.py tt_logic
python scripts/test_neural_logic_layout.py
```

The [legacy safety gate](info_gate_legacy.md) and [one-SRAM example](../asic/sram_example/README.md) remain separate regressions, not the active chip.
