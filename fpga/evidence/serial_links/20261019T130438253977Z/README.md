# STM COM9 and FPGA COM12 verification

Run `fpga/bitstreams/VERIFY_COM9_COM12.bat`, or from the repository root:

```powershell
python fpga/scripts/verify_serial_links.py
```

Close other serial applications on COM9 and COM12 first. The script does not
program the FPGA or change pin assignments. It reads STM COM9 without sending
application commands, while sending one valid 153-byte inference request to
FPGA COM12. It never forwards STM data to the FPGA or sends motor commands.
No female-to-female jumper or adapter loopback is required for this script.

Default COM9 capture: two seconds each at 1,000,000, 115,200, 921,600 and 9,600
baud, 8N1, no flow control. For a capture at the verified STM rate only:

```powershell
python fpga/scripts/verify_serial_links.py --stm-bauds 1000000 --seconds 5
```

Logs are saved under `fpga/evidence/serial_links/<UTC timestamp>/`:
raw `.bin` data, timestamped chunk captures, decoded CRC-valid frames, USB port
identity and `results.json`. Exit code zero requires both a CRC-valid STM frame
and a correct FPGA inference response. A successful STM capture alone does not
establish the FPGA connection. Opening a COM port is not evidence of received data.

## Physical result, 19 October 2026

Original evidence: `fpga/evidence/serial_links/20261019T130438253977Z/results.json`.

| Link | Actual result |
| --- | --- |
| COM9, CH9102 USB VID:PID 1A86:55D4, 1,000,000 baud | 489 bytes; 41 CRC-valid AA55 frames |
| COM9 at the three other tested rates | Some raw bytes; no CRC-valid AA55 frames |
| COM12, Prolific USB VID:PID 067B:2303, 921,600 baud | 153 request bytes written; zero response bytes; inference test failed |

Of the 41 valid STM frames, 40 had type `08`, payload length 7; one had type
`00`, payload length 3. Example actually received:

```text
AA 55 08 07 00 00 00 00 00 00 00 8D
```

The STM parser verifies `AA 55 TYPE LEN PAYLOAD CRC8/MAXIM`; CRC starts at zero
and covers TYPE+LEN+PAYLOAD, using reflected polynomial 8C. The example's seven
zero payload bytes are actual captured data. Frame type semantics are not
inferred from the numeric type alone; use the running STM firmware definition.

The JP7 inference image instead expects `5A A5 01 94` plus 74 signed little-endian
Q8.8 observations and CRC, and returns `5A A5 02 06` plus three residuals and CRC.
STM's 1 Mbps AA55 stream is not a valid observation packet for that 921600-baud
image. Observing COM9 over USB on the laptop does not show that STM data reaches
JP7 electrically. The script measures the two independent links, not an integrated
STM-to-FPGA pipeline. Physical JP7 UART continuity remains unresolved.

Parser self-check (no hardware):

```powershell
python fpga/scripts/verify_serial_links.py --self-test
```

This checks CRC8's standard `123456789` vector, noise resynchronization, an AA55
sequence inside payload, an invalid CRC and an incomplete tail. It passed before
the physical capture. Core/weights/bitstreams were not changed for this test.
