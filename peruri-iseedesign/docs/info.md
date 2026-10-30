# How it works

The active chip is `tt_um_wlmoi_igor_neural_logic`: complete dual-MAC Q8.8 inference with topology 24 -> 64 -> 64 -> 4. All 5,888 weights and 132 biases are immutable model constants implemented in ordinary standard-cell logic. The 152 input/hidden activation words use flip-flops. There are **no physical SRAM macros**. Hidden layers use ReLU and outputs are clipped to [-256,256].

This fallback preserves full on-chip inference. SRAM integration was delaying completion: the last SRAM run passed GDS, LVS/DRC, routed timing and gate-level inference, but failed Tiny Tapeout supply-pin placement precheck. Its source and evidence remain archived in [the SRAM implementation](../asic/neural_sram/README.md).

The host protocol is retained as **model verification**, not writable model storage. BEGIN invalidates previous inputs/results. Each VALIDATE_WORD compares staged bytes against the built-in model at the sequential address. A different coefficient sets a fault; it cannot modify the chip's model. Verify all 6,020 words and COMMIT before loading inputs. Changing the model requires regenerating the logic and fabricating a new chip.

Registered even/odd reads feed two MAC lanes. Inference still takes 3,080 cycles: 61.6 us at the 50 MHz target, subject to physical timing qualification. The fallback removes development delays from SRAM integration; these measurements do not show a reduction in the inference cycle count.

## Register interface

`ui_in[0]` write-enable; `ui_in[4:1]` write register; `ui_in[7:5]` read selector. Write data is `uio_in`; read data is `uo_out`. Deassert write-enable when reading.

| Write register | Meaning |
|---:|---|
| 0 | Host word address bits 7:0 |
| 1 | Host word address bits 12:8; upper bits must be zero |
| 2, 3 | Stage low and high data bytes |
| 4 | 1=BEGIN verification, 2=VALIDATE_WORD, 3=COMMIT |
| 5 | Input index 0-23 |
| 6 | LOAD_INPUT from staged data |
| 7 | START inference |
| 8 | Output index 0-3 |
| 9 | Diagnostic page: 0=identity, 1-4=latency counter bytes |

| Read selector | Meaning |
|---:|---|
| 0 | bit 0 reset released, 1 ready, 2 busy, 3 done, 4 host fault, 5 neural fault, 6 loading |
| 1, 2 | Built-in model low/high data bytes, zero while busy |
| 3, 4 | Selected neural output low/high bytes, zero unless valid |
| 5, 6 | Verified word count low/high bytes |
| 7 | Identity 0xA6 on diagnostic page 0, latency bytes on pages 1-4 |

# How to test

1. Reset and select diagnostic page 0; read identity 0xA6.
2. BEGIN; for each of 6,020 words write register 2, then 3, then VALIDATE_WORD. Both bytes must be restaged for each word. Address auto-increments.
3. Set host addresses with registers 0/1 and read back every word through selectors 1/2. Stop on any mismatch.
4. COMMIT and check ready without host/neural faults.
5. For each of 24 inputs set index, stage both bytes, and LOAD_INPUT. Allow another rising edge before changing the input registers.
6. START and poll done/fault. Select each of four outputs and read selectors 3/4. Read diagnostic pages 1-4 to check 3,080 cycles.

`make -C test` runs a pin-only model verification/readback/inference test. The same harness tests the generated physical netlist with `GATES=yes`. Run `python verification/run.py tt_logic` for the local runner. The [host helper](../asic/neural_sram/host.py) accepts board-specific clocked transport callbacks.

# External hardware

A Tiny Tapeout-compatible digital host must drive the synchronous register interface. The chip does not implement the older FPGA UART protocol, a motor driver, or the FPGA DWA pipeline. Connect I/O only at the selected board's supported voltage levels. See the [active implementation](../asic/neural_logic/README.md) for model generation, layout and timing acceptance.
