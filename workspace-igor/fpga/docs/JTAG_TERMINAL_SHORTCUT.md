# Desktop JTAG terminal

Double-click `IGOR - JTAG Terminal` on the Windows Desktop. The shortcut runs
`fpga/bitstreams/OPEN_JTAG_TERMINAL.bat`, which invokes
`fpga/scripts/open_jtag_terminal.ps1` using the installed Quartus tools.

The Desktop launcher enumerates the JTAG chain, verifies the dedicated JTAG SOF
against its SHA256 receipt, programs that image, and opens an interactive terminal.
It does not rebuild RTL. The window stays open after an error so the diagnostic
remains visible. Press any key to close it. Chain/programming/probe logs are saved
under `fpga/evidence/jtag_terminal/<UTC timestamp>/`.

The console runs one automatic demonstration after reset. Type `r` for another
known-vector inference or `!` for the deliberate CRC rejection test. A complete
custom observation frame can be entered as hexadecimal pairs and Enter. See the
[project and command guide](../experiments/parallel8_jtag/README.md).

## Initial diagnosis before adding the JTAG variant

The live check on 19 October 2026 detected `DE-SoC [USB-1]`, `SOCVHPS`, and
`5CSEBA6`. Quartus reported: `There are no JTAG UARTs available`.
See `fpga/evidence/jtag_terminal/20261019T1207461333405Z/` for the original logs.

The original accepted Parallel8 SOF provides a physical UART on JP1 pins 1/2 at
921600 baud. USB-Blaster does not convert those pins into a Windows COM port.
The new, separate `igor_parallel8_jtag.sof` adds the JTAG UART console and feeds
the policy receiver with an internal UART serializer. It retains the original
Parallel8 core and weights. Physical JP1 RX is reserved for the original image;
the JTAG variant uses the console as its input source.

For a diagnostic-only run from PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File fpga/scripts/open_jtag_terminal.ps1 -ProbeOnly
```

Default tools: `D:\Quartus-Program\quartus\bin64`; default cable: `1`.
The script accepts `-QuartusBin` and `-Cable` overrides. Direct invocation without
`-ProgramJtagImage` opens the image already on the board. `-ProbeOnly` performs
the bounded three-second diagnostic and may consume startup output.
