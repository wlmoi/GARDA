# Verified Jetson GPIO → FPGA inference

On 2026-10-18, production FPGABridge passed 98/98 real FPGA requests at
921600 baud, matching all expected fixed-point outputs. Mean RTT 4.594 ms,
max 5.920 ms. Ethernet to HPS separately passed 10/10 network-only requests.
See [full diagnosis](jetson_de10_diagnosis.md).

## Wiring and reset

| Jetson header | FPGA DE10 JP1 |
|---|---|
| pin 8 TX | pin 1 RX |
| pin 10 RX | pin 2 TX |
| pin 9 GND | pin 12 GND |

Use 3.3 V signals. Remove the temporary Jetson pin 8–10 loopback jumper.
Program the **Parallel8 921600** image. With KEY1 released, press/release
**only KEY0**. Expected idle: LED1 on, LED3–LED7 off. KEY1 is E-stop and
latches until KEY0 reset; LED3+LED4 means stop_active plus E-stop fault 1.
Do not disable that guard to obtain replies.

## Repeat the inference test, without motors

```bash
cd /home/toyotateamaitb/igor_ws
python3 src/igor_pipeline/scripts/uart_test.py --port /dev/ttyTHS1 --baud 921600 --iter 50 --timeout 1
```

Expected: 50/50, raw Q8.8 [-46,60,34], CRC-valid 11-byte replies.
Only one process may own ttyTHS1.

## Build and inspect the ROS launch

The session build/install is under /tmp and may disappear after reboot:

```bash
source /opt/ros/humble/setup.bash
source /tmp/igor-uart-install/setup.bash
ros2 launch igor_bringup bringup.launch.py --show-args
```

To make a normal workspace build instead:

```bash
source /opt/ros/humble/setup.bash
colcon build --base-paths src waypoint_list --packages-up-to igor_bringup igor_controller
source install/setup.bash
```

Bringup now exposes fpga_baudrate and fpga_timeout. The declared
waypoint_action dependency ensures the planner's action interface is built.

## Full hardware launch, after sensors/STM32 are connected

This command starts the motor driver. It has not been executed in this session.
First verify device paths, restrain/lift the robot, clear the FPGA E-stop latch,
and complete sensor/STOP acceptance before sending movement commands.

```bash
ros2 launch igor_bringup bringup.launch.py \
  algorithm:=cl_drl_cbf use_fpga:=true \
  fpga_port:=/dev/ttyTHS1 fpga_baudrate:=921600 fpga_timeout:=0.02 \
  mcu_port:=/dev/ttyACM0 lidar_port:=/dev/lidar \
  use_mock_serial:=false launch_planner:=false
```

The 20 ms inference deadline matches the target control period; test under
actual system load before claiming 50 Hz operation. Existing freshness and
fault STOP checks remain enabled. A 10 Hz LiDAR does not continuously satisfy
a 25 ms freshness lease; the physical sensor/control contract requires review
and testing rather than weakening the lease to force motion.

This direct UART route sends 74 processed observation features and receives
three AI residuals. Jetson performs filtering, kinematics and STM32 commands.
It does not send full raw scans to FPGA or run AI over Ethernet.

For Ethernet AI, HPS still needs a connection to fabric (the implemented
gateway uses a separate HPS-local USB-UART adapter and matching kernel driver).
Do not point production ROS at the network-only mock backend.
