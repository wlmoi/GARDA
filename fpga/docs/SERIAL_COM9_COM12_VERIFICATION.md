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

Captured traffic stays local unless the user explicitly authorizes publication. Do not add raw captures or decoded payloads to a public repository by default.

Parser self-check (no hardware):

```powershell
python fpga/scripts/verify_serial_links.py --self-test
```

This checks CRC8's standard `123456789` vector, noise resynchronization, an AA55
sequence inside payload, an invalid CRC and an incomplete tail. Core/weights/bitstreams are not changed by this diagnostic.
