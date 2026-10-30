# Physical Parallel8 JTAG console verification — 19 October 2026

**Latest console correction:** see [the empty-Enter fix](EMPTY_ENTER_FIX.md) and
[ten passing physical checks](20261019T123946Z/physical_commands.json).
The screenshot and five-command logs below describe the initial image, not the
subsequent corrected build. Both use the same Parallel8 neural core and weights.

Quartus Programmer GUI configured `igor_parallel8_jtag.sof` on
`DE-SoC [USB-1]`, HPS bypass at device 1, FPGA at device 2. GUI completion:
**100**, `Successfully performed operation(s)`, **19:26:57 WIB**.
`quartus_programmer_success.jpg` is the original unmodified computer-use
screenshot; `.uia.txt` records the GUI accessibility text including progress 100.

`physical_terminal.log` records the real Quartus terminal connection to device 2,
JTAG UART instance 0 and the first automatic inference. It received:

```text
RX count=0xB FPGA bytes: 5A A5 02 06 D2 FF 3C 00 22 00 61
cycles=0x00001B04 accepted=0x00000001 rejected=0x00000000 error=0x00 CHECK=PASS
```

`physical_commands.log` / `.json` record five additional physical transactions
using the installed Quartus `jtag_atlantic.dll`, with no simulator substituted:

| Transaction | Observed result |
| --- | --- |
| Three `r` requests | Exact 11-byte response, 6,916 cycles, PASS each |
| `!` bad-CRC request | No response bytes, error 06, rejection-test PASS |
| Full 153-byte request pasted as hex | Exact expected response, DATA label |

The output decodes to Q8.8 raw residuals `[-46, 60, 34]`. Latency is 138.32 µs
for the core at 50 MHz; this excludes JTAG/serial/host overhead. Error `0B` in
later logs means the earlier result expired while waiting for the next command;
the latest fault stays recorded even after a successful transaction. It does
not mean the fresh, CRC-valid response failed. The console has no motor output.

The bounded CLI capture ends with a console-attribute restoration diagnostic
because stdout was redirected and the terminal was stopped by timeout. The
connection and inference preceding it succeeded; physical command tests use the
DLL directly and complete without that terminal redirection issue.

Build evidence: `../../experiments/parallel8_jtag/output_files/` contains the
latest original Quartus reports. Latest full compile: **0 errors, 53 warnings**,
4,013 ALMs, 7,017 registers, 66 M10K, eight DSP, zero PLL, 12 pins. Minimum
summary hold slack: **+0.119 ns**, minimum setup slack **+7.041 ns**. Warnings include vendor debug
SDC filters and retained core ROM implementation messages; this is a working
FPGA demonstration, not ASIC fabrication sign-off or exhaustive verification.

The dedicated SOF SHA256 and unchanged core SHA256 are recorded in
`../../bitstreams/igor_parallel8_jtag.json`. Simulation evidence is in the project
directory: byte-order/FIFO-full retry and actual-core inference, CRC rejection,
custom hex request, E-stop inhibition. E-stop was simulated, not physically
pressed during these five runtime command tests.
