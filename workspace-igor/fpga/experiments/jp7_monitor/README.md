# Physical JP7 monitor — diagnostic image

This isolated image keeps the Parallel8 core and weight banks, physical UART RX
on JP7 pin 1/Y15 and TX on pin 2/AC24, and adds an Intel JTAG UART console.
It does not connect JP1 to Jetson while running. Restore the original JP1 image
for Jetson operation, or use a separately verified integration for simultaneous
links. STM COM9 is not forwarded or written by this diagnostic.

The JTAG console supports:

- `q`: snapshot actual pad RX transition count, decoded byte count, last byte,
  framing errors, safety stop, policy accepted/rejected counts, error and cycles.
- `e`: enable transparent physical pad RX-to-TX echo for adapter continuity tests.
  Echoed bytes are not inference results. This mode bypasses policy TX only.
- `i`: restore normal policy UART TX (the reset default).

The input stream always reaches the normal policy receiver. Echo tests send
diagnostic bytes, so the parser may record a rejection; inference requires a
new valid observation frame after returning to mode `i`. No motor is driven.

`fpga/scripts/diagnose_jp7_monitor.py` queries JTAG, tests physical COM12 echo at
9600/115200/921600 baud, returns to inference mode, tests the known observation,
and queries counters again. It writes local evidence only. No jumper between
the two female adapter connectors is required. Close other JTAG/COM12 terminals
before running it. Both USB-Blaster and the USB–TTL adapter must be attached.

Open `igor_jp7_monitor.qpf` in Quartus 25.1 Standard. Prepare source files with
`fpga/scripts/prepare_jp7_monitor.py` before compilation, never during a build.
Vendor IP paths point to the installed Quartus directory. The monitor simulation
checks decoded bytes, bad stop bits, counters, snapshots and mode commands.
It does not validate physical wires; those conclusions require runtime logs.
