# Test report (2026-11-11)

| Item | Result |
|---|---|
| Serial port discovery | Ran: pyserial 3.5 enumerates 0 ports on this PC (no board attached) |
| Protocol vs RTL | PASS: real `garda_uart_top` RTL co-simulated in Icarus Verilog 12 (`tests/rtl_cosim/run_cosim.py`): 38 requests incl. status, ROM[0]/ROM[6019] vs `.mem`, 24 NN inputs + start + poll + 4 outputs vs reference vector 0 (-98, 74, -96, -256), RTL latency 18192 cycles, all responses CRC-valid with opcode echo; a bad-CRC frame gets no reply and the next frame is also ignored (sticky fault) |
| CRC8 | PASS: standard check value "123456789" -> 0xF4; known frame `A5 07 00000000 73 5A` |
| Serialize/decode, malformed frames (bad SOF/EOF/CRC/length/opcode echo) | PASS (22 Python unit tests) |
| Timeout, sticky fault, disconnected device, missing LIVE port | PASS (SimDevice / real missing-port error) |
| E-stop behaviour | PASS in RTL co-sim (`tests/rtl_cosim/run_io.py`: KEY1 -> fault 2, SW3 -> 3, SW2 -> 4, SW3+KEY1 priority -> 2, SW0/SW1 no effect; always enable 0, v=omega=0). Physical KEY1 on hardware NOT TESTED |
| Exports match traffic (JSON/CSV/HEX) | PASS |
| Ring buffer bound, slow subscriber not blocking | PASS |
| Waveform bit order (LSB first, start/stop, parity) | PASS (node test) |
| Animation tied to events | Code path: animations are created only in `handle()` of SSE events; browser run showed 74-120 packets and 5 demo steps from events. Not visually frame-verified |
| Dashboard desktop 1500 px / mobile 400 px (Edge headless) | PASS: no console errors, no horizontal scroll |
| "Production build" | N/A: no build step (static files, stdlib server) |
| **LIVE FPGA end-to-end** | **NOT TESTED** (no DE10 board / serial port available) |
| Recorded hardware trace | none exists; bundled trace is SIMULATION |

Co-sim caveat: it simulates RTL behaviour with an ideal testbench UART; it does not test the FPGA pins, USB-UART bridge, board or the 20 ms lease timing. Icarus came from MSYS2 (`pacman -S mingw-w64-ucrt-x86_64-iverilog`); Questa (Quartus install) has no license here.

## Programming script (`Program-FPGA.ps1`)
- PowerShell parse: 0 errors. No hardware: reports "no JTAG cable detected", resets stale jtagserver between attempts, exits 10. Missing SOF -> exit 3.
- Chain parser tested on sample `jtagconfig` output: DE10-Nano chain -> FPGA at position 2 (`@2`); MAX 10 chain correctly does not match the Cyclone V SOF.
- **Actual programming: NOT TESTED** (no board/JTAG cable). Browser I/O panel: SW3/KEY1 clicks verified in SIMULATION (Edge headless).
