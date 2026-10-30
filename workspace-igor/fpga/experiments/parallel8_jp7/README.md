# Parallel8 UART on JP7 — DE10-Nano

Open `igor_parallel8_jp7.qpf` in Quartus Standard 25.1. This separate project
keeps the original Parallel8 core, weights, top-level behavior and UART protocol.
Only RX/TX pad locations change from JP1 to JP7. No motor is connected by this RTL.

| USB–TTL adapter, 3.3 V logic | DE10-Nano |
| --- | --- |
| TX output | JP7 pin 1 → FPGA UART_RX, Y15 / GPIO_1[0] |
| RX input | JP7 pin 2 ← FPGA UART_TX, AC24 / GPIO_1[1] |
| GND | JP7 pin 12 (or 30) |
| VCC | Leave disconnected; power the board normally |

Pin numbers mean physical header pins, not zero-based GPIO indexes. Verify the
pin-1 marking on the board. Source: Terasic DE10-Nano User Manual, Figure 3-20,
printed page 27 and Table 3-10, printed page 29:
[official manual distributed by Mouser](https://www.mouser.com/datasheet/2/598/DE10_Nano_User_manual_a_b-1108056.pdf#page=28).

The adapter USB end connects to the laptop and must enumerate as a COM port.
USB-Blaster separately programs the FPGA over JTAG; JP7 carries application data.
Program this image with `fpga/bitstreams/PROGRAM_PARALLEL8_JP7.bat`. The Desktop
JTAG Terminal shortcut programs a different image and disconnects physical JP7 RX;
use the JP7 programming launcher when returning to the USB–TTL connection.
Baud: **921600**, eight data bits, no parity, one stop bit, no flow control.
Keep KEY1 released; press/release KEY0 to reset and clear the E-stop latch.

This is a binary inference protocol, not the ASCII `r` JTAG console. The FPGA
waits for a valid 153-byte observation request and returns an 11-byte CRC-checked
response. Typing `r` in MobaXterm does not invoke inference on this image.
An idle terminal may therefore remain blank. Use the host protocol test:

```powershell
python src/igor_pipeline/scripts/uart_test.py --port COM5 --baud 921600 --iter 10 --dump-hex
```

Run from the repository root and replace COM5 with the detected adapter port.
Alternatively double-click `fpga/bitstreams/TEST_JP7_UART.bat`; it detects a sole
USB serial COM adapter and captures ten requests/responses under
`fpga/evidence/jp7_uart/`. It stops when none or multiple adapters are present.
Do not open MobaXterm on the same COM port during this test. Expected default
residuals are raw Q8.8 `[-46,60,34]`; expected core latency remains 6,916 cycles
at 50 MHz (138.32 µs), while serial/USB/host round-trip latency is additional.

Prepare sources with `python fpga/scripts/prepare_jp7_variant.py` before compiling.
From this directory run Quartus `quartus_sh --flow compile igor_parallel8_jp7`.
Original implementation reports are in `output_files/`. `source_manifest.json`
records hashes for copied RTL and weight banks. Build/programming success and
physical UART runtime validation must be distinguished in the evidence logs.
