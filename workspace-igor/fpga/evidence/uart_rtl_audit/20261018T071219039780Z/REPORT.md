# UART RTL audit ? 18 October 2026

All five suites passed using production Parallel8 RTL at 50 MHz.
Accepted source and packaged SOF hashes match the recorded build.

| Suite | Result |
|---|---|
| Neural core | 236 vectors, 8,364 activation cases, 54,399 assertions |
| UART protocol and fault recovery | 184 transactions, 268 assertions |
| Production board wrapper | 18 checkpoints |
| Independent nominal 921600-baud host | 18 checkpoints; asynchronous back-to-back bytes |
| Real-clock stress | 50/50 valid frames, exactly 550 bytes, 150 golden actions; nominal and +/-1% host bit durations |

Checks include TX high during reset, quiet startup, start/stop bits, headers,
CRCs, no extra bytes between requests and silence over 21 ms after the final
result, including stale timeout. Directed tests cover CRC/framing errors,
parser recovery, watchdogs, reset and E-stop.

Initial stress used an intentionally out-of-domain core vector. RTL correctly
rejected it with error 8; the initial log is retained. The corrected harness
selects valid normalized observations and passes.

No RTL defect reproducing the Jetson garbage stream was found. No production
RTL, clock, bitstream or FPGA configuration was changed. Existing accepted
timing reports have positive setup/hold slack at 50 MHz; Quartus implementation
was not rerun. Simulation does not establish physical signal integrity, Jetson
pin routing/port ownership, actual clock frequency, or current FPGA configuration.

Reproduce: `python tools/check_uart_rtl.py` from workspace root.
Details: `receipt.json` and each suite's `simulation.log`.
