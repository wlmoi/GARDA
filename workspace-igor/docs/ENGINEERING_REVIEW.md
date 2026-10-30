# Engineering review and interview notes

This project is a programmable UART, SPI, and I2C engine with four execution
contexts and one 512-byte IHP SRAM. Explain the design through its contracts,
tradeoffs, and recorded evidence.

## A concise introduction

I built a host-programmable protocol engine with four deterministic execution
contexts. A shared instruction store drives firmware-defined serial behavior.
I verify it with a Python cycle model, external-pin RTL tests, independent
protocol waveform checks, and foundry SRAM models. The physical flow uses
Tiny Tapeout's CMOS5L tools. I track simulation, routing, DRC, and LVS as
separate acceptance stages.

## Focus areas

| Interview topic | Project example | Reasoning to explain |
|---|---|---|
| Code Quality and Correctness Review | Host range checks before SPI activity | Invalid inputs preserve device state and errors identify the violated contract |
| Problem and Test Design | Targeted SRAM writes with neighbor readback | Address aliasing, byte preservation, and upper-boundary behavior require distinct tests |
| System Design and Architecture Reasoning | Four contexts share one memory port | The scheduler gives predictable grants while a falling-edge SRAM read prepares rising-edge execution |
| Technical Writing and Structured Feedback | Separate RTL, routing, DRC, and LVS evidence | Describe the exact symptom, affected revision, reproduction, change, and acceptance check |
| Software Development Fundamentals | Assembler, reference model, transport-independent driver | Keep encoding, execution semantics, and board I/O independently testable |

## Questions to practice

**How do you program a known location?**

The host API uses word addresses from 0 to 255. Word 128 maps to byte address
256, which sets the high address bit. I pause execution, load a bounded image
at that word, verify readback, configure the context entry, and resume.
The regression patches both byte lanes and checks the other addresses.

**How do you distinguish simulation success from physical success?**

A cycle-model comparison checks execution behavior. Protocol peers check the
waveform interpretation independently. DRC checks geometry and LVS checks
layout connectivity against the schematic. Each stage produces its own
evidence and has its own acceptance condition.

**What did the LVS debugging teach you?**

The SRAM needs a physical pin interface in the LVS reader. Bus ordering and
escaped supply names also affect Netgen input parsing. I tested the reader
adaptation with a matching fixture and a deliberately miswired array supply.
The fixture validates the adaptation, while the complete-chip reports identify
physical mismatches. Those reports exposed supply columns crossing interface
pins. Moving the SRAM cleared the boundary DRC errors, and the remaining LVS
comparison exposed a sequencing dependency. The flow now places the official
interface pins before selecting power columns, with a guard requiring those
coordinates. This is an example of checking when a design assumption becomes
valid, as well as checking the geometry itself.

**How do you handle a tool workaround responsibly?**

I limit it to the relevant input copy, preserve the original artifact, and
exercise a fault case. The normal LVS metrics and checker remain active.
Power-grid metrics are refreshed after successful connectivity checks, so
the final result describes the extended grid.

## Structured feedback template

1. State the observed behavior and the exact revision.
2. Identify the file, address, pin, or physical coordinate involved.
3. Explain the impact on the design's contract.
4. Describe a bounded correction.
5. Give the reproduction and acceptance test.

## Evidence to bring

- [Host programming and word-address examples](HOST_INTERFACE.md)
- [Architecture and scheduler](ARCHITECTURE.md)
- [Verification cases and results](VERIFICATION.md)
- [SRAM integration and physical-flow status](SRAM.md)
- The final LVS, DRC, timing, and Tiny Tapeout precheck reports for the revision
  discussed in the interview
