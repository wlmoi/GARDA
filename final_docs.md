# Project IGOR — final operating and test guide

**Recorded hardware session: 18 October 2026**  
Workspace: `/home/toyotateamaitb/igor_ws`  
Devices: NVIDIA Jetson Orin Nano, Terasic DE10-Nano, Hiwonder JetAuto STM32 chassis, RPLiDAR.

This guide describes the code and hardware tested in this session. Use it for the current setup; older instructions in `pipeline_docs.md`, `test.md`, and older README sections contain superseded protocols, addresses, or daemon flags.

## 1. What works, and what remains unverified

| Item | Result |
|---|---|
| Jetson ↔ DE10 HPS Ethernet | Working: 1 Gbit/s full duplex; ping and SSH verified |
| Physical Ethernet UDP request/reply | 10/10 network-only transactions passed; mean RTT 1.639 ms |
| Jetson header UART | Exact 512-byte loopback passed at 115200 and 921600 baud |
| Actual FPGA inference over direct Jetson UART | **98/98 passed**, including 16 different model fixtures; mean RTT 4.594 ms, maximum 5.920 ms |
| STM32 communication and IMU | 550 CRC-valid IMU frames in five seconds; zero CRC errors |
| Physical LiDAR | Health OK; real 1080-sample scans received; approximately 74 ms between scans in the captured sample |
| Individual wheels | User observed each wheel move in the expected order and stop |
| Expanded wheel combinations | **All 11 groups moved and stopped correctly**, confirmed by the user |
| Live sensors → FPGA → controller with zero velocity requested | Healthy diagnostics received; all output velocity commands remained zero |
| ROS packages | `waypoint_action`, `igor_navigation`, `igor_controller`, and `igor_bringup` built successfully |
| 5 m × 4 m route implementation | Measured-pose and command-estimated versions implemented and software-tested |
| Completed rectangle on the floor | **Not demonstrated.** The motion-requested preflight detected a nearby return at 0.284 m and prevented the route from starting |
| AI inference specifically through Ethernet | **Not demonstrated.** The verified inference connection is direct Jetson GPIO UART |

The session established physical FPGA inference and physical motor operation, and exercised the live pipeline while requesting zero movement. It did not establish a completed moving sensor→FPGA→motor navigation mission. Serial write success is not motor feedback; physical wheel results came from user observation.

## 2. Actual architecture

```text
RPLiDAR ── USB /dev/lidar ───────────────────────┐
                                               v
STM32 ── USB /dev/ttyACM0 ── IMU ──> Jetson controller
                                               |
                           form 74-feature observation
                                               |
                         /dev/ttyTHS1, 921600 baud
                                               v
                                   DE10 FPGA Parallel8
                                               |
                                  3 Q8.8 AI residuals
                                               v
                               Jetson blending / CBF / STOP gates
                                               |
                                   Mecanum inverse kinematics
                                               |
                            STM32 USB, 1,000,000 baud
                                               v
                                      Four wheel motors

Separate working network connection:
Jetson enP8p1s0 192.168.50.1 <── Ethernet ──> DE10 HPS end0 192.168.50.2
```

The FPGA receives **74 processed features**, not complete raw sensor streams:

- 64 normalized frontal LiDAR features.
- Six IMU features.
- Three nominal velocity-command features.
- One normalized heading-error feature.

Jetson retains sensor processing, filtering, safety checks, kinematics, and STM32 motor commands. The FPGA returns three residual actions. A zero residual alone does not mean the motors should stop; the controller must zero the complete motor command on a fault or zero nominal input.

### Wire protocols

| Link | Protocol |
|---|---|
| Jetson GPIO ↔ FPGA | 921600 baud, 8N1, 3.3 V TTL; 153-byte request, 11-byte response; CRC8 Maxim; signed Q8.8 |
| Jetson ↔ STM32 | USB serial, 1,000,000 baud; `AA 55`, motor function `0x03`; four zero-based motor indices and float32 RPS; CRC8 |
| Jetson ↔ HPS UDP | Port 8080; Protocol V2, exactly 492-byte requests and 50-byte replies; CRC32 and correlated frame/timestamp |

UDP status 6 means **network-only mock**, not FPGA inference success. Production clients reject it.

## 3. Wiring and device identification

### Direct FPGA UART — the verified AI path

| Jetson 40-pin header | DE10 FPGA JP1 |
|---|---|
| Pin 8, TX | Pin 1, UART RX |
| Pin 10, RX | Pin 2, UART TX |
| Pin 9, GND | Pin 12, GND |

Use 3.3 V signal levels and a common ground. The FPGA project maps RX to FPGA pin V12 and TX to E8. Verify physical JP1 pin orientation. Remove any pin 8–10 loopback jumper before reconnecting FPGA signals.

### USB devices on this Jetson

| Device | Path/identity observed |
|---|---|
| Jetson header UART | `/dev/ttyTHS1`, controller `serial@3100000` |
| STM32 | `/dev/ttyACM0`, USB `1a86:55d4`, serial `5917012181` |
| Stable STM32 path | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5917012181-if00` |
| LiDAR | `/dev/lidar` → `/dev/ttyCH341USB0`, USB `1a86:7523` |
| DE10 HPS USB console, when connected | FT232R `0403:6001`; observed `/dev/ttyUSB0` with stable ID `usb-FTDI_FT232R_USB_UART_B402QWPK-if00-port0` |
| DE10 programming/JTAG | `09fb:6010 Altera DE-SoC`; does not provide an HPS Linux serial login |

The HPS console was later unplugged; it need not appear during normal direct-UART inference. Device paths can change after reconnecting hardware.

```bash
cd /home/toyotateamaitb/igor_ws
lsusb
ls -l /dev/ttyTHS1 /dev/ttyACM0 /dev/lidar
ls -l /dev/serial/by-id/
python3 -c "from serial.tools import list_ports; print([(p.device,p.description,p.hwid) for p in list_ports.comports()])"
```

The LiDAR's custom `ttyCH341USB0` node may not appear in pyserial's standard port enumeration. Inspect its actual device node and symlink too. Only one process should own each serial connection.

## 4. Fixes that made communication and wheel movement succeed

| Problem found | Correction and resulting behavior |
|---|---|
| Wrong Ethernet interface assumed in old examples | Identified Jetson `enP8p1s0` and HPS `end0`; used their actual names |
| HPS configured for DHCP on a direct cable without a DHCP server | Added HPS `192.168.50.2/24`; Jetson uses `192.168.50.1/24`. Ping, SSH and UDP then worked |
| Wired addressing was not prepared for restart | Saved static addressing on HPS and enabled Jetson wired-profile autoconnect/never-default. Configuration was validated, but a reboot test was not performed |
| JTAG cable mistaken for the Linux console | Connected the separate DE10 USB-UART console; logged into HPS and inspected/configured it |
| UART wiring was initially wrong | Corrected crossed TX/RX and common ground; isolated Jetson loopback established that its UART/header worked |
| Board had previously used the 9600 image | User loaded the Parallel8 921600 image and host tests used matching baud |
| FPGA received no successful requests while LED1, LED3 and LED4 were on | Decoded this as reset released plus E-stop active/latched, fault code 1. Releasing KEY1 and resetting only KEY0 cleared it; valid replies then appeared |
| Active controller default baud still 9600 | Changed it to 921600 and exposed `fpga_baudrate`/`fpga_timeout` in launch |
| Launch endpoint used the old subnet | Updated Ethernet default to `udp://192.168.50.2:8080`; direct UART operation still requires explicit `fpga_port:=/dev/ttyTHS1` |
| Physical LiDAR path could fall back to synthetic scans | Hardware bringup now uses the installed SLAMTEC `rplidar_ros` driver; synthetic publishing is selected only by explicit mock mode |
| Actual driver reports approximately 359° coverage | Corrected overly strict full-scan validation while retaining range/timestamp checks; regression-tested against captured metadata |
| Scan resampling assumed a fixed angle origin | Controller now retains actual scan angle metadata |
| Missing/stale sensors could become a clear-space observation | Active controller now sends complete STOP instead |
| Missing physical STM32 could silently become mock | Physical initialization now fails instead; short serial writes are failures |
| Clock changes could affect freshness timing | Controller and MCU receive leases now use monotonic time |
| Residual output could retain movement despite zero nominal input | Zero nominal input forces zero output; post-compute freshness/output checks precede motor transmission |
| Recovery automatically reversed without a verified rear path | Recovery now holds zero wheel speeds |
| Shutdown did not reliably call driver cleanup | Controller destroys the node and closes hardware with STOP; route supervisor also sends independent final STOP packets |
| ROS planner interface not declared as a dependency | Added `waypoint_action` to `igor_controller` |
| Standalone connection bundle differed from source assets | Regenerated `tools/de10_connect.py`; connection regressions pass |
| Network helper assumed `eth0`/old subnet and hid errors | Updated interface selection/address defaults and error reporting |

### The decisive FPGA reset procedure

1. Program the correct Parallel8 image.
2. Leave **KEY1 fully released**.
3. Press and release **only KEY0**.
4. Before sending requests, expect **LED1 on; LED3–LED7 off**.

For this RTL:

| LEDs | Meaning |
|---|---|
| LED7–LED4 | Four-bit error code |
| LED3 | E-stop active or latched |
| LED2 | Response-valid indication |
| LED1 | Reset released |
| LED0 | Valid/fresh residual permit; not a direct chassis motor-power permit |

LED1+LED3+LED4 means E-stop fault 1. KEY1 latches the stop; simply releasing it does not clear the latch. Reset with KEY0 while KEY1 remains released. During FPGA-controller operation, an inference fault causes the host to stop; KEY1 is not a physical chassis power disconnect.

### Bitstream warning specific to this checkout

The checked-out `fpga/bitstreams/igor_src_policy_parallel8.sof` is a **132-byte Git LFS pointer**, not the programmable object. Obtain the real LFS object on the Quartus machine before programming:

- Real object size: **6,690,394 bytes**.
- Expected SHA256: `cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49`.

Quartus and git-lfs were not installed on this Jetson. Programming was performed by the user. Inspect the detected JTAG chain in Quartus; do not assume fixed HPS/FPGA chain indices. A KEY0 reset does not load a different image. After a power cycle or HPS boot flow that reloads fabric, confirm the intended image again.

## 5. Build and prepare each terminal

Known working environment: Jetson AArch64, Ubuntu/ROS 2 Humble, Python 3.10, NumPy, pyserial, colcon, and installed `rplidar_ros`.

For a normal workspace build:

```bash
cd /home/toyotateamaitb/igor_ws
source /opt/ros/humble/setup.bash
colcon build --base-paths src waypoint_list --packages-up-to igor_bringup igor_controller
source install/setup.bash
ros2 launch igor_bringup bringup.launch.py --show-args
```

In each subsequent ROS terminal:

```bash
cd /home/toyotateamaitb/igor_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
```

This session instead built under `/tmp/igor-uart-build`, `/tmp/igor-uart-install`, and `/tmp/igor-uart-build-logs`. To use that existing session build, substitute:

```bash
source /opt/ros/humble/setup.bash
source /tmp/igor-uart-install/setup.bash
```

The `/tmp` build may disappear after reboot. Source one intended overlay so stale installed code does not shadow the current source. The session user already had `dialout` access; another account may need device-group permissions.

## 6. Test FPGA inference without moving the wheels

Stop other FPGA serial clients first. With correct wiring, Parallel8 loaded, and the E-stop latch cleared:

```bash
python3 src/igor_pipeline/scripts/uart_test.py --self-check --baud 921600
python3 src/igor_pipeline/scripts/uart_test.py \
  --port /dev/ttyTHS1 --baud 921600 --iter 50 --timeout 1
```

Expected fixed-input result:

```text
Q8.8 = [-46, 60, 34]
Float residuals = [-0.1796875, 0.234375, 0.1328125]
Reply = 5a a5 02 06 d2 ff 3c 00 22 00 61
Validation passed: 50/50
```

For a preserved capture, use a new filename:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
python3 src/igor_pipeline/scripts/uart_test.py \
  --port /dev/ttyTHS1 --baud 921600 --iter 50 --timeout 1 \
  --jsonl "docs/ethernet_validation/fpga_uart_${RUN_TAG}.jsonl"
```

### Isolate Jetson UART if no bytes return

Disconnect **both FPGA signal wires** first, then jumper **Jetson pin 8 to pin 10**:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
python3 tools/uart_diagnose.py --port /dev/ttyTHS1 --mode loopback \
  --seconds 1 --output "docs/ethernet_validation/loopback_${RUN_TAG}.json"
```

Expected: exact 512-byte PASS at both 115200 and 921600. Remove the jumper and restore the crossed FPGA wiring before running inference again. Never join the lines while both boards' TX outputs remain connected.

## 7. Test individual wheels, pairs, and all four

The wheel-test tool sends motor packets directly to STM32; it does not call the FPGA. These commands send nonzero motor speeds. Secure the robot with all four wheels lifted and clear. Close other STM32 owners, including the main controller. The script validates the observed STM32 USB identity before sending commands.

First inspect the plan without opening serial:

```bash
python3 tools/test_jetauto_wheels.py --groups singles pairs four \
  --output /tmp/igor_wheel_dry_run.json
```

Run all groups:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
python3 tools/test_jetauto_wheels.py --groups singles pairs four \
  --run --wheels-raised --rps 0.5 --seconds 0.75 \
  --output "docs/ethernet_validation/wheel_groups_${RUN_TAG}.json"
```

For only individual wheels, use `--groups singles`; for only all pairs, use `--groups pairs`; for all four together, use `--groups four`.

| Order | Wheels selected |
|---|---|
| 1–4 | M1 front-left; M2 rear-left; M3 front-right; M4 rear-right |
| 5 | M1 + M2 |
| 6 | M1 + M3 |
| 7 | M1 + M4 |
| 8 | M2 + M3 |
| 9 | M2 + M4 |
| 10 | M3 + M4 |
| 11 | M1 + M2 + M3 + M4 |

At the tested 0.5 RPS, active left motors receive +0.5 and active right motors −0.5 because of the mirrored mounting. Each group is followed by repeated STOP packets and a pause. Ctrl+C triggers cleanup and STOP. The completed 11-group session was physically confirmed by the user; future runs still need observation of actual movement and stopping.

## 8. Test LiDAR and the complete pipeline while stationary

Place the robot in its normal driving orientation with a horizontal scan plane. In this session, an incorrect upright/vertical placement made LiDAR see the floor as a nearby wall. Also clear people, supports, cables, and nearby objects from the scan plane.

Inspect close returns without opening the chassis controller:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
ROS_LOG_DIR=/tmp/igor-lidar-check python3 tools/inspect_lidar_clearance.py \
  --output "docs/ethernet_validation/lidar_clearance_${RUN_TAG}.json"
```

This starts and stops the installed LiDAR driver. It reports distances and angles; it does not send wheel commands. Angles are relative to the configured LiDAR axis, which must be aligned/verified against the chassis before interpreting them as robot directions.

Run the complete **zero-command preflight**, without `--run`:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
ROS_LOG_DIR=/tmp/igor-preflight python3 tools/run_timed_rectangle.py \
  --output-dir "docs/ethernet_validation/preflight_${RUN_TAG}"
```

The supervisor starts real LiDAR, the FPGA-enabled controller, and STM32. It publishes zero velocity for about ten seconds, checks diagnostics and clearance, shuts down the children, and independently sends final STOP packets. No other hardware controller/serial client should be running.

A passing preflight requires real scans, multiple healthy calibrated hardware diagnostics, zero safe velocities, live hardware processes, and minimum recent clearance **greater than 0.45 m**. Startup sensor faults can occur before the first scan; persistent faults need investigation.

Read the new output directory:

- `result.json`: preflight result, fault counts, zero-command check, final STOP result.
- `lidar.log` and `controller.log`: hardware/node logs.

### Sensor-age configuration

The bringup default receive-freshness lease remains **25 ms**. Captured scan intervals were about **74 ms**, so the supervised low-speed rectangle/preflight tool explicitly uses a **150 ms** receive-freshness lease. Scan message timestamps are validated separately; this is not a hard 150 ms acquisition-to-actuation guarantee. IMU updates were much faster. The 150 ms value is a test configuration based on observed scan timing, not a general robot stopping-distance certification. It retains stale-data STOP checks. The helper does not bypass collision boundaries or fabricate scans.

## 9. Operate the FPGA-enabled controller manually

Use this instead of the supervisor when an interactive hardware bringup is needed:

```bash
ros2 launch igor_bringup bringup.launch.py \
  algorithm:=cl_drl_cbf use_fpga:=true \
  fpga_port:=/dev/ttyTHS1 fpga_baudrate:=921600 fpga_timeout:=0.02 \
  sensor_freshness_timeout_ms:=150.0 \
  mcu_port:=/dev/ttyACM0 lidar_port:=/dev/lidar \
  use_mock_serial:=false launch_planner:=false
```

The command opens the chassis driver. Keep the robot restrained/clear for initial checks, and use a clear supervised area for any movement. Without a fresh nonzero command, output must remain zero.

In another prepared ROS terminal:

```bash
ros2 topic echo /igor/diagnostics
ros2 topic echo /igor/cmd_vel_safe
ros2 topic echo /igor/safety_gate_alert
ros2 topic hz /scan
```

Successful diagnostics include `fpga: true`, `mock: false`, and `safety_permit: true`. Fault diagnostics include a reason and zero wheel setpoints. These fields are software state, not independent motor acknowledgments.

The controller accepts both `/cmd_vel_in` and `/cmd_vel`. Use only one active movement-command source. Do not start a route and teleop simultaneously.

## 10. Run the requested 5 m × 4 m route

This is a rectangle, with the **first side 5 m** and each corner turning left:

```text
Start (0,0), heading 0°
    → 5 m → (5,0)
    left 90°
    → 4 m → (5,4)
    left 90°
    → 5 m → (0,4)
    left 90°
    → 4 m → (0,0)
    left 90° → initial heading
```

### A. Implemented no-localization version

The user explicitly requested operation without localization. `timed_rectangle` estimates travel by integrating the controller's **executed velocity commands**; it does not measure wheel travel or position. It does not accumulate distance while the controller reports zero. Slip, motor calibration, steering corrections, and latency can change real distance and final heading.

Defaults: 0.20 m/s straight, +0.30 rad/s at corners, zero intervals of 0.5 seconds between stages. Ideal nominal motion is about 111 seconds plus pauses. Actual dimensions are estimates, not guaranteed 5 m × 4 m measurements.

After a successful stationary preflight, put all wheels on the floor, point the robot along the first 5 m side, clear the whole route and stopping space, and supervise with an immediate physical stop available. Stop all existing hardware nodes before using the supervisor, since it starts its own:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
ROS_LOG_DIR=/tmp/igor-rectangle python3 tools/run_timed_rectangle.py \
  --run --floor-ready \
  --output-dir "docs/ethernet_validation/rectangle_${RUN_TAG}"
```

The tool first repeats the stationary preflight. Only a passing result starts movement. It stops on stale sensors/controller output, close obstacles, unexpected reverse/lateral/right-turn commands, scheduling gaps, segment deadlines, total deadline, hardware-node exit, or interruption.

Logs also contain `route.log` and `route.jsonl` once the route starts. `done: true` means the command-estimated stages completed; it is not a measured-position acceptance result.

**Latest physical attempt:** preflight rejected 0.284 m clearance. All safe commands stayed zero; final STOP was sent. Follow-up returns were about 0.294 m at +80° and 0.408 m at −121°. No completed floor rectangle was recorded. The subsequent request to bypass the boundary around people was not implemented; obstacle stopping remains enabled.

### B. Measured-pose version for later localization

`rectangle_route` requires a fresh measured `geometry_msgs/PoseStamped` topic. Its path is relative to the starting pose, with four left quarter-turns and return to the starting heading. It checks pose freshness/frame changes, path deviation, scan clearance, controller diagnostics, and timeouts.

The existing `waypoint_server/motion_node.py` integrates commands for visualization; it is not a measured localization source. No suitable physical localization source was available in this session.

With a real measured `/pose` source and the hardware controller running separately:

```bash
# Starts disarmed; does not command motion.
ros2 launch igor_bringup rectangle_route.launch.py

# Future measured-localization run, only after validating that source:
ros2 launch igor_bringup rectangle_route.launch.py \
  armed:=true measured_pose_confirmed:=true pose_topic:=/pose
```

Do not run the measured and timed route publishers together. Configuration is in `src/igor_bringup/config/rectangle_5x4_left.yaml`.

## 11. Stop and recover

- Use **Ctrl+C in the route supervisor terminal**. Cleanup stops its command publisher, publishes zeros, closes the controller, and sends independent final STOP packets.
- Stop other teleop/route publishers too. A one-off zero message can be overwritten by another active movement publisher.
- With all movement publishers stopped and the controller still running, an explicit zero is:

```bash
ros2 topic pub --once /cmd_vel_in geometry_msgs/msg/Twist '{}'
```

- For an FPGA E-stop/fault: stop the host process, release KEY1, reset only KEY0, and create a new client/controller instance. Transport errors can latch the client; do not reuse a failed instance and assume it recovered.
- Check the report for `final_stop_sent: true` or `final_stop_error`. Serial STOP cannot protect against every Jetson crash, USB/power loss, stuck controller, or hardware fault. Provide an accessible physical chassis stop for floor tests.

## 12. Ethernet setup and its separate AI limitation

Current addresses:

| Board | Interface | Address |
|---|---|---|
| Jetson | `enP8p1s0` | `192.168.50.1/24` |
| DE10 HPS Linux | `end0` | `192.168.50.2/24` |

```bash
ip -br addr show enP8p1s0
ip route get 192.168.50.2
ping -I enP8p1s0 -c 3 192.168.50.2
ssh fpga@192.168.50.2
```

Authenticate interactively. Passwords are intentionally not recorded here.

If temporary Jetson addressing is needed, the helper configures an address without flushing unrelated addresses/routes:

```bash
bash src/igor_pipeline/scripts/setup_network_hardware.sh enP8p1s0 192.168.50.1/24
```

On HPS, temporary configuration is:

```bash
sudo ip link set dev end0 up
sudo ip address replace 192.168.50.2/24 dev end0
```

Persisted during the session:

- Jetson NetworkManager profile `enP8p1s0`: manual address, autoconnect=yes, never-default=yes; Wi-Fi retains the default route.
- HPS `/etc/network/interfaces.d/end0`: static address without a gateway.
- Original HPS configuration backed up at `/etc/network/end0.before-igor`.

### Network-only UDP test

On HPS, using the deployed workspace:

```bash
cd /home/fpga/igor_ws
python3 src/igor_pipeline/hps_de10/de10_udp_gateway.py \
  --bind 192.168.50.2 --backend mock --allow-client 192.168.50.1
```

On Jetson:

```bash
python3 src/igor_pipeline/scripts/ethernet_test.py \
  --host 192.168.50.2 --network-only --iter 10
```

Expected: `NETWORK_ONLY PASS`, status 6. The same request without `--network-only` must fail against this backend. Stop this mock gateway when finished; it is not a production AI service.

### What true Ethernet AI still requires

The supplied fabric image exposes UART, not a native HPS memory-mapped accelerator bridge. The existing HPS gateway expects a **separate HPS-local USB-to-3.3 V TTL UART adapter** wired to FPGA JP1. Direct Jetson-to-JP1 wires do not create that HPS connection. Never connect two TX drivers to FPGA RX simultaneously.

The running HPS kernel was `6.12.100-armv7-fpga`; `CONFIG_USB_SERIAL` and `CONFIG_USB_ACM` were disabled, with no matching kernel build resources installed. That gateway approach therefore needs both its adapter connection and a compatible kernel/driver. Pyserial 3.5 was installed in `/home/fpga/igor_ws/.venv`; the generic connection script invokes system Python, so hardware deployment must also select an interpreter with pyserial.

A native HPS/fabric bridge would instead require a matching FPGA/Platform Designer project, ABI, boot handoff, and driver. Neither approach was completed in this session. See [eth_direction.md](eth_direction.md) for details. Do not use old daemon `--hw`/`--mock` or `/dev/mem` DDR instructions as a working native accelerator path.

## 13. Software regression commands

These tests do not move hardware. Localhost UDP tests require socket permissions:

```bash
python3 -m unittest discover -s test -p test_rectangle_route.py
python3 -m unittest discover -s test -p test_ethernet.py
python3 -m unittest discover -s test -p test_connect_de10.py
python3 -m unittest discover -s test -p 'test_uart*.py'
python3 fpga/verification/run_host_regression.py
```

Latest observed suite results:

| Suite | Passing tests |
|---|---:|
| New route/active-source sensor/MCU checks | 13 |
| Ethernet protocol/gateway | 16 |
| Connection automation/standalone bundle | 18 |
| UART fixtures | 14 |
| Packaged host/controller regression | 29 |

The host regression targets `fpga/software_integration/src`; it is distinct from the active workspace controller. New source-guard tests explicitly cover the active controller/MCU changes. Pure path simulation is software evidence, not physical route completion. Packet CRCs are integrity checks, not authentication or proof of safe navigation.

## 14. Files and evidence

| File | Purpose |
|---|---|
| `src/igor_controller/igor_controller/fpga_bridge.py` | Real UART/UDP accelerator client |
| `src/igor_controller/igor_controller/mcu_driver.py` | STM32 motor TX and IMU RX |
| `src/igor_controller/igor_controller/controller_node.py` | Observation, inference, filtering, STOP gates, motor kinematics |
| `src/igor_bringup/launch/bringup.launch.py` | Hardware/mock launch selection and exposed transport settings |
| `tools/test_jetauto_wheels.py` | Singles, six pairs, all-four tests; dry-run default |
| `tools/inspect_lidar_clearance.py` | Physical clearance diagnostics without chassis commands |
| `tools/run_timed_rectangle.py` | Zero-command preflight, optional timed mission, cleanup and final STOP |
| `timed_rectangle_path.py`, `timed_rectangle_node.py` in the controller package | No-localization command-estimated rectangle |
| `rectangle_path.py`, `rectangle_route_node.py` in the controller package | Measured-pose rectangle for a future localization source |
| `test/test_rectangle_route.py` | Route and active-source safety/transport regression |

Physical evidence:

- [98-request FPGA inference capture](docs/ethernet_validation/jetson_fpga_bridge_20261018_acceptance.jsonl)
- [FPGA latency summary](docs/ethernet_validation/jetson_fpga_bridge_20261018_summary.json)
- [Ethernet network-only capture](docs/ethernet_validation/jetson_hps_network_20261018.jsonl)
- [Jetson UART loopback](docs/ethernet_validation/jetson_loopback_20261018_run1.json)
- [STM32/IMU capture summary](docs/ethernet_validation/jetauto_stm32_telemetry_20261018.json)
- [LiDAR capture](docs/ethernet_validation/jetauto_lidar_20261018_run1.json)
- [All 11 wheel groups, user-confirmed](docs/ethernet_validation/jetauto_wheel_groups_20261018_run1.json)
- [Latest motion-requested preflight result](docs/ethernet_validation/jetauto_rectangle_20261018_run1/result.json)
- [Close-return diagnostic](docs/ethernet_validation/jetauto_clearance_20261018_run1.json)

Further detail: [diagnosis history](docs/jetson_de10_diagnosis.md), [rectangle test report](docs/jetauto_rectangle_test.md), and [direct UART runbook](docs/direct_uart_runbook.md). This final guide records later results that supersede intermediate statements in those historical reports.

Documentation validation: all local evidence links resolved, all 22 Bash code blocks passed shell syntax parsing, and the no-hardware protocol self-check and documented tool help options were checked. No motors or hardware route were started while writing this guide.
