# GARDA UART protocol (DE10-Lite build)

The framing, CRC and all legacy opcodes are the existing GARDA protocol from
`rtl/garda_core/garda_uart_protocol.v` / `garda_uart_top.v`, unchanged.
Opcodes 0x20–0x29 are DE10-Lite additions in `rtl/de10_lite/garda_lite_uart_top.v`.

## Two hosts

Port A (JP1 pins 1/2) and port B (JP1 pins 3/4) share one protocol engine through a
frame-level arbiter. A port is granted the link on a start bit that follows at least
12 idle bit times. It keeps the link until both its RX line and the FPGA TX line
have been idle for 2 byte times. Frames from the other port are not forwarded meanwhile
(they are counted as collisions), so the core never sees interleaved bytes.

## Frames

```
request  host → FPGA : A5 | op | d0 d1 d2 d3 | CRC | 5A      (payload little endian)
response FPGA → host : 5A | op | r0 r1 r2 r3 | CRC | A5
```

* CRC-8, polynomial 0x07, init 0x00, MSB first, no reflection, no final XOR.
  The request CRC covers `A5 op d0..d3`; the response CRC covers `5A op r0..r3`.
  Example: `A5 20 00 00 00 00 3E 5A` (IDENT).
* One request, then one response, about 4 clocks after the request's last byte. A byte that
  arrives while the FPGA is still answering latches `protocol_fault`.
* **Sticky faults (legacy behaviour, kept):** a framing error, wrong header/tail, CRC
  mismatch or a >100 ms gap inside a frame latches `protocol_fault`. After that the
  FPGA answers **nothing** until reset. A CRC-valid frame whose payload breaks its
  opcode contract latches `invalid_command`. It is still answered, and the flag is
  visible in the status word. Both remove motor permission (fault 4).
* Recovery: press KEY0, or send `SAFE_RESET`. That frame is recognised by an independent
  receiver (`garda_safe_reset_sniffer.v`) even while `protocol_fault` is latched.
  It is ignored while KEY1 (physical E-stop) is held.

## Status word (opcode 7 and the default response)

| bits | meaning |
|---|---|
| 0 | motor_enable (safety gate output) |
| 1 | planner busy · 2 planner done |
| 3 | protocol_fault · 4 invalid_command |
| 15:8 | fault code (table below) |
| 24:16 | selected candidate index |

## Legacy opcodes (unchanged)

| op | name | payload contract | response |
|---|---|---|---|
| 1 | MAP_BEGIN | frame sequence (must increase) | status |
| 2 | MAP_WRITE | `[14:0]` address, `[23:16]` cost, `[31:24]=0`, `[15]=0` | status |
| 3 | MAP_COMMIT | 0 (requires all 16384 cells) | status |
| 4 | CFG_WRITE | version 1 limits word (e.g. 0x00143D0F) | status |
| 5 | CFG_LOCK | 0 | status |
| 6 | RUN | 0 | status |
| 7 | STATUS | 0 | status |
| 8 | ROM_READ | address < 6020 | weight word |
| 9 | LATENCY | 0 | planner cycles |
| 10 | NN_LOAD | `[4:0]` index < 24, `[23:8]` Q8.8 value | status |
| 11 | NN_START | 0 | status |
| 12 | NN_READ | `[1:0]` output index | `{fault,busy,done,value[15:0]}` |
| 13 | NN_CYCLES | 0 | inference cycles (18192) |
| 14 | COMMAND | 0 | `{omega[11:5], v[4:0]}` |
| 15 | EVENTS | 0 | fault event counter |
| 16 | LAST_FAULT | 0 | last logged fault |

Map freshness and the command lease are both 1 000 000 cycles (20 ms). A planner
result permits motion for at most 20 ms after the run. That is the original GARDA
safety design, unchanged here.

## DE10-Lite extension opcodes

| op | name | payload | effect / response |
|---|---|---|---|
| 0x20 | IDENT | 0 | `0x47444C02` ("GDL", interface v2; v1 builds answer `0x47444C01` and lack 0x2A–0x2C) |
| 0x21 | HOST_ESTOP | 0 | latch host E-stop (ORed with KEY1 into the gate's estop input). The exact frame `A5 21 00 00 00 00 CRC 5A` is also detected **out of band** on each RX pin, so it takes effect even when the other host owns the link |
| 0x22 | SAFE_RESET | `0x52534554` ("RSET") | reset ~12 byte-times after the frame (sniffer) |
| 0x23 | WATCHDOG | `[15:0]` timeout ms, 0 = off | if armed and no accepted command for the timeout: latch protective stop (fault 3) |
| 0x24 | EXT_STATUS | 0 | host_estop, key_estop, watchdog armed/trip, E-stop-test state, capture valid, SW2, SW3, enable, done, busy, faults, fault code, last fault |
| 0x25 | ESTOP_TEST | delay cycles 1…2²⁴−1 | after the next planner result, wait `delay` cycles, then assert host E-stop |
| 0x26 | ESTOP_CAPTURE | 0 | `[0]` valid `[2]` motor_enable just before the stop `[3]` host source `[4]` KEY1 source `[12:8]` v `[19:13]` ω `[31:24]` clock edges until motor_enable was seen low |
| 0x27 | COUNTERS | 0 | `{CRC-valid frames[31:16], accepted commands[15:0]}` |
| 0x28 | BUILD_ID | 0 | build stamp written by `scripts/build.py` (UNIX time) |
| 0x29 | LINK_INFO | 0 | `{CLKS_PER_BIT[31:16], cycles per ms[15:0]}` |
| 0x2A | PORT_STATS | 0 | `{port B frames granted[31:16], port A frames granted[15:0]}` |
| 0x2B | PORT_INFO | 0 | `{collisions[31:16], 0, requesting port[0]}` (0 = A laptop, 1 = B Jetson) |
| 0x2C | BOARD_IO | 0 | `[9:0]` SW9..0 `[11:10]` KEY1..0 (1 = released) `[21:12]` LEDR9..0 `[22]` PLL locked |

All new stop sources can only **remove** motor permission. None of them can grant it.

## Fault codes (safety gate priority order)

| code | meaning |
|---|---|
| 0 | all checks passed, command passed to motors |
| 1 | reset active |
| 2 | E-stop (KEY1 or host) |
| 3 | protective stop (SW3 or watchdog) |
| 4 | not ready (SW2, protocol fault or invalid command) |
| 5 | map invalid, incomplete, out of sequence or stale |
| 6 | configuration not valid or not locked |
| 7 | rollout arithmetic fault |
| 8 | deadline or command lease expired |
| 9 | result not valid yet |
| 10 | absolute v/ω limit exceeded |
| 11 | v/ω change limit exceeded |

