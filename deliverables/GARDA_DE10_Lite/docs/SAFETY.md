# GARDA DE10-Lite: safety of the data and control flow

GARDA is a safety gate for physical AI: neural and planning results are only *proposals*.
Nothing reaches a motor unless the hardware safety gate (`garda_safety_security_gate.v`,
unmodified) passes every check in the same clock cycle. This page lists every path from a
host to the motor command and how each path is guarded. It also lists the evidence for each.

```
 Laptop  ──JP1 1/2──┐                       ┌─ out-of-band E-stop detector (port A) ─┐
                    ├─► two-host arbiter ─► UART protocol (framing, CRC-8, timeout) ─► command contract ─► GARDA core
 Jetson  ──JP1 3/4──┘                       └─ out-of-band E-stop detector (port B) ─┤                      (planner, neural)
                                                                                     ▼                            │
 KEY1 (physical E-stop) ───────────────────────────────────────────────────► E-STOP  ──►  SAFETY GATE  ◄──────────┘
 SW3 / link watchdog ──────────────────────────────────────────────────► PROTECTIVE STOP ─►  (11 checks)  ─► motor_enable, v, ω
 SW2 / protocol fault / invalid command ───────────────────────────────────► NOT READY ─►
```

## Rules the hardware enforces

| # | Rule | Where | Evidence |
|---|---|---|---|
| 1 | Motor permission needs: no reset, no E-stop, no protective stop, ready, valid fresh map (≤ 20 ms), locked config, no arithmetic fault, no deadline/lease expiry (20 ms), valid result for the current map, absolute v/ω limits and v/ω change limits. Otherwise v = ω = 0 | `garda_safety_security_gate.v` (unmodified) | lockstep equivalence (`sim/tb_lockstep.v`), board test |
| 2 | Every frame needs header/tail, CRC-8 and a complete frame within 100 ms. Any error latches `protocol_fault`, which removes permission until reset | `garda_uart_protocol.v` (unmodified) | `tb_legacy_uart` (24 cases) on both tops |
| 3 | Every opcode has a strict payload contract. A violation latches `invalid_command` and removes permission | `garda_lite_uart_top.v` (legacy contracts copied verbatim) | `tb_legacy_uart`, board test |
| 4 | KEY1 E-stop acts combinationally on the gate. It is not synchronised and needs no clock cycle. It latches the planner FAULT state until reset | `garda_top.v` (unmodified) | board test (KEY1 capture) |
| 5 | Host E-stop latches until reset and ORs into the same E-stop input as KEY1 | `garda_lite_uart_top.v` | board test: capture shows motor_enable dropped in the same clock cycle (0-edge latency) |
| 6 | **A host E-stop is never blocked by the other host.** Each raw RX pin has its own detector for the CRC-valid E-stop frame, before the arbiter | `garda_estop_sniffer.v` | board test "out-of-band detector latched the E-stop" during a forced collision |
| 7 | Link loss: when armed, silence longer than the timeout latches a protective stop | `garda_lite_uart_top.v` watchdog | board test (fault 3 after silence) |
| 8 | Two hosts never interleave bytes: a port is granted only after ≥ 12 idle bit times and keeps the link until its response is complete | `garda_uart_port_arbiter.v` | board test: port isolation, collision, retry |
| 9 | Reset can only return to the safe power-on state. UART safe reset needs a magic payload and is refused while KEY1 is held | `garda_safe_reset_sniffer.v` | board test |
| 10 | Every addition can only **remove** permission. No new path can set `motor_enable` | design review of `rtl/de10_lite/*` | lockstep: identical behaviour on legacy traffic |
| 11 | Real-time constants keep their meaning at the 45 MHz core clock (20 ms lease/freshness, 100 ms UART gap) | `garda_de10_lite_top.v` parameters | `LINK_INFO` read from the FPGA reports 45 MHz |
| 12 | Observers (VGA, HEX, LEDs, BOARD_IO) are registered taps. They cannot extend core timing paths or feed back into the core | board top | timing report: all corners met |

## Host-side rules

* A serial port that merely opens is never reported as a working FPGA. Only a CRC-valid IDENT
  with the GARDA signature switches the UI to *FPGA RESPONDING / LIVE HARDWARE*.
* Automatic retries are limited to read-only commands and the idempotent E-stop. State-changing
  commands (map, config, run) are never re-sent, because a duplicate could change behaviour.
* Commands an older FPGA image does not know are not sent (interface-version check),
  so the Control Center cannot accidentally latch `invalid_command`.
* JTAG programming only accepts one 10M50DA (IDCODE 0x031050DD), a `.sof` built for
  10M50DAF484C7G whose SHA-256 matches the build manifest, and an explicit operator click.
  Flash is never written.
* The local bridge listens on 127.0.0.1 only. It checks Host and Origin, needs a per-launch
  token, and offers a fixed command list. There is no shell and no free file path.
* SOFTWARE SIMULATION and RECORDED HARDWARE TRACE views are always labelled. A recorded trace
  is only written when the FPGA actually answered.

## Remaining limits (honest list)

* The neural core is a separate datapath. Its outputs are read over UART and do not drive the
  planner or the motors in this build.
* The watchdog is fed by *any* accepted command from either host. It detects silence of both
  hosts, not of one specific host.
* While the laptop uploads a map, normal Jetson commands only get the link between laptop frames.
  Its E-stop is not affected (rule 6).
* No motor driver is connected. `motor_enable`, v and ω are status outputs (LEDs, VGA, UART).
* Hardware tests so far: JTAG programming and the laptop UART link (IDENT, LINK_INFO,
  BUILD_ID, STATUS, EXT_STATUS read live with CRC OK). The Jetson port and the full demo
  sequence on hardware are pending until they are run; see `reports/VERIFICATION_REPORT.md`.
