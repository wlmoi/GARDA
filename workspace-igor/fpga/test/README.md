# Active neural SRAM submission tests

`tb.v` instantiates `tt_um_wlmoi_igor_neural_sram`. `test.py` uses submission pins only and applies to both RTL and the generated gate netlist. It verifies rejected unloaded START, full 6,020-word upload/readback, one inference against the independent Python model, the 3,080-cycle latency, I/O direction, and result invalidation on BEGIN.

The Makefile includes the official IHP core and 4096x16 and 256x16 SRAM models with SIM/FUNCTIONAL. Gate mode additionally includes the CMOS5L cells and their UDP definitions. Run `make` or `make GATES=yes` with the matching PDK and exported gate netlist.

The previous safety-gate tests are preserved in `verification/test_tt_gate.py` and `verification/tb_gate_wrapper.v`. Use `python verification/run.py tt` and `tt_generic` for those legacy regressions.
