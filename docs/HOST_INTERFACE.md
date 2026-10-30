# Host interface

The host SPI bus is independent of protocol GPIO: CS_n=`ui[0]`, SCLK=`ui[1]`,
MOSI=`ui[2]`, MISO=`uo[0]`. Use mode 0, MSB first. The core clock must run.
Allow at least four core clocks per SCLK half-period and for CS setup/recovery.
MISO is zero while CS is inactive; this dedicated output is not tri-stated.

Every frame starts with `{write, address[6:0]}`, followed by data bytes.
Writes have bit 7 set; reads have bit 7 clear and transmit dummy data bytes.
CS stays low for the complete frame. The register address stays fixed across
a burst; only DATA's internal byte address auto-increments, modulo 512.
Program words use little-endian bytes: low byte then high byte.

| Address | Register | Behavior |
|---|---|---|
| 0 | CONTROL | R/W bit 0 enables core execution. Software pause retains pin state. |
| 1 | STATUS | Read `{errors[3:0], running[3:0]}`. |
| 2 | ADDRESS_LO | R/W program byte address bits 7:0. |
| 3 | ADDRESS_HI | R/W program byte address bit 8 in bit 0; nonzero bits 7:1 are rejected. |
| 4 | DATA | Read/write program byte, auto-increment. Reads and writes accepted only while CONTROL=0; rejected accesses return zero on reads, do not advance address and set selected context error. |
| 5 | CONTEXT | R/W selected context ID in bits 1:0. |
| 6 | ENTRY_LO | R/W restart PC bits 7:0. |
| 7 | ENTRY_HI | Read zero; nonzero writes are rejected (PC is eight bits). |
| 8 | RESTART | Write context bitmap: reset execution state, load ENTRY, start selected contexts. |
| 9 | STOP | Write context bitmap: halt selected contexts and release their owned pins. |
| 10 | PIN_MASK | R/W selected context output ownership. Writes require CONTROL=0 and no overlap with another context. Accepted changes release the old mask. |
| 11 | ERROR_CLEAR | Write-one-to-clear context error bitmap. |
| 12 | ID | Read 0xA7 (compact ISA/memory revision). |
| 13, 14 | RECEIVE_LO/HI | Read selected context receive register. |
| 15, 16 | PC_LO/HI | Read selected context PC. |
| 17, 18 | X_LO/HI | Read selected context X. |
| 19 | PROGRAM_AW | Read 8: program depth is 2^8 words. |

Unmapped reads return zero; unmapped writes have no register effect.
Control writes serialize with execution and may stretch a transaction.
Program DATA reads require software pause because execution and readback
share one read port. Pausing before multibyte debug reads gives a coherent
snapshot. `ena` also pauses
execution but releases physical GPIO, unlike software CONTROL pause.

`tools.host.Engine` accepts a `transfer(bytes) -> bytes` callback supplied by
your board's SPI library. It verifies frame length, program readback, and pin
ownership configuration. Each callback must assert CS for the whole frame.

```python
from tools.build_demo import build_demo
from tools.host import Engine

engine = Engine(board_spi_transfer)  # Your mode-0 board transport.
assert engine.identify() == 0xA7
image, contexts = build_demo()
engine.pause()
engine.stop()
engine.load(image)
# On reuse, clear each previous mask first to allow pin reassignment.
for tid in range(4):
    engine.configure(tid, 0)
for context in contexts:
    engine.configure(context['tid'], context['pin_mask'])
    engine.start(1 << context['tid'], context['entry'])
engine.resume()
```

The demo uses test-oriented timing; choose compatible timing and peripheral
connections before a board run. Read STATUS to identify completed or errored
contexts. `engine.received(tid)` pauses execution before reading and leaves it
paused; resume explicitly when appropriate. Clear sticky errors with register
11 before retrying a rejected configuration.

Program memory is unspecified after power-up. Load every reachable word and
literal before starting; the demo fills unused words with HALT. Reset retains
written program memory in RTL but clears all control and ownership state.

## Program an exact SRAM word address

Host entry addresses are word indices from 0 through 255. Each word contains
two little-endian bytes. The hardware byte address is twice the word index.

| Word address | Byte address | ADDRESS_HI | ADDRESS_LO |
|---|---|---|---|
| 0x00 | 0x000 | 0x00 | 0x00 |
| 0x7F | 0x0FE | 0x00 | 0xFE |
| 0x80 | 0x100 | 0x01 | 0x00 |
| 0xFF | 0x1FE | 0x01 | 0xFE |

The following example uses a freshly reset device and starts a UART transmit
program at word 0x80. The host transport supplies a complete mode-0 SPI frame
per callback and follows the documented core-clock timing.

```python
from tools.host import Engine
from tools.protocols import uart_bit_grants, uart_tx

engine = Engine(board_spi_transfer)
period = uart_bit_grants(50_000_000, 115_200, receive=True)
program = uart_tx(0x55, pin=1, bit_grants=period)
entry = 0x80

engine.stop()
engine.load(program, entry=entry)
assert engine.read_program(entry=entry, count=len(program)) == program
engine.configure(tid=0, pin_mask=0x02)
engine.start(mask=1, entry=entry)
engine.resume()
```

`load` verifies the programmed bytes by default. `read_program` returns
16-bit words and leaves the engine paused. Address and length validation
precedes SPI activity, including the upper boundary at word 255. The RTL
regression verifies targeted writes and unchanged neighbors through SPI pins.

The SRAM's layout origin is fixed at (300.0, 34.02) micrometers in the
physical configuration. Runtime programming selects an internal word address.
See [SRAM integration](SRAM.md) for the macro and supply geometry.
