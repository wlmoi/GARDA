> **Current Ethernet setup:** follow [eth_direction.md](eth_direction.md) and
> [connection instructions](docs/connect_de10.md). The supported endpoint is
> `udp://192.168.50.2:8080`, with Jetson `192.168.50.1/24` on its actual wired
> interface (`enP8p1s0` on this Jetson). Older examples below using
> `192.168.1.50`, daemon `--hw`/`--mock`, or an HPS DDR/DMA bridge are obsolete.
> The deployed path requires HPS Linux plus an HPS-local USB-to-3.3 V UART
> adapter to the FPGA. Programming a SOF alone does not start Ethernet.
> See [Jetson diagnostic results](docs/jetson_de10_diagnosis.md).

# Project IGOR: Jetson Orin Nano <-> DE10-Nano FPGA Acceleration Pipeline Documentation (`pipeline_docs.md`)

This document provides complete technical documentation for the implementation of the **Gigabit Ethernet & Serial AI Acceleration Pipeline** described in [`pipeline_plan.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/pipeline_plan.md), [`pipeline_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/pipeline_architecture.md), and [`global_planner_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/global_planner_architecture.md).

---

## 1. System Overview & Technical Ground Truth

The acceleration pipeline offloads the **74-128-64-3 PPO Gated Residual policy** from the **NVIDIA Jetson Orin Nano** host controller to the **Intel Cyclone V SoC DE10-Nano FPGA** over high-speed Gigabit Ethernet UDP (port 8080) with automatic UART serial fallback.

### Ground Truth Parameters:
- **Observation Input**: 74 elements ($64\text{ frontal LiDAR} + 6\text{ IMU }(a_x, a_y, a_z, \omega_x, \omega_y, \omega_z) + 3\text{ nominal twist }(v_x, v_y, \omega) + 1\text{ Course-Lock heading error } \Delta\theta$).
- **Quantization**: Signed fixed-point **Q8.8** ($x_{\text{int}} = \text{round}(x \times 256.0)$).
- **Inference Output**: 3 delta actions ($[\Delta v_x, \Delta v_y, \Delta \omega_z]$ clamped in $[-1.0, 1.0]$).
- **PL Acceleration Core**: `igor_src_policy_core.v` (74 $\to$ 128 (ReLU) $\to$ 64 (ReLU) $\to$ 3 MLP) using 18,051 int16 quantized parameters from `policy_weights.mem`.
- **Global Planner Integration**: Lookahead carrot tracking from `WaypointGlobalPlannerNode` feeds nominal body velocity commands and heading difference into the 74-D observation vector, which is safety-checked and streamed to the DE10-Nano.

---

## 2. Hardware Wiring & Physical Interconnection Guide

To deploy the full hardware pipeline on the physical JetAuto robot, follow the wiring scheme below connecting the **Jetson Orin Nano**, the **DE10-Nano Cyclone V FPGA**, the **STM32 Sub-Controller**, and the **Slamtec RPLiDAR A1/A2**:

```
+---------------------------------------------------------------------------------------+
|                                    PHYSICAL WIRING                                    |
|                                                                                       |
|   +-----------------------+     Gigabit Ethernet (RJ45 Cat6)   +--------------------+ |
|   |                       | <================================> |                    | |
|   |   Jetson Orin Nano    |      Static IP: 192.168.1.10/24    | DE10-Nano SoC FPGA | |
|   |   (Master Controller) |      Target IP: 192.168.1.50:8080  | (AI Accelerator)   | |
|   |                       |                                    |                    | |
|   |                       | --- UART Fallback (Header JP1) --- | (GPIO 0 / JP1)     | |
|   |   Pin 8  (UART TXD)   | ---------------------------------> | GPIO_0[0] (RX)     | |
|   |   Pin 10 (UART RXD)   | <--------------------------------- | GPIO_0[1] (TX)     | |
|   |   Pin 9  (GND)        | ---------------------------------- | GND (Pin 12)       | |
|   +-----------------------+                                    +--------------------+ |
|         |          |                                                                  |
|         | USB      | USB                                                              |
|         v          v                                                                  |
|   +-----------+  +-------------------+                                                |
|   | RPLiDAR   |  | STM32 JetAuto MCU |                                                |
|   | /dev/lidar|  | /dev/ttyACM0      |                                                |
|   | (115.2k)  |  | (1,000,000 bps)   |                                                |
|   +-----------+  +-------------------+                                                |
|                            | 4x Motor Signals                                         |
|                            v                                                          |
|                  [M1:FL, M2:RL, M3:FR, M4:RR]                                         |
+---------------------------------------------------------------------------------------+
```

### Detailed Pin & Connector Connections:
1. **Gigabit Ethernet Connection (Primary Fast Link)**:
   - Connect a standard Cat5e/Cat6 RJ45 patch cable directly between the Jetson Orin Nano Gigabit Ethernet port and the DE10-Nano RJ45 port.
   - Jetson Ethernet IP: `192.168.1.10/24` (Subnet `255.255.255.0`).
   - DE10-Nano HPS Linux IP: `192.168.1.50/24` (Port: `8080`).
2. **UART Serial Connection (Fallback Link & Monitoring)**:
   - If utilizing UART instead of Ethernet:
     - **Jetson Pin 8 (UART2 TXD)** $\to$ **DE10-Nano GPIO_0[0] (Pin 1 on JP1 header)**.
     - **Jetson Pin 10 (UART2 RXD)** $\to$ **DE10-Nano GPIO_0[1] (Pin 2 on JP1 header)**.
     - **Jetson Pin 9 / 14 (GND)** $\to$ **DE10-Nano Ground (Pin 12 on JP1 header)**.
     - Baud rate: `115200` or `921600` bps.
3. **STM32 Motor & IMU Link**:
   - Micro-USB cable from Jetson USB 3.0 port to the JetAuto STM32 chassis controller USB port (`/dev/ttyACM0` @ 1,000,000 bps).
   - Transmits 4-wheel Mecanum RPS speed commands (Func `0x03`) and receives 6-DOF MPU-6050 IMU telemetry (Func `0x07`).
4. **LiDAR Link**:
   - USB cable from RPLiDAR A1/A2 adapter to Jetson USB port (`/dev/lidar` or `/dev/ttyUSB0` @ 115200 bps).

---

## 3. Implemented Components & File Mapping

```
src/igor_pipeline/
├── protocol/
│   ├── protocol_legacy.h             # Legacy baseline struct (Read-Only)
│   └── protocol_v2.h                 # Compact 74-D/3-D struct with Q8.8 & CRC-32
├── hps_de10/
│   ├── de10_driver_legacy.h          # Legacy driver header (Read-Only)
│   ├── de10_server_legacy.c          # Legacy server implementation (Read-Only)
│   ├── de10_shared_mem_ext.h         # Dual-mode HAL header (Mock & Physical Hardware)
│   ├── de10_shared_mem_ext.c         # HAL implementation (mmap /dev/mem or heap buffers)
│   ├── de10_server_daemon.c          # Production HPS server daemon (--mock / --hw)
│   └── Makefile                      # Build script for de10_server_daemon
├── simulators/
│   ├── mock_de10_host_server.cpp     # Standalone C++ offline simulator
│   └── CMakeLists.txt                # Build configuration for simulator
├── jetson_orin/
│   ├── jetson_client_legacy.cpp      # Legacy streamer client (Read-Only)
│   ├── jetson_client_adapter.hpp     # Production C++ streamer API
│   ├── jetson_client_adapter.cpp     # Low-latency UDP socket streamer implementation
│   ├── jetson_main.cpp               # Client benchmark & verification CLI tool
│   └── CMakeLists.txt                # Build configuration for client streamer
├── fpga_pl/
│   └── ai_accel_wrapper.v            # Avalon-MM Slave / DMA Master Verilog PL wrapper
└── scripts/
    ├── test_local_loopback.sh        # Stage 1 offline loopback automation test
    ├── setup_network_hardware.sh     # Stage 2 network configuration utility
    └── benchmark_latency.py          # Latency & jitter statistical profiler
```

---

## 4. Detailed Component Architecture & Function Calls

### 4.1 Extended Protocol (`protocol_v2.h`)
- **`SensorPacketV2`**: Packed struct transmitting:
  - `uint32_t magic` (`0x49474F52` = `"IGOR"`)
  - `uint32_t frame_id`
  - `uint64_t timestamp_ns` (monotonic high-resolution timestamp)
  - `float linear_velocity[3]`, `float angular_velocity[3]`
  - `uint32_t sensor_data_len` (`74`)
  - `float sensor_data[74]`
  - `int16_t q8_8_data[74]` (pre-quantized fixed-point array)
  - `uint32_t crc32`
- **`InferenceResponsePacketV2`**: Packed struct returning:
  - `uint32_t magic` (`0x49474F52`)
  - `uint32_t frame_id`, `uint64_t timestamp_ns` (echoed for RTT)
  - `uint32_t status_code`, `uint32_t num_outputs` (`3`)
  - `float ai_results[3]`, `int16_t q8_8_results[3]`
  - `uint32_t execution_cycles`, `uint32_t crc32`

### 4.2 Dual-Mode Memory HAL (`de10_shared_mem_ext.c`)
- **`hal_init(SoC_HAL_Context *ctx, int is_mock)`**:
  - `is_mock == 0`: Maps `/dev/mem` for lightweight bridge (`0xFF200000`, span 2MB) and shared SDRAM (`0x20000000`, span 16MB).
  - `is_mock == 1`: Allocates virtual aligned heap buffers, preventing segmentation faults when testing on non-FPGA hosts.
- **Double-Buffering Ping-Pong**:
  - Configures `in_buf_ping` (0x000000), `out_buf_ping` (0x400000), `in_buf_pong` (0x800000), `out_buf_pong` (0xC00000) in shared DDR.
- **`hal_trigger_inference(SoC_HAL_Context *ctx, int bank, uint32_t len, uint32_t timeout_us)`**:
  - Pulses start bit (`*accel_ctrl = 0x01`).
  - Monitors `*accel_status` done bit with a 20 ms timeout watchdog.

---

## 5. How to Test Connection & Run Full Pipeline (End-to-End)

Follow this complete step-by-step procedure to test connectivity, run the bringup stack, send global planner waypoint routes, stream AI observations to the FPGA, receive delta actions, and drive the Mecanum chassis.

### Step 1: Verify Hardware Network Connection
On the Jetson Orin Nano, configure the Ethernet interface and verify connectivity with the DE10-Nano:
```bash
# 1. Configure Jetson IP address
sudo ip addr add 192.168.1.10/24 dev eth0 || true
sudo ip link set eth0 up

# 2. Ping DE10-Nano to verify physical cable link
ping -c 3 192.168.1.50
```

### Step 2: Test Low-Level FPGA Streaming Connection
Test UDP packet transmission and verify Round-Trip Time (RTT) before launching ROS 2:
```bash
# Target live DE10-Nano hardware (or use 127.0.0.1 for mock testing)
python3 src/igor_pipeline/scripts/benchmark_latency.py 192.168.1.50 8080
```
Expected output:
```text
Total Sent: 200, Total Received: 200, Packet Loss Rate: 0.00%
Mean RTT: ~2.0 ms
```

### Step 3: Launch DE10 Server Daemon
- **On Physical DE10-Nano (via SSH / Serial Console)**:
  ```bash
  cd ~/igor_pipeline/hps_de10
  sudo ./de10_server_daemon --hw --port 8080
  ```
- **On Local Jetson (Mock Verification Mode)**:
  ```bash
  ./src/igor_pipeline/hps_de10/de10_server_daemon --mock --port 8080
  ```

### Step 4: Launch Master Robot Bringup
Launch the entire system in a new terminal on the Jetson Orin Nano. This activates:
- RPLiDAR Driver (`/scan`)
- STM32 MCU Driver (`/dev/ttyACM0` for motor execution & IMU feedback)
- `IgorControllerNode` (Freshness gate, 0.1s predictive safety gate, FPGA UDP streamer)
- `WaypointGlobalPlannerNode` (Action Server `/waypoint`)

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

# For live hardware deployment:
ros2 launch igor_bringup bringup.launch.py \
    algorithm:=cl_drl_cbf \
    use_fpga:=true \
    fpga_port:="udp://192.168.1.50:8080" \
    mcu_port:=/dev/ttyACM0 \
    lidar_port:=/dev/lidar \
    use_mock_serial:=false \
    launch_planner:=true

# (Or for local software simulation without hardware):
ros2 launch igor_bringup bringup.launch.py \
    algorithm:=cl_drl_cbf \
    use_fpga:=true \
    fpga_port:="udp://127.0.0.1:8080" \
    use_mock_serial:=true \
    launch_lidar:=false \
    launch_planner:=true
```

### Step 5: Send Route Command to Global Planner
In another terminal, send the route goal to the global planner:
- **Option A: Send Single Goal via ROS 2 Action CLI**:
  ```bash
  source /opt/ros/humble/setup.bash
  source install/setup.bash
  ros2 action send_goal /waypoint waypoint_action/action/WaypointSet \
      "{absis: 5.0, ordinat: 0.0, yaw: 0.0, duration: 12.0}" --feedback
  ```
- **Option B: Run Autonomous Multi-Waypoint Sequence**:
  ```bash
  ros2 run waypoint_client waypoint_client_node
  ```
  And trigger the rectangle route by publishing the filename:
  ```bash
  ros2 topic pub --once /waypoint_filename std_msgs/msg/String "{data: 'demo_rectangle.yaml'}"
  ```

### Step 6: Monitor Execution & Diagnostics
Observe real-time telemetry, FPGA acceleration status, and motor RPS:
```bash
# Monitor controller diagnostics (5 Hz)
ros2 topic echo /igor/diagnostics

# Monitor safety gate alert status
ros2 topic echo /igor/safety_gate_alert

# Monitor real-time action feedback
ros2 topic echo /waypoint/_action/feedback
```
The execution will stream 74-D observation packets to the DE10-Nano over UDP, receive delta actions, evaluate the 0.1s safety gate, convert velocity to 4-wheel Mecanum RPS, and command the STM32 to drive the robot along the specified route.

---

## 6. Compilation & Execution Reference by Target Platform

Here is the exact checklist of source files, compile commands, and run commands required on each device:

### 6.1 Intel Cyclone V SoC DE10-Nano (FPGA + HPS Linux)

#### Files Required on DE10-Nano:
- `src/igor_pipeline/protocol/protocol_v2.h`
- `src/igor_pipeline/hps_de10/de10_shared_mem_ext.h`
- `src/igor_pipeline/hps_de10/de10_shared_mem_ext.c`
- `src/igor_pipeline/hps_de10/de10_server_daemon.c`
- `src/igor_pipeline/hps_de10/Makefile`
- `fpga/bitstreams/igor_src_policy.sof` (or compiled from `ai_accel_wrapper.v` + `igor_src_policy_core.v`)

#### Compilation on DE10-Nano (ARMv7 Linux / Native GCC):
```bash
cd ~/igor_pipeline/hps_de10
make clean && make
```
*(Produces executable binary: `de10_server_daemon`)*.

#### Running on DE10-Nano:
1. **Program FPGA Bitstream** (via Quartus Programmer / JTAG or U-Boot / devcfg):
   ```bash
   # If using Linux devcfg:
   dd if=igor_src_policy.rbf of=/dev/fpga0 bs=1M
   ```
2. **Run Server Daemon in Hardware Mode**:
   ```bash
   cd ~/igor_pipeline/hps_de10
   sudo ./de10_server_daemon --hw --port 8080
   ```
   *(Or with `--mock` if running without physical FPGA bitstream programmed)*.

---

### 6.2 NVIDIA Jetson Orin Nano (Master Robot Controller / Ubuntu 22.04 + ROS 2 Humble)

#### Files Required on Jetson Orin Nano:
- **ROS 2 Workspace Packages**:
  - `src/igor_bringup/` (`launch/bringup.launch.py`)
  - `src/igor_controller/` (`controller_node.py`, `waypoint_global_planner_node.py`, `fpga_bridge.py`, `mcu_driver.py`, `heading_estimator.py`)
  - `src/igor_navigation/` (Kinematics, Subsampler, CBF safety filters, weights)
  - `waypoint_list/waypoint_action/` (`WaypointSet.action`)
  - `waypoint_list/waypoint_client/` (`waypoint_Action_Client.py`, `point/demo_rectangle.yaml`)
- **Pipeline C++ Client & Test Tools**:
  - `src/igor_pipeline/protocol/protocol_v2.h`
  - `src/igor_pipeline/jetson_orin/jetson_client_adapter.hpp` & `.cpp`
  - `src/igor_pipeline/jetson_orin/jetson_main.cpp`
  - `src/igor_pipeline/scripts/benchmark_latency.py`
  - `test_global_planner_pipeline.py`

#### Compilation on Jetson Orin Nano:
1. **Build ROS 2 Navigation & Global Planner Packages**:
   ```bash
   cd ~/vs-code-data/Python/igor_ws
   source /opt/ros/humble/setup.bash
   
   # Build action interfaces and controller packages
   colcon build --packages-select waypoint_action
   source install/setup.bash
   colcon build --base-paths src waypoint_list --packages-select igor_navigation igor_controller igor_bringup waypoint_client
   ```
2. **Build C++ Jetson Streamer Client (Standalone verification)**:
   ```bash
   cd ~/vs-code-data/Python/igor_ws/src/igor_pipeline/jetson_orin
   mkdir -p build && cd build
   cmake .. && make
   ```
   *(Produces executable binary: `jetson_ai_streamer`)*.

#### Running on Jetson Orin Nano:
1. **Configure Ethernet Network Link**:
   ```bash
   sudo ip addr add 192.168.1.10/24 dev eth0 || true
   sudo ip link set eth0 up
   ```
2. **Run Standalone Connection Benchmark (Pre-Flight Check)**:
   ```bash
   python3 src/igor_pipeline/scripts/benchmark_latency.py 192.168.1.50 8080
   ```
3. **Launch Autonomous Robot Bringup**:
   ```bash
   source /opt/ros/humble/setup.bash
   source install/setup.bash
   ros2 launch igor_bringup bringup.launch.py \
       algorithm:=cl_drl_cbf \
       use_fpga:=true \
       fpga_port:="udp://192.168.1.50:8080" \
       mcu_port:=/dev/ttyACM0 \
       lidar_port:=/dev/lidar \
       use_mock_serial:=false \
       launch_planner:=true
   ```
4. **Trigger 3m x 5m Rectangle Demo Route**:
   ```bash
   # Terminal A: Start action client
   ros2 run waypoint_client waypoint_client_node
   
   # Terminal B: Dispatch rectangle YAML
   ros2 topic pub --once /waypoint_filename std_msgs/msg/String "{data: 'demo_rectangle.yaml'}"
   ```

