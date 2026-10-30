# Testing scenario report — 20 October 2026

**Programmed and tested on real DE10-Nano. Overall scenario acceptance remains FAIL/INCOMPLETE due missing IMU telemetry and physical acceptance prerequisites.**

## Setup

- JTAG: DE-SoC [USB-1], FPGA 5CSEBA6 at chain index 2.
- Accepted Parallel8 JP1 pins 1/2 observer image programmed successfully with Quartus 25.1; SOF checksum `0x02434612`, zero errors/warnings. RX pad V12, TX pad E8.
- Laptop adapter TX -> JP1 pin 1; adapter RX <- JP1 pin 2; GND pin 12. UART 921600 baud.
- After reconnection: FPGA UART **COM18**, STM32 **COM9**, LiDAR **COM17**. Approved signed CH340 driver **3.4.2014.8** restored; device ProblemCode 0.
- Ran exact Desktop target `fpga/bitstreams/RUN_LAPTOP_ABC.bat`, selecting FULL HARDWARE CHECKS. No source/RTL modifications, no motor commands and no robot movement.

## Results

| Check | Actual result | Evidence |
|---|---|---|
| Software unit tests | 53 PASS | [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/summary.json) |
| Integer model/oracle provenance | PASS | [model_identity_oracle.log](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/model_identity_oracle.log) |
| RTL simulation | 256 vectors / 768 output checks PASS | [parallel8_rtl_256_vectors.log](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/parallel8_rtl_256_vectors.log) |
| Physical FPGA, COM18 input + JTAG observer | 256 vectors / 768 outputs; 0 LSB error; 6916 cycles each | [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/mock_board_jtag/20261020T014918319941Z/summary.json) |
| Physical UART request/response | 261 valid transactions, 783 outputs, 0 mismatches; four malformed-input tests PASS | [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/mock_inference/20261020T014955061062Z/summary.json) |
| Actual packaged controller bridge, timeout=20ms | 256/256 synthetic observations PASS; mean 13.245ms, max 19.871ms | [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/controller_deadline/summary.json) |
| Passive JTAG datalogger | 9 snapshots; completed; no error | [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/datalogger/20261020T015026443449Z/summary.json) |
| LiDAR original 5-second preflight | 52 rotations; identity/health/transport OK; only 1 quality-qualified scan, so original stage FAIL | [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/sensors/summary.json) |
| LiDAR extended 30-second check | 382 rotations; 194 quality-qualified; 0 resynchronization bytes; format contract PASS | [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/lidar_extended/summary.json) |
| STM32 telemetry | 103 CRC-valid frames; no type-7 IMU packet; imu_ok=false | [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/sensors/summary.json) |

## Interpretation

- The original runner summary is preserved unchanged: **13 PASS, 1 FAIL, 6 unresolved**. Its failed sensor preflight is not rewritten as PASS after a supplemental longer LiDAR capture. Missing IMU remains unresolved.
- STM32 capture: 99 type-8 length-7 and four type-0 length-3 frames, zero bad CRC candidates, **zero finite IMU frames**. Successful USB communication is not proof of IMU readiness.
- Extended LiDAR passed the existing project quality criterion, with 67–94 valid distance points per rotation. Only 10–23 of the 64 derived candidate features had full two-bin measured support per rotation. Missing support is recorded, not relabelled measured clear space. Full 74-feature live observation is not established.
- Core time **6916 / 50MHz = 138.32 microseconds**. Controller-bridge timings above include host/USB/UART work and were measured on this laptop with the existing bridge in real mode. Observed max under 20ms is a finite test result, not a worst-case scheduling guarantee.
- The standalone numerical UART harness reports mean 113.776ms and max 114.913ms. That harness includes `serial.flush()` and a separate response-reading path; it is a different measurement path from the packaged controller bridge. Do not substitute either host timing for core latency. No transport source was edited to improve these numbers.
- Invalid-input checks: bad CRC, negative LiDAR, tail feature above normalized one, truncated frame; all rejected without successful replies, followed by valid recovery transactions.
- The passive logger sampled the last completed inference, with no new inputs injected during its three-second stage. `new_results_observed=0` is therefore expected; it is not a live sensor-to-FPGA stream test. Its error field retained `0x0B` (stale residual) after idle time; the log is preserved, not presented as a zero-fault continuous-control run.
- Physical inputs used for numerical and deadline comparisons were synthetic 74-feature vectors. No claim is made that these were live LiDAR/IMU control observations.

## Outstanding testing_scenario.md requirements

- STM32 IMU telemetry must provide the expected type-7 six-float payload, with confirmed units/calibration and freshness. Current frames do not meet that requirement.
- `test/test_security_auth.py` does not exist; no zero-test PASS was substituted.
- A1 requires independently measured pose and physical 5x4m route evidence; A2 requires a supervised physical command-estimated run. Fixture route tests are separate.
- B live robot inference trace requires actual complete sensor observations and actuator/control trace. The bench vector tests above do not replace it.
- C requires supervised cable pull during real motion, four-wheel STOP/reconnect trace and measured stopping time/distance. No motion was started.

## Previous interrupted attempt

The earlier run stopped after 96 exact physical vectors when Windows lost FPGA UART/JTAG/LiDAR. It remains preserved at [RUN_REPORT.md](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014413210604Z/RUN_REPORT.md). The retry above is a separate complete numerical run.

## Traceability

- [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/mock_board_jtag/20261020T014918319941Z/summary.json) — SHA-256 `9a305e891fa34093a6e96084bbb1a82a028370b2d989b0f401df48de57e973b6`.
- [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/mock_inference/20261020T014955061062Z/summary.json) — SHA-256 `fee9bac7b0210f3523e7221dcb408ace918e38c1e54b86b46ebf42d63e772ac5`.
- [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/datalogger/20261020T015026443449Z/summary.json) — SHA-256 `4821ba11df2dddab90ea4aa1b2154dcfe3f4660eb631a7948a69a619647102ad`.
- [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/summary.json) — SHA-256 `4bfad91dba082cf765d5e39d2359c63899579313e392f95759ab0adb71b22d9d`.
- [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/sensors/summary.json) — SHA-256 `c1f6a1ebf3210c20477d2302767498c25df80dcdec54c4961731d5deb38cf65b`.
- [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/lidar_extended/summary.json) — SHA-256 `f42e8de24b344e88330e2b381e29403ab4af5979d5830a85c3617f1091d2c4dd`.
- [summary.json](D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/testing_scenarios/20261020T014758007153Z/controller_deadline/summary.json) — SHA-256 `d75485d387f2ff80dcf5927b2e683ac3d04d63c5e118aa4eee134c8149516cb0`.
