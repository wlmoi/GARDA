# Global Planner Architecture & Implementation Plan: `global_planner_plan.md`

## 1. Executive Summary & Objective

The objective of this architecture and implementation plan is to design and integrate a **Robust Global Planner** for Project IGOR (Hiwonder JetAuto Mecanum AMR). The system incorporates:
1. **Global Goal/Waypoint Mission Management**: Based on ROS 2 Action Server/Client paradigm modeled after the reference in `waypoint_list/` (`waypoint_Action_Server`, `waypoint_Action_Client`, `WaypointSet.action`, and YAML sequence dispatcher).
2. **AI & FPGA Hardware Acceleration Integration**: Seamlessly feeding lookahead navigation commands to the 74-dimensional observation vector of the AI model (`64 LiDAR + 6 IMU + 3 Twist + 1 Heading`) running either on the Cyclone V DE10-Nano FPGA accelerator (via UDP over Gigabit Ethernet as specified in `pipeline_architecture.md` / `global_planner_architecture.md`, with fallback to serial/mock) or local CPU inference.
3. **Jetson Orin Nano Safety Gate & Active Recovery**: Implementing an obstacle-predictive safety gate that:
   - Evaluates a 0.1s forward collision envelope ($r_{\text{safe}} = 15\text{ cm}$ radius boundary) against raw LiDAR and IMU telemetry.
   - Triggers hard stall on FPGA inference input, performs an active emergency backoff recovery maneuver (reversing at $0.15\text{ m/s}$ for $0.1\text{ s}$), and resumes target tracking.
   - Enforces a 20–30 ms freshness timeout / drop policy on raw sensor inputs to prevent stale inferences from lagging FPGA execution ($~16\text{ ms}$ PL execution time).
4. **Mecanum Dynamic Velocity Dispatch**: Adapting runtime speed bounds dynamically (like `teleop_mecanum.py` runtime speed scaling) and converting twist outputs to 4-wheel Mecanum RPS (with physical right-side sign inversion).
5. **Substantial Robustness Enhancements**: Transitioning from open-loop, time-stepped coordinate dead-reckoning (used in the naive `waypoint_list`) to closed-loop closed-space tracking with carrot lookahead, adaptive waypoint switching, stuck detection, dynamic re-planning, and graceful degradation.

---

## 2. Analysis of Existing Codebase & Identified Limitations

### 2.1 The Reference `waypoint_list/` Mechanism
In `waypoint_list/waypoint_server/waypoint_server/waypoint_Action_Server.py`:
- **Open-Loop Execution**: It calculates linear and angular velocities simply as $(x_2 - x_1)/t$ and $(\psi_2 - \psi_1)/t$ and loops with `time.sleep(0.1)` until elapsed time reaches duration.
- **Blind Assumption**: The robot assumes it reaches the exact target coordinate at the end of the time duration, completely ignoring wheel slip, obstacle detours, delays, or external disturbances.
- **Disconnected from AI & Sensors**: It publishes directly to `/cmd_vel` without sensing LiDAR or feeding the 74-D input observation pipeline.

### 2.2 The AI Inference Pipeline (`src/igor_controller` & `src/igor_navigation`)
- **Neural Network Architecture**: MLP taking 74 inputs:
  - `obs[0..63]`: 64 normalized frontal LiDAR rays ($[-\pi/2, +\pi/2]$, clipped to 3.5m).
  - `obs[64..66]`: IMU linear accelerations $(a_x, a_y, a_z) / 3.0$.
  - `obs[67..69]`: IMU angular velocities $(\omega_x, \omega_y, \omega_z) / 2.0$ in rad/s.
  - `obs[70..72]`: Nominal commanded velocities $(v_x / 0.60, v_y / 0.50, \omega_z / 2.0)$.
  - `obs[73]`: Course-Lock normalized heading error $\Delta \theta / \pi \in [-1, 1]$.
- **Residual Output**: 3 actions $(\Delta v_x, \Delta v_y, \Delta \omega_z)$ in $[-1, 1]$ quantized in Q8.8 fixed point for DE10-Nano FPGA accelerator.
- **Nominal Guidance Needed**: The AI model is trained as a **gated residual collision avoidance controller**. It *requires* a valid nominal velocity $(v_x, v_y, \omega_z)$ and heading error $\Delta \theta$ directed toward the target lookahead carrot. Without a goal-directed nominal command, the robot cannot progress to global waypoints.

---

## 3. Robustness Architecture & Critical Improvements

To achieve production-grade robustness and satisfy all requirements from `global_planner_architecture.md`, the new global planner architecture replaces the naive open-loop system with the following improvements:

```
+---------------------------------------------------------------------------------------------+
|                                    ROS 2 MISSION LAYER                                      |
|  +-----------------------------+               +-----------------------------------------+  |
|  | Waypoint Client             |  Action Goal  | Igor Global Planner Node                |  |
|  | (YAML List / Aruco / Manual)| ------------> | (Action Server: WaypointSet.action)     |  |
|  +-----------------------------+               +-----------------------------------------+  |
+-------------------------------------------------------------|-------------------------------+
                                                              | Lookahead Carrot & Path
                                                              v
+---------------------------------------------------------------------------------------------+
|                                JETSON ORIN NANO SAFETY GATE                                 |
|  +---------------------------------------------------------------------------------------+  |
|  | 1. Sensor Freshness Filter: Discards IMU/LiDAR older than 20-30 ms                     |  |
|  | 2. Lookahead Carrot Tracker: Generates nominal (cmd_vx, cmd_vy, cmd_omega, delta_theta)|  |
|  | 3. Safety Gate Forward Predictor: 0.1s kinematic projection vs 15cm obstacle zone      |  |
|  | 4. Emergency Backoff Recovery FSM: Reverse 0.15 m/s for 0.1s -> resume inference       |  |
|  +---------------------------------------------------------------------------------------+  |
+------------------------------------|------------------------^-------------------------------+
                        Nominal Obs  |                        | AI Actions
                        (74-D Q8.8)  v                        | (3-D Q8.8)
+-------------------------------------------------------------|-------------------------------+
|                       ACCELERATION ENGINE (DUAL-MODE)                                       |
|  +---------------------------------------------------------------------------------------+  |
|  | Gigabit Ethernet (UDP port 8080) to DE10-Nano HPS/FPGA (or UART / Local CPU fallback) |  |
|  | Inference: 74 inputs -> MLP (128 -> 64 -> 3) -> raw delta twist actions (~16 ms)      |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
                                                              | Safe Blended Twist
                                                              v
+---------------------------------------------------------------------------------------------+
|                                    ACTUATION & LOW-LEVEL                                    |
|  +---------------------------------------------------------------------------------------+  |
|  | Mecanum Inverse Kinematics (Right-side sign mirror) + Dynamic Max Speed Scaling       |  |
|  | STM32 Motor Driver: 4-wheel RPS packet (Func 0x03, 1 Mbps)                             |  |
|  | Hardware Watchdog: Implemented & configurable (passive/dormant by default)             |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
```

### 3.1 Closed-Loop Lookahead Tracking vs. Open-Loop Timing
* **Improvement**: Replace the timer-based duration loop with closed-loop pose feedback (fused from wheel odometry, IMU yaw, or SLAM `/pose`).
* **Mechanism**: Use `GlobalPath` and `LookaheadCarrotTracker` (from `igor_navigation.utils.path_tracker`) to dynamically compute nominal body velocities $(v_x, v_y, \omega_z)$ directed toward a carrot point at lookahead distance $L_d$ (default $0.60\text{ m}$).
* **Goal Tolerance & Timeout**: Waypoint transition triggers when Euclidean distance to target $< \epsilon_{\text{dist}}$ (e.g., $0.15\text{ m}$) and angular error $< \epsilon_{\text{yaw}}$ (e.g., $0.1\text{ rad}$), with a maximum timeout guard to prevent infinite hanging.

### 3.2 Sensor Freshness Timeout Gate (20–30 ms)
* **Requirement**: "Safety guard also have the behavior to drop the message from the input from the raw data if the raw data seemed old with timeout like 20-30 ms (it is because the processing of data of fpga took around 16 ms from my current testing)"
* **Mechanism**: Every incoming LiDAR and IMU message is timestamped with system monotonic nanoseconds. Before packing the 74-D observation vector:
  $$\Delta t_{\text{sensor}} = t_{\text{current}} - t_{\text{sensor\_stamp}}$$
  If $\Delta t_{\text{sensor}} > 25\text{ ms}$ (configurable 20–30 ms), the stale frame is dropped. If staleness persists for $> 3$ consecutive ticks, the node drops nominal velocity to 0 and holds position until fresh sensor data arrives.

### 3.3 Active Safety Gate & 0.1s Forward Collision Prediction
* **Requirement**: Calculate position for the next $0.1\text{ s}$ with the given inference from FPGA. If it enters a $15\text{ cm}$ boundary zone of an obstacle aligned with movement direction:
  1. Block all input to FPGA (stalling inference).
  2. Stop and reverse backward for $0.1\text{ s}$ with velocity $0.15\text{ m/s}$.
  3. Resume inference toward the former target.
* **Kinematic Forward Projection**:
  Given current robot pose $(x_0, y_0, \theta_0)$ and candidate twist $(v_x, v_y, \omega)$:
  $$\theta_{0.1} = \theta_0 + \omega \cdot \Delta t \quad (\Delta t = 0.1\text{ s})$$
  $$\begin{bmatrix} \Delta x_{\text{world}} \\ \Delta y_{\text{world}} \end{bmatrix} = \begin{bmatrix} \cos\theta_0 & -\sin\theta_0 \\ \sin\theta_0 & \cos\theta_0 \end{bmatrix} \begin{bmatrix} v_x \Delta t \\ v_y \Delta t \end{bmatrix}$$
  $$p_{0.1} = [x_0 + \Delta x_{\text{world}},\; y_0 + \Delta y_{\text{world}}]$$
* **Obstacle Boundary Test**:
  Check distance from $p_{0.1}$ to all LiDAR detected obstacle points within the directional motion cone:
  $$d_{\text{obs}} = \min_i \| p_{0.1} - p_{\text{obs}, i} \|$$
  If $d_{\text{obs}} < R_{\text{boundary}} = 0.15\text{ m}$ (safety bubble):
  - Transition state machine to `SAFETY_GATE_ACTIVE`.
  - Suppress FPGA TX packets (freeze FPGA inference).
  - Inject reverse recovery maneuver: $v_x = -0.15\text{ m/s},\; v_y = 0.0,\; \omega = 0.0$ for $t_{\text{reverse}} = 0.1\text{ s}$.
  - Transition to `RESUME_TRACKING` once backoff completes.

### 3.4 Runtime Speed Scaling Without Keypress Stalls
* **Requirement**: "changing max speed value when runtime will also change the value itself without waiting for any input key for its direction."
* **Mechanism**: Implement a dynamic ROS 2 Parameter callback (`add_on_set_parameters_callback`) for `max_linear_speed`, `max_angular_speed`, and `speed_scale_factor` (0.1 to 2.0). When updated via ROS 2 CLI (`ros2 param set ...`) or teleop publisher, the controller recalculates kinematic bounds immediately without re-initialization or waiting for directional inputs.

### 3.5 Watchdog Architecture
* **Requirement**: "For its hardware watchdog, implement it but don't activate it for now as I want to prove the system fully running without handling the safety of the jetson for now."
* **Mechanism**: Provide a dedicated `HeartbeatWatchdog` class on the Jetson that formats ping/keepalive packets and checks serial/socket activity. Add a boolean flag `enable_watchdog = False` (default) so that the watchdog structure is present, fully tested in mock, but dormant during initial hardware validation.

---

## 4. Architectural Data Flow & Component Mapping

```
                                      +---------------------------------------------+
                                      |            waypoint_client_node             |
                                      | Reads waypoints.yaml & Aruco Docking goals  |
                                      +---------------------------------------------+
                                                             |
                                                             | WaypointSet.action
                                                             v
                                      +---------------------------------------------+
                                      |          igor_global_planner_node           |
                                      | - Action Server (WaypointSet)               |
                                      | - Multi-goal queue management               |
                                      | - Lookahead Carrot Generator                |
                                      | - Progress & State Publisher                |
                                      +---------------------------------------------+
                                                             |
                                                             | /cmd_vel_in + Waypoint carrot
                                                             v
+------------------+  /scan (360)     +---------------------------------------------+
| RPLiDAR A1/A2    | ---------------> |             igor_controller_node            |
+------------------+  (Subsampled 64) | - Freshness Gate (< 25ms timeout)           |
                                      | - 74-D Vector Packing (Q8.8)                |
+------------------+  Func 0x07 (1M)  | - Ethernet UDP Bridge to DE10-Nano (8080)   |
| STM32 IMU Driver | ---------------> | - 0.1s Predictive Safety Gate               |
+------------------+  (ax..az, gx..gz)| - 0.15 m/s Reverse Recovery FSM             |
                                      | - Dynamic Speed Parameter Callback          |
                                      +---------------------------------------------+
                                                             |
                                                             | Func 0x03 (4x Mecanum RPS)
                                                             v
                                      +---------------------------------------------+
                                      |           STM32 Motor Controller            |
                                      | (FL: M1, RL: M2, FR: -M3, RR: -M4)          |
                                      +---------------------------------------------+
```

---

## 5. Step-by-Step Implementation Plan

### Phase 1: Global Planner Action Server Upgrade (`igor_planner`)
1. Create `igor_planner` package (or extend `igor_navigation` and `waypoint_server`) with:
   - Action server implementing `WaypointSet.action` compatible with `waypoint_client`.
   - Closed-loop waypoint navigation using robot odometry/pose instead of open-loop `time.sleep`.
   - Continuous real-time feedback computation: `absis_feedback`, `ordinat_feedback`, `yaw_feedback`, and `progress` percentage.
   - Smooth lookahead carrot calculation feeding the local controller via `/cmd_vel_in` and `/igor/target_pose`.

### Phase 2: Sensor Freshness Filter & 74-D Vector Pipeline
1. In `igor_controller/controller_node.py`:
   - Enhance LiDAR subsampler and IMU callback to track nanosecond timestamps.
   - Introduce `MAX_SENSOR_LATENCY_SEC = 0.025` (25 ms).
   - If sensor data age $> 25\text{ ms}$, reject packet and log warning; fall back to safe zero-command if timeout exceeds 3 cycles ($60\text{ ms}$).
   - Package validated 74-D vector with normalized sensors, nominal velocities, and heading error.

### Phase 3: Jetson Orin Nano Predictive Safety Gate & Recovery FSM
1. In `igor_controller/controller_node.py`:
   - Implement `check_forward_collision_risk(candidate_twist, lidar_beams, dt=0.1, radius=0.15)`.
   - Implement 3-State Recovery FSM:
     - `STATE_NORMAL`: Feed 74-D observation to DE10 FPGA; execute gated residual actions.
     - `STATE_SAFETY_TRIPPED`: When 0.1s forward trajectory enters 15 cm obstacle zone:
       * Inhibit outgoing UDP packets to DE10 (stall inference).
       * Command immediate stop, then $v_x = -0.15\text{ m/s}$ for $0.1\text{ s}$.
     - `STATE_RECOVERY_COMPLETE`: Reset obstacle trajectory buffer and resume inference toward original global waypoint.

### Phase 4: DE10-Nano Ethernet UDP Bridge Integration
1. Extend `fpga_bridge.py`:
   - Implement `UDPFPGABridge` adhering to `pipeline_architecture.md`:
     * Target IP: `192.168.1.50` (or `127.0.0.1` in mock mode), Port `8080`.
     * Binary packed structs with Q8.8 fixed-point serialization.
     * Socket timeout of $30\text{ ms}$ (with fallback to CPU controller if bridge packet is lost).

### Phase 5: Dynamic Speed Adjustment & Watchdog Skeleton
1. In `controller_node.py` and `teleop_mecanum.py`:
   - Bind dynamic parameter reconfiguration to adjust `max_linear_x`, `max_linear_y`, `max_angular_z`, and `speed_multiplier` without needing directional keypresses.
   - Implement dormant `STM32Watchdog` with heartbeat frame generation, enabled via parameter `enable_watchdog` (default: `False`).

### Phase 6: Dual-Mode Testing & Verification
1. Stage 1: Software Loopback / Mock Mode:
   - Run simulated `mock_de10_host_server` and `waypoint_client` with sample `waypoints.yaml`.
   - Verify closed-loop waypoint transition, feedback reporting, and mock safety gate intervention.
2. Stage 2: Hardware Deployment:
   - Deploy on Jetson Orin Nano connected to STM32 over USB (`/dev/ttyACM0`) and DE10-Nano over Gigabit Ethernet.

---

## 6. Verification Criteria & Acceptance Metrics

| Verification Item | Acceptance Criteria |
|---|---|
| **Waypoint Action Server** | Successfully accepts `WaypointSet` goals, publishes real-time feedback, and reaches target with tolerance $< 0.15\text{ m}$ closed-loop. |
| **Observation Dimension** | Bit-for-bit compliance with 74-D vector (`64 LiDAR + 6 IMU + 3 Twist + 1 Heading`) in Q8.8 fixed point. |
| **Sensor Freshness Gate** | Stale sensor data older than $25\text{ ms}$ is dropped and flagged before reaching FPGA inference. |
| **0.1s Predictive Safety Gate** | When obstacle is within 15 cm of predicted 0.1s forward path, inference stalls and robot backs up at $0.15\text{ m/s}$ for $0.1\text{ s}$. |
| **Dynamic Speed Scaling** | Updating speed parameter modifies robot speed in real-time without requiring directional trigger. |
| **Watchdog Dormancy** | Watchdog code exists and builds cleanly, remaining inactive by default (`enable_watchdog:=false`). |
