# JetAuto wheel tests and 5 m × 4 m left-turn route

## Physical checks completed, 2026-10-18

- Identified STM32: `/dev/ttyACM0`, USB 1a86:55d4, serial 5917012181.
- Tested each wheel individually at 0.5 RPS for 0.75 s, STOP between channels.
  **User confirmed front-left, rear-left, front-right, rear-right moved in that
  order and all stopped.** Final STOP packets were sent.
- RPLiDAR `/dev/lidar` → `/dev/ttyCH341USB0`: health OK; ten physical scans
  captured, 1080 samples per scan. Measured inter-scan interval about 74 ms.
- STM32 passive five-second capture: **550 valid IMU frames**, 100 gamepad
  frames, five system frames; zero CRC errors.
- Source controller now stops for invalid/stale sensors, respects actual scan
  angles, rejects missing physical MCU rather than switching to mock, verifies
  serial write lengths, uses monotonic leases, and closes with STOP.
  Automatic reverse recovery is replaced by zero wheel speed because the rear
  path is not verified. Zero input cannot become residual-generated movement.
- Active-source scan validation now accepts the actual SLAMTEC ~359° coverage;
  it rejects NaN, invalid ranges and invalid/stale stamps.
- Real zero-command sensor→FPGA→controller preflight obtains healthy
  diagnostics, and all executed velocity commands remain exactly zero.

## Requested geometry

This is a rectangle: **5 m forward → left 90° → 4 m forward → left 90° →
5 m forward → left 90° → 4 m forward → left 90°**, ending with initial heading.

Two implementations are available:

1. `rectangle_route`: measured-pose version, waits for a real `/pose` source.
   The existing command-integrating demo pose is not measured localization.
2. `timed_rectangle`: explicitly requested no-localization test. Estimates
   each leg and quarter-turn by integrating the **controller's executed
   velocity commands**, not measured motion. Slip, calibration, steering and
   obstruction can change actual dimensions and closure. It does not prove
   a measured 5 m × 4 m path.

Timed defaults: 0.20 m/s straight, +0.30 rad/s turns, 0.5 s zero interval
between stages. Nominal motion is about 111 s plus pauses. Nonzero unexpected
reverse/lateral/right-turn commands, stale scans/diagnostics, scheduling gaps,
segment/total timeout, transport errors or close obstacles stop the run.

## Prepared command

The current session was built under /tmp; normal persistent build instructions
are in [direct_uart_runbook.md](direct_uart_runbook.md).

```bash
source /opt/ros/humble/setup.bash
source /tmp/igor-uart-install/setup.bash
ROS_LOG_DIR=/tmp/igor-rectangle-run python3 tools/run_timed_rectangle.py \
  --run --floor-ready \
  --output-dir docs/ethernet_validation/rectangle_NEW_RUN_NAME
```

Use a new output directory each time. Omitting `--run --floor-ready` performs
only a zero-velocity preflight. Stop with Ctrl+C; cleanup stops the route
publisher, sends zeros, closes the chassis controller and independently sends
three final STOP packets. An abrupt loss of Jetson power/USB is outside this
software STOP mechanism; the supervisor must have an immediate physical stop.

The robot must be in its normal driving position, with wheels on the floor,
first leg pointing along the clear 5 m side, and a supervised clear perimeter.
The 0.45 m all-around LiDAR clearance requirement is checked before motion.
Do not run other serial owners, teleop or waypoint publishers concurrently.

The physical LiDAR driver used is installed `rplidar_ros`; no synthetic scan
fallback is used. For this supervised low-speed test, sensor lease is **150 ms**
based on measured 74 ms scan updates. The default 25 ms lease remains the
bringup default. This is a test configuration, not a full braking certification.

## Latest route attempts

- First preflight rejected scans because the active source required overly
  exact 360° coverage; fixed and regression-tested against actual metadata.
- Second zero-command preflight obtained 22 healthy diagnostics but detected
  close returns; no route started, all commands zero, final STOP sent.
- User corrected the robot's orientation after LiDAR was scanning the floor.
- First motion-requested preflight obtained 30 healthy diagnostics, but detected
  a 0.284 m return. **Route did not start**, all commands remained zero,
  final STOP sent.
- Follow-up scan found 0.294 m at about +80° and 0.408 m at about −121°.
  Requested those nearby objects/people be moved beyond 0.5 m before retry.

Evidence is under `docs/ethernet_validation/jetauto_*`. Wheel physical outcome
comes from the user's observation; serial write success is not a motor ACK.
No completed floor rectangle is claimed by these preflight results.

## Requested expanded wheel-group test

`tools/test_jetauto_wheels.py` now supports four individual wheels, all six
unique pairs, and all four together: **11 pulses**, default 0.5 RPS for
0.75 seconds each, STOP and pause between groups. Right-side motor signs
remain mirrored. Plan uniqueness, group cardinality, packet lengths and CRCs
were checked without opening the serial port.

```bash
python3 tools/test_jetauto_wheels.py --groups singles pairs four \
  --run --wheels-raised \
  --output docs/ethernet_validation/wheel_groups_NEW_RUN_NAME.json
```

This command requires all wheels lifted, securely supported and clear. The user subsequently confirmed all four wheels lifted and clear. The expanded
sequence completed **11/11 command groups**, with final STOP sent. Capture:
[jetauto_wheel_groups_20261018_run1.json](ethernet_validation/jetauto_wheel_groups_20261018_run1.json).
The user confirmed **all 11 groups moved and stopped correctly**. Physical
acceptance is user-observed; the serial interface supplies no motor feedback.
