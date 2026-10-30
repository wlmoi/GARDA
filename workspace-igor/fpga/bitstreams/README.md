# Program IGOR Parallel8 on DE10-Nano

**Physical UART on JP7:** use
[PROGRAM_PARALLEL8_JP7.bat](PROGRAM_PARALLEL8_JP7.bat) to program RX on JP7 pin 1
and TX on pin 2. [TEST_JP7_UART.bat](TEST_JP7_UART.bat) runs the binary protocol
test through a USB–TTL COM adapter. The [JP7 project guide](../experiments/parallel8_jp7/README.md)
contains wiring, baud and project instructions; [bring-up evidence](../evidence/jp7_uart/README.md)
distinguishes successful programming from pending physical UART validation.

**USB-Blaster console option (19 October 2026):**
double-click the Desktop shortcut **IGOR - JTAG Terminal**, or
[OPEN_JTAG_TERMINAL.bat](OPEN_JTAG_TERMINAL.bat). It programs the separate
`igor_parallel8_jtag.sof` and opens the real JTAG UART console. Type `r` for a
known-vector inference. This variant passed five physical JTAG command tests;
see the [console guide](../experiments/parallel8_jtag/README.md) and
[original GUI/runtime evidence](../evidence/jtag_parallel8/README.md).
Use the original image below for physical JP1 RX; the console image owns its
receiver through an internal serializer.

**Use `igor_src_policy_parallel8.sof` for the verified 74 -> 128 -> 64 -> 3
neural core: 6,916 cycles, 138.32 us at 50 MHz.** Pins and model weights are
already compiled into this image. No new compilation or pin planning is needed.
These are simulation/build results; a successful JTAG load is recorded separately.

**Board programmed successfully on 18 October 2026 at 12:58 WIB:** Quartus
reported `Configuration succeeded -- 1 device(s) configured`, with 0 errors
and 0 warnings. Cable: `DE-SoC [USB-1]`; HPS @1 bypass, FPGA @2 programmed.
See [actual programming log](../evidence/current_programming/20261018T0558125221956Z/programming.log)
and [receipt](../evidence/current_programming/20261018T0558125221956Z/inspection.json).
This confirms configuration; the runtime UART/robot test is separate.

## Program the board

1. Power the DE10-Nano and connect its USB-Blaster/JTAG port to the PC.
2. Double-click **[PROGRAM_PARALLEL8.bat](PROGRAM_PARALLEL8.bat)**.
3. Wait for the Quartus success message. Press and release KEY0 to reset.

The launcher uses the installed Quartus 25 tools at
`D:\Quartus-Program\quartus\bin64`, selects the only detected `5CSEBA6`,
checks the image against the accepted build and release, then programs it.
Other chain devices are bypassed at their detected positions. It stops when
the chain is unreadable, ambiguous, or has the wrong FPGA, or checksums fail.
The complete `fpga/` folder and Python are needed for release verification.
This launcher does not rebuild the RTL.

Run from the workspace root for inspection without programming:

```powershell
powershell -NoProfile -File fpga/scripts/program_fpga.ps1 -Project source_policy_parallel8 -AutoSelect
```

For a different Quartus location, pass `-QuartusBin "C:\...\quartus\bin64"`
to the script or launcher. With multiple boards, also select `-Cable N`.

Every attempt records logs and `inspection.json` under
[`../evidence/current_programming/`](../evidence/current_programming/).
`hardware_programmed=true` means the programming command completed successfully;
UART function and robot operation require separate checks. Once the FPGA is
identified, `detected_board.cdf` is generated there from the actual chain and
can be reopened in Quartus Programmer.

## Native Quartus programming project

Open **[OPEN_PROGRAMMER.bat](OPEN_PROGRAMMER.bat)**, or open
**[igor_src_policy_parallel8.cdf](igor_src_policy_parallel8.cdf)** in Quartus
Programmer. The CDF contains the chain actually observed during the successful
load: **SOCVHPS @1 bypass, 5CSEBA6 @2 Program/Configure**, with the correct SOF
selected. Select `DE-SoC [USB-1]`, then **Start**. If using a different board or
chain, use **Auto Detect** and attach `igor_src_policy_parallel8.sof` to the
detected `5CSEBA6` row, keeping HPS in bypass.
Keep the CDF and SOF together. The launcher sets this folder as working directory.

The complete, pin-planned RTL project is
[igor_src_policy.qpf](../experiments/parallel8/igor_src_policy.qpf).
Use that QPF for source inspection or recompilation; use CDF/Programmer when
you only want to load the existing image.

## Identity and runtime connections

- Device: Cyclone V SE **5CSEBA6U23I7**, DE10-Nano.
- SOF SHA256: `cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49`.
- Acceptance: [Parallel8 receipt](../experiments/parallel8/artifacts/acceptance.json).
- UART: nominal **921600, 8N1**, 3.3 V TTL. Adapter/Jetson TX -> JP1 pin 1
  (FPGA RX, V12); adapter/Jetson RX <- JP1 pin 2 (FPGA TX, E8); common GND
  on JP1 pin 12 or 30. The HPS USB console is a different interface.
- KEY0: reset. KEY1: latched E-stop; release it and use KEY0 to recover.
- LED0: safety permit; LED1: reset released; LED2: response-valid pulse;
  LED3: E-stop active; LED7:4: error code. LED0 can remain off until a valid
  transaction; the image waits for observations rather than moving a motor.
- SOF configures volatile FPGA SRAM and must be reloaded after power-off.
  The `.rbf` file is for a separately configured FPGA-manager/boot flow;
  do not select RBF for this JTAG procedure.

## USB driver troubleshooting

Bundled official driver folders:
`D:\Quartus-Program\quartus\drivers\usb-blaster` and `usb-blaster-ii`.
On 18 October 2026 Windows reported both packages already installed
(`oem54.inf`, `oem87.inf`). The connected unknown USB device instead reported
Code 43 and `USB\DEVICE_DESCRIPTOR_FAILURE`; this does not identify it as
USB-Blaster. Replace/check the USB data cable, connect directly to another PC
USB port, confirm board power and the correct JTAG connector, then retry.
Do not force an Altera driver onto an unidentified USB device.
After reconnection, JTAG identified `SOCVHPS` and `5CSEBA6`, and the programming
operation above succeeded. The earlier Code 43 was a connection/enumeration
failure, not evidence that the bundled driver packages were missing.
