# One SRAM synthesis example

This auxiliary example stores the 256 W3 parameters in one explicit IHP
256x16 SRAM and exposes clocked byte staging, word writes and readback on
Tiny Tapeout pins. It exercises the memory interface; the active Igor chip
and complete inference datapath remain selected by the root `info.yaml`.

Run `python scripts/verify_sram_example.py` from the repository root. It
checks that synthesis retains exactly one SRAM, then runs the same pin-only
tests on RTL and its generic netlist using the pinned, unmodified IHP model.
Tests read back all W3 words, all-address bit patterns, enable, write-output
hold and reset retention. These checks do not qualify a routed physical chip.

All UIO pins are inputs carrying the byte value. `ui[0]` loads an 8-bit
address; `ui[1]` and `ui[2]` stage the low and high data bytes; `ui[3]` writes
the staged word. Assert each command over a separate rising edge. With
commands clear, another rising edge refreshes readback. `ui[4]` selects the
high read byte, while `ui[5]` selects interface identity 0xA7. Reset clears
the staging registers and disables writes, retaining the SRAM contents.
