# IHP SRAM simulation models

These two Apache-2.0 files are copied unchanged from IHP-Open-PDK revision
`2bbec755dc67ca3db0261c3d6163e15735d66710`, matching the Tiny Tapeout CMOS5L installer.
Their original copyright and license notices are retained.

Source directory:
https://github.com/IHP-GmbH/IHP-Open-PDK/tree/2bbec755dc67ca3db0261c3d6163e15735d66710/ihp-sg13g2/libs.ref/sg13g2_sram/verilog

The pinned CMOS5L `sg13cmos5l_sram` directory is a symlink to this library.
Both RTL and gate-level tests compile these models with `SIM` and `FUNCTIONAL`.
Physical views are read directly from the installed PDK.
