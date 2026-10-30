# Project IGOR: Global Planner & Safety Gate Architecture Documentation (`global_planner_docs.md`)

This document provides a comprehensive technical overview of the implementation completed for **Phase 1 through Phase 3** of [`global_planner_plan.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/global_planner_plan.md), satisfying all requirements from [`global_planner_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/global_planner_architecture.md), [`pipeline_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/pipeline_architecture.md), and [`teleop_mecanum.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/teleop_mecanum.py).

---

## 1. System Architecture & Features Implemented

```
+---------------------------------------------------------------------------------------------+
|                                    ROS 2 MISSION LAYER                                      |
|  +-----------------------------+               +-----------------------------------------+  |
|  | Waypoint Client             |  Action Goal  | WaypointGlobalPlannerNode               |  |
|  | (YAML List / Aruco / Manual)| ------------> | (Action Server: WaypointSet.action)     |  |
|  +-----------------------------+               +-----------------------------------------+  |
+-------------------------------------------------------------|-------------------------------+
                                                              | Lookahead Carrot & Path
                                                              v
+---------------------------------------------------------------------------------------------+
|                                JETSON ORIN NANO SAFETY GATE                                 |
|  +---------------------------------------------------------------------------------------+  |
|  | 1. Sensor Freshness Filter: Discards IMU/LiDAR older than 25 ms (20-30 ms threshold)   |  |
|  | 2. Lookahead Carrot Tracker: Generates nominal (cmd_vx, cmd_vy, cmd_omega, delta_theta)|  |
|  | 3. Safety Gate Forward Predictor: 0.1s kinematic projection vs 15cm obstacle boundary  |  |
|  | 4. Emergency Backoff Recovery FSM: Reverse 0.15 m/s for 0.1s -> resume inference       |  |
|  | 5. Dynamic Speed Parameters: Runtime speed scaling without waiting for keypresses     |  |
|  +---------------------------------------------------------------------------------------+  |
+------------------------------------|------------------------^-------------------------------+
                        Nominal Obs  |                        | AI Actions
                        (74-D Q8.8)  v                        | (3-D Q8.8)
+-------------------------------------------------------------|-------------------------------+
|                       ACCELERATION ENGINE (DUAL-MODE)                                       |
|  +---------------------------------------------------------------------------------------+  |
|  | Ethernet UDP (Port 8080) to DE10-Nano FPGA / UART / Local CPU fallback                 |  |
|  | 74-D Vector: 64 LiDAR + 6 IMU + 3 Twist + 1 Heading                                    |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
                                                              | Safe Blended Twist
                                                              v
+---------------------------------------------------------------------------------------------+
|                                    ACTUATION & LOW-LEVEL                                    |
|  +---------------------------------------------------------------------------------------+  |
|  | Mecanum Inverse Kinematics (Right-side sign mirror: FL: M1, RL: M2, FR: -M3, RR: -M4)   |  |
|  | STM32 Motor Driver: 4-wheel RPS packet (Func 0x03, 1 Mbps)                             |  |
|  | Hardware Watchdog: Implemented (HeartbeatWatchdog, dormant by default)                |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
```

### Key Features Implemented:
1. **Closed-Loop Waypoint Global Planner**:
   - Replaced open-loop duration sleeping with closed-loop pose feedback (`/pose` subscription from SLAM, odometry, or `motion_node`).
   - Compliant with `WaypointSet.action` (`absis`, `ordinat`, `yaw`, `duration`).
   - Supports both translational tracking and in-place pure rotational movements.
   - Publishes continuous real-time feedback (`absis_feedback`, `ordinat_feedback`, `yaw_feedback`, and `progress` string).
2. **Sensor Freshness Drop Gate (20–30 ms)**:
   - Tracks arrival timestamps for incoming RPLiDAR (`/scan`) and STM32 MPU-6050 IMU telemetry.
   - Evaluates sensor age against a 25 ms threshold (designed for the ~16 ms FPGA processing latency). Stale messages are dropped and logged to prevent lagging inferences.
3. **Jetson Orin Nano Predictive Safety Gate (0.1s Horizon / 15 cm Barrier)**:
   - Predicts 0.1s forward displacement based on candidate inference velocities.
   - If displacement enters the 15 cm obstacle zone in the directional motion cone:
     - Blocks FPGA inference inputs (stalls inference).
     - Commands an immediate stop followed by a 0.1s emergency reverse backoff at 0.15 m/s.
     - Automatically resets and resumes normal tracking once backoff is complete.
4. **Dual-Mode DE10-Nano FPGA Bridge (Ethernet UDP & UART)**:
   - Supports Gigabit Ethernet UDP streaming to DE10-Nano HPS (`192.168.1.50:8080` or `127.0.0.1:8080` for mock mode) and serial UART fallback.
   - Packets serialized in signed Q8.8 fixed-point format with CRC-32 checksum.
5. **Dynamic Runtime Speed Scaling**:
   - ROS 2 dynamic parameter callback (`_on_parameter_change`) enables updating `max_linear_x`, `max_linear_y`, `max_angular_z`, and `speed_scale` at runtime without keypress delays.
6. **Hardware Watchdog**:
   - `HardwareWatchdog` class is fully implemented and hooked into the command stream, configured dormant by default (`enable_watchdog:=false`).

---

## 2. File Directory & Function Call Workflow

| File | Primary Functions & Classes | Description |
|---|---|---|
| [`waypoint_global_planner_node.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_controller/igor_controller/waypoint_global_planner_node.py) | `WaypointGlobalPlannerNode`<br>`compute_closed_loop_twist()`<br>`execute_callback()`<br>`_pose_callback()` | ROS 2 Action Server for `WaypointSet`. Tracks robot pose, computes lookahead commands, and publishes to `/cmd_vel_in` and `/cmd_vel`. |
| [`controller_node.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_controller/igor_controller/controller_node.py) | `IgorControllerNode`<br>`_control_loop()`<br>`check_forward_collision_risk()`<br>`_on_parameter_change()`<br>`HardwareWatchdog` | Main 50 Hz controller. Enforces sensor freshness drop gate, predictive safety gate, 0.1s backoff recovery FSM, 74-D observation assembly, and Mecanum IK. |
| [`fpga_bridge.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_controller/igor_controller/fpga_bridge.py) | `FPGABridge`<br>`infer()`<br>`checksum_crc8()`<br>`compute_crc32()` | Communicates with Cyclone V DE10-Nano over Ethernet UDP port 8080 or UART serial, packing 74 Q8.8 inputs and receiving 3 Q8.8 actions. |
| [`bringup.launch.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_bringup/launch/bringup.launch.py) | `generate_launch_description()` | Master bringup launch file supporting single-command launch of RPLiDAR driver, Igor controller, and waypoint global planner. |
| [`demo_rectangle.yaml`](file:///home/hadynata/vs-code-data/Python/igor_ws/waypoint_list/waypoint_client/point/demo_rectangle.yaml) | Waypoint List | Mission route configuration for the 3m x 5m rectangular navigation demo. |

---

## 3. Dedicated Demo Case: 3m x 5m Rectangle Traversal

For the demo, the global planner executes a complete **3m x 5m rectangle trajectory**:
$$\text{Forward } (5\text{m}) \longrightarrow \text{Left } (90^\circ) \longrightarrow \text{Forward } (3\text{m}) \longrightarrow \text{Left } (90^\circ) \longrightarrow \text{Forward } (5\text{m}) \longrightarrow \text{Left } (90^\circ) \longrightarrow \text{Forward } (3\text{m})$$

### Rectangle Geometry & Coordinates:
- **Start Pose**: $(0.0, 0.0), \text{yaw} = 0^\circ$
- **Segment 1 (Side 1 = 5m)**: Move forward to $(5.0, 0.0)$, heading $0^\circ$.
- **Segment 2 (Turn 1)**: Rotate in-place to heading $90^\circ$ (pointing left / $+Y$).
- **Segment 3 (Side 2 = 3m)**: Move forward to $(5.0, 3.0)$, heading $90^\circ$.
- **Segment 4 (Turn 2)**: Rotate in-place to heading $180^\circ$ (pointing rear / $-X$).
- **Segment 5 (Side 3 = 5m)**: Move forward to $(0.0, 3.0)$, heading $180^\circ$.
- **Segment 6 (Turn 3)**: Rotate in-place to heading $-90^\circ / 270^\circ$ (pointing $-Y$).
- **Segment 7 (Side 4 = 3m)**: Move forward to $(0.0, 0.0)$, returning to origin with heading $0^\circ$.

The waypoints are defined in [`waypoint_list/waypoint_client/point/demo_rectangle.yaml`](file:///home/hadynata/vs-code-data/Python/igor_ws/waypoint_list/waypoint_client/point/demo_rectangle.yaml):
```yaml
waypoints:
  - x: 5.0
    y: 0.0
    yaw: 0.0
    duration: 12.0
  - x: 0.0
    y: 0.0
    yaw: 90.0
    duration: 3.0
  - x: 5.0
    y: 3.0
    yaw: 90.0
    duration: 8.0
  - x: 0.0
    y: 0.0
    yaw: 180.0
    duration: 3.0
  - x: 0.0
    y: 3.0
    yaw: 180.0
    duration: 12.0
  - x: 0.0
    y: 0.0
    yaw: -90.0
    duration: 3.0
  - x: 0.0
    y: 0.0
    yaw: 0.0
    duration: 8.0
```

---

## 4. How to Run the 3m x 5m Rectangle Demo

### Step 1: Start the Accelerator Daemon
- **On Physical DE10-Nano FPGA**:
  ```bash
  cd ~/igor_pipeline/hps_de10
  sudo ./de10_server_daemon --hw --port 8080
  ```
- **Or on Local Host (Simulation / Mock Mode)**:
  ```bash
  ./src/igor_pipeline/hps_de10/de10_server_daemon --mock --port 8080
  ```

### Step 2: Start Master Robot Bringup
In a separate terminal on the Jetson Orin Nano, launch the full navigation stack:
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
*(If running purely on a PC/laptop without physical hardware, set `use_mock_serial:=true`, `launch_lidar:=false`, and `fpga_port:="udp://127.0.0.1:8080"`)*.

### Step 3: Run the Waypoint Action Client
In a third terminal, start the waypoint client listener:
```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 run waypoint_client waypoint_client_node
```

### Step 4: Dispatch the 3m x 5m Rectangle Route
In a fourth terminal, publish the filename to trigger the route execution:
```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 topic pub --once /waypoint_filename std_msgs/msg/String "{data: 'demo_rectangle.yaml'}"
```

### Step 5: Visualizing and Monitoring in Rviz
To monitor the robot's pose trajectory, lookahead carrot tracking, and LiDAR obstacle field:
```bash
rviz2 -d waypoint_list/waypoint_server/rviz/waypoint_config.rviz
```

The robot will execute each segment sequentially:
1. Progressively drive forward 5 meters.
2. Rotate 90 degrees to face left.
3. Drive forward 3 meters.
4. Rotate 90 degrees to face rear.
5. Drive forward 5 meters.
6. Rotate 90 degrees to face start.
7. Drive forward 3 meters back to origin $(0.0, 0.0)$.
All motor commands are continuously validated by the 0.1s predictive safety gate and accelerated via DE10-Nano FPGA inference.
