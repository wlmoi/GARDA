# GARDA UART Explorer

Real-time UART explorer for the GARDA FPGA serial link. Run `START_UART_EXPLORER.bat` (or `python explorer.py`),
open http://127.0.0.1:8780. Needs Python 3.10+; `pip install pyserial` for LIVE mode. No other dependencies.

Architecture: `serial / SimDevice -> protocol.py decoder -> Hub (ring buffer 20000 events, bounded per-client queues) -> /events (SSE) -> browser`.
Serial I/O is synchronous under one lock and never waits for the UI; slow browsers lose display events only. Exports (`/api/export?fmt=json|csv|hex`) come from the ring.

## Modes (always shown in the header badge and banner)
| Mode | Meaning |
|---|---|
| LIVE | pyserial port. Badge says "FPGA responding" only after a CRC-valid response arrived. |
| SIMULATION | `SimDevice` = software model of the protocol contract. Never claims an FPGA. Events carry `source=SIM`. |
| RECORDED TRACE | replay of `traces/*.json`; original provenance is shown. The bundled trace is **SIMULATION provenance**, not hardware. |

## Protocol (verified from `dashboard/dist/source/rtl/garda_uart_protocol.v`, `_rx.v`, `_tx.v`, `garda_uart_top.v`)
- 8N1, LSB first, `CLKS_PER_BIT=434` at 50 MHz = 115207 baud (nominal 115200), 8.68 us/bit.
- Request (8 B): `A5 | op | payload[7:0] payload[15:8] payload[23:16] payload[31:24] | CRC8 | 5A`
- Response (8 B): `5A | op echo | data LE (4 B) | CRC8 | A5`  (RTL shifts `{A5,crc,data,op,5A}` out LSB byte first)
- CRC8: poly 0x07, init 0, no reflection, no final XOR, over bytes 0..5 (response CRC covers `5A,op,data`).
- No sequence number: one outstanding request. Request/response association = opcode echo + request id (host side).
- Bad frame, CRC, bad payload (`payload_ok`), or timeout latches sticky protocol/invalid fault; only physical KEY0 clears it. The Explorer therefore refuses to transmit payloads the RTL would reject (unless forced via API).
- Opcodes: see `protocol.py::OPCODES`. Status word: enable b0, busy b1, done b2, protocol_fault b3, invalid b4, fault_code [15:8], candidate [24:16]. Gate fault codes in `FAULT_CODES`.

## Capabilities of the deployed design (what the UI enables/disables)
| Requested | Status |
|---|---|
| PING / status (op 7), read result (op 12), read safety (7, 14, 16), run inference (10-13) | supported |
| 74-feature input | **not supported**: deployed neural core has 24 inputs, 4 outputs |
| Trigger E-stop by UART | **not supported**: E-stop is the physical KEY1 input. Verified by reading status `fault_code==2` (event `ESTOP_CONFIRMED`) |
| Reset safety state by UART | **not supported**: KEY0 only |
| "Proposed AI motion" | not exposed by the protocol; shown as such. Adding telemetry would need an RTL change (not made) |

## Programming the FPGA
`..\Program-FPGA.ps1` (PowerShell): finds Quartus, detects cable + FPGA position in the JTAG chain, checks the .sof matches the device,
clears stale `jtagd/jtagserver/quartus_pgm`, programs with retries and a last-resort auto-select. JTAG programming works whatever the FPGA is doing;
it cannot fix an unpowered board, missing USB driver, or a .sof for another device. Options: `-Sof`, `-Cable`, `-DryRun` (detect only), `-Force`, `-Explorer`.
The bundled `igor.sof` is for Cyclone V 5CSEBA6U23I7 (**DE10-Nano**); a DE10-Lite (MAX 10) needs its own .sof (the script refuses a mismatch).

## Board I/O panel (switches, keys, LEDs)
Mapping verified in the real RTL (`tests/rtl_cosim/run_io.py`): KEY1 held -> fault 2 (E-stop); SW3 -> fault 3 (protective stop); SW2 -> fault 4 (ready inhibited);
KEY0 = reset (clears sticky fault); SW0/SW1 unused by `garda_uart_top`. LEDs `{fault[3:0], done, busy, rst_n, enable}` are derived from the op 7 status.
SIMULATION: switches/keys are clickable and drive the software model. LIVE: the host cannot press board inputs over UART, so they are read-back indicators
(inferred from fault_code; enable "auto-read" and flip the real switch). Driving them from the PC would need an RTL change (not made).

## Events
PORT_OPENED, TX_STARTED, TX_COMPLETED, RX_DATA_RECEIVED, FRAME_DECODED, CRC_VALID/CRC_ERROR, FPGA_RESPONSE_RECEIVED, COMMAND_TIMEOUT, ESTOP_CONFIRMED are directly observed host-side.
COMMAND_ACCEPTED/REJECTED is **inferred** from response status bits (`verified:false`). Blocks inside the FPGA diagram are explanatory, not telemetry.
Host RTT (perf_counter, includes USB-UART latency) is separate from RTL cycle latency (op 13).

## Waveform
DECODED RECONSTRUCTION only (`web/wave.js`). The CAPTURED tab is disabled: no logic-analyzer input exists.

## Judge demo (5 steps, verdicts computed from real responses)
Status, ROM[0] vs `bram_unified_weights.mem`, NN vector 0 vs `test_outputs.mem`, safety readout, operator-assisted E-stop (press KEY1 within 15 s; if not seen -> NOT_VERIFIED).
Run with actuators disconnected. "Pause visualization" pauses only the UI; "Stop safely" halts between frames.

## Tests
`python -I -m unittest discover -s tests`, `python tests/rtl_cosim/run_cosim.py` and `run_io.py` (real RTL in Icarus Verilog), `node tests/test_wave.js`, `node tests/browser_check.cjs <edge> http://127.0.0.1:8780/ <prefix> --sim-demo`. See `TEST_REPORT.md`.
