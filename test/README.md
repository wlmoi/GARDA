# Active neural logic submission tests

`tb.v` instantiates `tt_um_wlmoi_garda_neural_logic`. `test.py` exercises the submission pins: model verification using the 6,020 supplied words, an inference against the independent Python model, and command and reset behavior. The model is fixed in logic; the current submission does not instantiate SRAM.

Run `make` for RTL simulation. Gate simulation (`make GATES=yes`) requires the matching IHP PDK models and a netlist generated from this revision. The existing IHP configuration is not a SKY130 physical-flow result.

The safety-gate tests are in `verification/test_tt_gate.py` and `verification/tb_gate_wrapper.v`.
