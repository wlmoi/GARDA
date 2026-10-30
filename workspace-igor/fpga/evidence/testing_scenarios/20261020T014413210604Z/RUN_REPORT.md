# Scenario run — 20 October 2026

Status: **FAIL — interrupted by USB device disappearance**. No chassis motion commanded.

- Initial inventory: STM32 COM9, FPGA UART COM18, LiDAR COM19, DE-SoC USB-Blaster.
- Quartus programmed accepted Parallel8 JP1 pin 1/2 monitor successfully, checksum `0x02434612`, zero errors/warnings.
- Approved CH340 driver 3.4.2014.8 restored; ProblemCode 0.
- Exact Desktop target `RUN_LAPTOP_ABC.bat` selected FULL HARDWARE CHECKS.
- **53 software tests passed**, model/oracle identity passed, **256-vector RTL simulation passed**.
- **96 physical FPGA vectors / 288 outputs matched exactly**, 0 LSB error, 6,916 core cycles. This is partial coverage, not a 256-vector pass.
- Next UART write failed with Windows `WriteFile failed` / `The device does not recognize the command`. Enumeration then showed no FPGA UART, no JTAG, and no LiDAR; only STM32 COM9 remained. The separate UART-return and passive JTAG stages consequently failed.
- LiDAR initial device-info query had received 0 bytes; no scan PASS is claimed.
- STM32 delivered 104 CRC-valid frames: 99 type-8 length-7 and five type-0 length-3; no type-7 IMU packet was seen.
- Overall runner: **10 PASS, 4 FAIL, 6 unresolved**. Missing security-auth test and physical A/B/C acceptance remain unresolved.

See `summary.json`, stage logs, `sensors/summary.json` and `fpga/evidence/mock_board_jtag/20261020T014552892337Z/summary.json`. Legacy scope strings mention COM12; the actual input port for this run was COM18.

Operator subsequently reconnected hardware. Retry must use a new timestamped folder; this original failed run is preserved. Source/RTL logic was not changed.
