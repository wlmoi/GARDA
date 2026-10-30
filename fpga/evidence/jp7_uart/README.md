# JP7 UART bring-up — 19 October 2026

Project: `../../experiments/parallel8_jp7/igor_parallel8_jp7.qpf`.
RX is JP7 pin 1 / Y15; TX is JP7 pin 2 / AC24. Both are fitted as 3.3-V LVTTL.
Pin assignments are confirmed in the original Quartus `.pin` report.

Full compilation finished at 19:56:47 WIB: zero errors, 49 warnings. Timing
Analyzer completed with zero errors/warnings. Original reports are in the project
`output_files` directory. This build uses 3,301 ALMs, 6,264 registers, 64 M10K,
eight DSP, zero PLL and 13 pins. Source SHA256 checks confirm copied RTL, SDC
and eight weight banks match the original Parallel8 project.

`20261019T1257277362133Z/programming.log` records successful physical FPGA
configuration at 19:57:32 WIB, zero errors/warnings, checksum 0x022A4972.
`image_receipt.json` identifies the exact SOF and timing acceptance.

COM12 is a Prolific USB-to-Serial adapter, USB VID:PID 067B:2303. The first
request (`20261019T1257513567109Z`) and the retry after user-confirmed wiring/reset
(`20261019T1259261074901Z`) opened COM12 and sent the default observation frame,
but received zero response bytes. Physical inference over JP7 is therefore
**not yet validated**. Programming success does not establish UART continuity.

The next diagnostic is a user-prepared adapter loopback, with FPGA disconnected
and adapter TX joined to RX. `../../scripts/test_ttl_loopback.py --port COM12`
records byte-exact echo tests at 9600, 115200 and 921600 baud. Do not run that
diagnostic as proof of FPGA inference; it tests the adapter separately.
