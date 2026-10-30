#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controller_node.py - ROS 2 Igor Navigation Controller Node & Jetson Orin Safety Gate
Target Platform: Hiwonder JetAuto Mecanum AMR (Jetson Orin Nano + STM32 + DE10-Nano)
PERURI Chip Hackathon 2026 - Project IGOR

Execution Pipeline:
1. Subscribes /scan (360° RPLiDAR) and /cmd_vel_in (Global Planner / Lookahead Carrot).
2. Freshness Gate (< 25 ms): Rejects stale LiDAR/IMU inputs to prevent lagging FPGA execution.
3. Subsamples scan to 64 frontal beams via LidarSubsampler.
4. Reads MPU-6050 IMU telemetry via background STM32 driver.
5. Auto-calibrates gyro bias and tracks Course-Lock heading difference (obs[73]).
6. Assembles 74-dimension observation vector in Q8.8 fixed-point scaling.
7. Enforces STRICT FPGA GUARD & Ethernet/Serial FPGA Bridge:
   - Evaluates 0.1s predictive forward collision boundary (15 cm radius).
   - If barrier violated: Activates Jetson Safety Gate -> blocks FPGA inference input,
     commands zero wheel speeds during a 0.1s stop interval, then resumes target tracking.
8. Dynamic speed bounds: Runtime parameter updates without keypress halts.
9. Computes 4-wheel Mecanum RPS with JetAuto physical right-side sign inversion.
10. Transmits motor speeds to STM32 @ 1 Mbps and publishes /igor/cmd_vel_safe & /igor/heading.
"""

import sys
import json
import math
import time
import numpy as np
from typing import Optional, Tuple, Dict, Any

import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import SetParametersResult
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32, String, Bool

# Import IGOR submodules
from igor_navigation.drivers.lidar_subsampler import LidarSubsampler
from igor_navigation.utils.kinematics import MecanumKinematics
from igor_navigation import create_controller

from igor_controller.mcu_driver import STM32Driver
from igor_controller.heading_estimator import HeadingEstimator
from igor_controller.fpga_bridge import FPGABridge, FPGACommunicationError


class HardwareWatchdog:
    """
    Heartbeat Watchdog for Jetson Orin <-> STM32/FPGA link.
    Implemented but kept dormant (passive) by default as requested in architecture.
    """
    def __init__(self, timeout_sec: float = 0.5, enabled: bool = False):
        self.timeout_sec = timeout_sec
        self.enabled = enabled
        self.last_heartbeat = time.monotonic()
        self.tripped = False

    def kick(self) -> None:
        self.last_heartbeat = time.monotonic()
        self.tripped = False

    def is_expired(self) -> bool:
        if not self.enabled:
            return False
        if time.monotonic() - self.last_heartbeat > self.timeout_sec:
            self.tripped = True
            return True
        return False


class IgorControllerNode(Node):
    VALID_FPGA_ALGORITHMS = {'cl_drl', 'cl_drl_cbf', 'cl_drl_dwa'}

    def __init__(self):
        super().__init__('igor_controller_node')

        # Declare ROS 2 Parameters
        self.declare_parameter('algorithm', 'cl_drl_cbf')
        self.declare_parameter('use_fpga', False)
        self.declare_parameter('mcu_port', '/dev/ttyACM0')
        self.declare_parameter('fpga_port', '/dev/fpga')
        self.declare_parameter('fpga_baudrate', 921600)
        self.declare_parameter('fpga_timeout', 0.3)
        self.declare_parameter('control_rate_hz', 50.0)
        self.declare_parameter('use_mock_serial', False)

        # Dynamic Speed Parameters (Updated at runtime without keypress delay)
        self.declare_parameter('max_linear_x', 0.60)
        self.declare_parameter('max_linear_y', 0.50)
        self.declare_parameter('max_angular_z', 2.00)
        self.declare_parameter('speed_scale', 1.0)

        # Safety Gate Parameters
        self.declare_parameter('sensor_freshness_timeout_ms', 25.0)  # 20-30 ms freshness gate
        self.declare_parameter('safety_boundary_radius', 0.15)      # 15 cm obstacle zone
        self.declare_parameter('safety_reverse_speed', 0.15)        # 0.15 m/s reverse
        self.declare_parameter('safety_reverse_duration', 0.10)     # 0.1s backoff duration
        self.declare_parameter('enable_watchdog', False)            # Dormant by default

        self.algorithm = str(self.get_parameter('algorithm').value).lower()
        self.use_fpga = bool(self.get_parameter('use_fpga').value)
        self.mcu_port = str(self.get_parameter('mcu_port').value)
        self.fpga_port = str(self.get_parameter('fpga_port').value)
        self.fpga_baudrate = int(self.get_parameter('fpga_baudrate').value)
        self.fpga_timeout = float(self.get_parameter('fpga_timeout').value)
        self.control_rate_hz = float(self.get_parameter('control_rate_hz').value)
        self.use_mock_serial = bool(self.get_parameter('use_mock_serial').value)

        self.freshness_timeout_sec = float(self.get_parameter('sensor_freshness_timeout_ms').value) / 1000.0
        self.safety_radius = float(self.get_parameter('safety_boundary_radius').value)
        self.reverse_speed = float(self.get_parameter('safety_reverse_speed').value)
        self.reverse_duration = float(self.get_parameter('safety_reverse_duration').value)
        self.enable_watchdog = bool(self.get_parameter('enable_watchdog').value)

        # Register dynamic parameter callback
        self.add_on_set_parameters_callback(self._on_parameter_change)

        self.get_logger().info("==================================================================")
        self.get_logger().info("  IGOR CONTROLLER INITIALIZING (Hiwonder JetAuto Mecanum AMR)")
        self.get_logger().info(f"  Selected Algorithm : {self.algorithm}")
        self.get_logger().info(f"  FPGA Acceleration  : {self.use_fpga}")
        self.get_logger().info(f"  MCU Port           : {self.mcu_port}")
        self.get_logger().info(f"  FPGA Port          : {self.fpga_port}")
        self.get_logger().info(f"  Freshness Timeout  : {self.freshness_timeout_sec*1000.0:.1f} ms")
        self.get_logger().info(f"  Watchdog Active    : {self.enable_watchdog} (Dormant={not self.enable_watchdog})")
        self.get_logger().info("==================================================================")

        # STRICT FPGA GUARD: Reject non-neural algorithms on FPGA
        if self.use_fpga and self.algorithm not in self.VALID_FPGA_ALGORITHMS:
            self.get_logger().fatal(
                f"\n[FATAL CONFIGURATION ERROR] use_fpga=True is only supported for CL-DRL neural\n"
                f"network hardware acceleration ('cl_drl', 'cl_drl_cbf', 'cl_drl_dwa').\n"
                f"The requested algorithm '{self.algorithm}' is an iterative classical planner!\n"
            )
            raise RuntimeError(f"Illegal configuration: algorithm '{self.algorithm}' cannot run on FPGA accelerator.")

        # Kinematics helper
        self.kinematics = MecanumKinematics(
            wheelbase=0.216,
            track_width=0.195,
            wheel_diameter=0.0965,
            max_rps=5.0
        )

        # Hardware Watchdog (Dormant by default)
        self.watchdog = HardwareWatchdog(timeout_sec=0.5, enabled=self.enable_watchdog)

        # LiDAR Subsampler (360 deg -> 64 frontal beams)
        self.lidar_subsampler = LidarSubsampler(
            num_target_rays=64,
            angle_min=-np.pi / 2.0,
            angle_max=np.pi / 2.0,
            min_range=0.15,
            max_range=3.50
        )
        self.latest_ranges: Optional[np.ndarray] = None
        self.last_scan_time: float = 0.0

        # STM32 MCU Driver
        self.mcu = STM32Driver(
            port=self.mcu_port,
            baudrate=1000000,
            mock=self.use_mock_serial
        )

        # Heading Engine
        self.heading_engine = HeadingEstimator(
            calib_samples=100,
            omega_deadband=0.02,
            initial_yaw=0.0
        )

        # FPGA Bridge or CPU Controller
        self.fpga: Optional[FPGABridge] = None
        self.cpu_controller = None

        if self.use_fpga:
            self.fpga = FPGABridge(
                port=self.fpga_port,
                baudrate=self.fpga_baudrate,
                timeout=self.fpga_timeout,
                mock=self.use_mock_serial
            )
            if self.algorithm in ['cl_drl_cbf', 'cl_drl_dwa']:
                self.cpu_controller = create_controller(algo_name=self.algorithm)
        else:
            self.cpu_controller = create_controller(algo_name=self.algorithm)

        # Commanded Velocity State
        self.cmd_linear_x = 0.0
        self.cmd_linear_y = 0.0
        self.cmd_angular_z = 0.0
        self.last_cmd_time = time.monotonic()

        # =====================================================================
        # Jetson Orin Nano Safety Gate State Machine
        # States:
        #   0: NORMAL (AI inference streaming to FPGA / CPU)
        #   1: SAFETY_GATE_ACTIVE (FPGA blocked, reversing 0.15 m/s for 0.1s)
        # =====================================================================
        self.safety_gate_active = False
        self.safety_reverse_start_time = 0.0
        self.safety_events_count = 0
        self.stale_sensor_drops = 0

        # ROS 2 Subscribers
        self.sub_scan = self.create_subscription(
            LaserScan,
            '/scan',
            self._scan_callback,
            rclpy.qos.qos_profile_sensor_data
        )

        self.sub_cmd_vel = self.create_subscription(
            Twist,
            '/cmd_vel_in',
            self._cmd_vel_callback,
            10
        )

        self.sub_cmd_vel_std = self.create_subscription(
            Twist,
            '/cmd_vel',
            self._cmd_vel_callback,
            10
        )

        # ROS 2 Publishers
        self.pub_safe_twist = self.create_publisher(Twist, '/igor/cmd_vel_safe', 10)
        self.pub_heading = self.create_publisher(Float32, '/igor/heading', 10)
        self.pub_diag = self.create_publisher(String, '/igor/diagnostics', 10)
        self.pub_safety_alert = self.create_publisher(Bool, '/igor/safety_gate_alert', 10)

        # Control Loop Timer (50 Hz)
        timer_period = 1.0 / self.control_rate_hz
        self.timer = self.create_timer(timer_period, self._control_loop)
        self.get_logger().info(f"IgorControllerNode successfully started at {self.control_rate_hz:.1f} Hz.")

    def _on_parameter_change(self, params):
        for param in params:
            if param.name == 'max_linear_x':
                self.get_logger().info(f"Updated max_linear_x: {param.value}")
            elif param.name == 'max_linear_y':
                self.get_logger().info(f"Updated max_linear_y: {param.value}")
            elif param.name == 'max_angular_z':
                self.get_logger().info(f"Updated max_angular_z: {param.value}")
            elif param.name == 'speed_scale':
                self.get_logger().info(f"Updated speed_scale: {param.value}")
            elif param.name == 'enable_watchdog':
                self.enable_watchdog = bool(param.value)
                self.watchdog.enabled = self.enable_watchdog
                self.get_logger().info(f"Watchdog enabled state updated: {self.enable_watchdog}")
        return SetParametersResult(successful=True)

    def _scan_callback(self, msg: LaserScan) -> None:
        self.latest_ranges = None
        self.last_scan_time = 0.0
        ranges = np.asarray(msg.ranges, dtype=np.float32)
        increment = float(msg.angle_increment)
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        age = self.get_clock().now().nanoseconds / 1e9 - stamp
        if (len(ranges) < 64 or not math.isfinite(msg.angle_min)
                or not math.isfinite(increment) or increment == 0
                or abs(abs(increment)*len(ranges)-2*math.pi) > max(.04, 1.5*abs(increment))
                or not -.1 <= age < .5 or np.any(np.isnan(ranges))
                or np.any(np.isneginf(ranges)) or np.any(ranges <= .05)):
            return
        self.latest_ranges = ranges
        self.scan_angle_min = float(msg.angle_min)
        self.scan_angle_end = float(msg.angle_min) + len(ranges)*increment
        self.last_scan_time = time.monotonic()

    def _stop_for_fault(self, reason):
        sent = self.mcu.send_motor_speeds(0., 0., 0., 0.)
        self.pub_safe_twist.publish(Twist())
        self.pub_safety_alert.publish(Bool(data=True))
        self.pub_diag.publish(String(data=json.dumps({
            'fault': reason, 'safety_permit': False, 'fpga': self.use_fpga,
            'mock': self.use_mock_serial, 'safe': [0.,0.,0.], 'rps': [0.]*4,
            'motor_tx_confirmed': sent is True})))

    def _cmd_vel_callback(self, msg: Twist) -> None:
        """Stores commanded velocities and applies dynamic speed scaling."""
        scale = float(self.get_parameter('speed_scale').value)
        max_vx = float(self.get_parameter('max_linear_x').value) * scale
        max_vy = float(self.get_parameter('max_linear_y').value) * scale
        max_wz = float(self.get_parameter('max_angular_z').value) * scale

        self.cmd_linear_x = float(np.clip(msg.linear.x * scale, -0.15, max_vx))
        self.cmd_linear_y = float(np.clip(msg.linear.y * scale, -max_vy, max_vy))
        self.cmd_angular_z = float(np.clip(msg.angular.z * scale, -max_wz, max_wz))
        self.last_cmd_time = time.monotonic()
        self.watchdog.kick()

    def check_forward_collision_risk(
        self,
        cand_vx: float,
        cand_vy: float,
        cand_omega: float,
        beams_m: np.ndarray,
        horizon_dt: float = 0.10,
        boundary_radius: float = 0.15
    ) -> bool:
        """
        Jetson Orin Safety Gate: Kinematic Forward Projection over 0.1s.
        Tests whether the candidate robot motion causes the robot to enter a 15 cm boundary zone
        of an obstacle aligned with its motion direction.
        """
        # Forward translation in body frame over 0.1s
        dx_b = cand_vx * horizon_dt
        dy_b = cand_vy * horizon_dt
        disp_norm = math.hypot(dx_b, dy_b)

        if disp_norm < 1e-4:
            # Stationary or pure rotation: test closest frontal ray
            return bool(np.min(beams_m) < boundary_radius)

        motion_angle = math.atan2(dy_b, dx_b)  # In body frame [-pi, pi]

        # Check rays within 45 degrees of motion direction
        ray_angles = np.linspace(-np.pi / 2.0, np.pi / 2.0, len(beams_m))
        for r_m, r_ang in zip(beams_m, ray_angles):
            ang_diff = abs(math.atan2(math.sin(r_ang - motion_angle), math.cos(r_ang - motion_angle)))
            if ang_diff < (np.pi / 4.0):
                # Obstacle point in body frame
                ox = r_m * math.cos(r_ang)
                oy = r_m * math.sin(r_ang)
                # Distance from predicted 0.1s robot position to obstacle point
                d_predicted = math.hypot(ox - dx_b, oy - dy_b)
                if d_predicted < boundary_radius:
                    return True
        return False

    def _control_loop(self) -> None:
        """Main 50 Hz control execution loop."""
        now = time.monotonic()
        dt = 1.0 / self.control_rate_hz

        # Missing/stale data cannot be replaced by a clear-space observation.
        if not 0 <= now-self.last_cmd_time < .5:
            self._stop_for_fault('COMMAND_STALE')
            return
        if not self.use_mock_serial and (self.latest_ranges is None or
                not 0 <= now-self.last_scan_time <= self.freshness_timeout_sec):
            self._stop_for_fault('SCAN_MISSING_OR_STALE')
            return
        command = np.array([self.cmd_linear_x,self.cmd_linear_y,self.cmd_angular_z])
        if not np.all(np.isfinite(command)):
            self._stop_for_fault('COMMAND_INVALID')
            return

        # Watchdog timeout check
        if self.watchdog.is_expired():
            self.get_logger().warn("Watchdog timeout expired! Neutralizing commands.")
            self.cmd_linear_x = 0.0
            self.cmd_linear_y = 0.0
            self.cmd_angular_z = 0.0

        # Command loss timeout (> 0.5s)
        if now - self.last_cmd_time > 0.5:
            self.cmd_linear_x = 0.0
            self.cmd_linear_y = 0.0
            self.cmd_angular_z = 0.0

        # =====================================================================
        # 1. SENSOR FRESHNESS FILTER (20-30 ms drop threshold)
        # =====================================================================
        lidar_fresh = False
        if self.latest_ranges is not None and len(self.latest_ranges) > 0:
            lidar_age = now - self.last_scan_time
            if lidar_age <= self.freshness_timeout_sec:
                lidar_fresh = True
            else:
                self.stale_sensor_drops += 1
                # If sensor data is stale, drop message and log periodically
                if self.stale_sensor_drops % 50 == 1:
                    self.get_logger().warn(
                        f"Dropping stale LiDAR data! Age: {lidar_age*1000.0:.1f}ms > "
                        f"{self.freshness_timeout_sec*1000.0:.1f}ms threshold."
                    )

        if lidar_fresh:
            beams_m = self.lidar_subsampler.subsample_from_laserscan(
                self.latest_ranges, angle_min=self.scan_angle_min, angle_max=self.scan_angle_end
            )
            beams_norm = np.clip(beams_m / 3.50, 0.0, 1.0).astype(np.float32)
            d_min = float(np.min(beams_m))
        else:
            # Fallback safe default observation
            beams_norm = np.ones(64, dtype=np.float32)
            beams_m = np.ones(64, dtype=np.float32) * 3.50
            d_min = 3.50

        # 2. Process IMU Telemetry & Heading
        (ax, ay, az), (gx, gy, gz), imu_t = self.mcu.get_latest_imu()
        if not np.all(np.isfinite([ax,ay,az,gx,gy,gz])):
            self._stop_for_fault('IMU_INVALID')
            return
        if not self.use_mock_serial and (imu_t <= 0 or not 0 <= time.monotonic()-imu_t <= self.freshness_timeout_sec):
            self._stop_for_fault('IMU_MISSING_OR_STALE')
            return
        imu_age = now - imu_t if imu_t > 0 else 0.0
        if imu_age > self.freshness_timeout_sec and imu_t > 0:
            self.stale_sensor_drops += 1

        self.heading_engine.update_imu(gz, current_time=now)
        self.heading_engine.update_command(self.cmd_angular_z, dt=dt)

        delta_theta = self.heading_engine.get_heading_difference()
        norm_delta_theta = self.heading_engine.get_normalized_heading_error()

        # Publish Heading Telemetry
        heading_msg = Float32()
        heading_msg.data = float(delta_theta)
        self.pub_heading.publish(heading_msg)

        # 3. Assemble 74-Element Observation Vector
        # obs[0..63]  : 64 frontal LiDAR beams in [0, 1]
        # obs[64..66] : ax/3.0, ay/3.0, az/3.0
        # obs[67..69] : gx/2.0, gy/2.0, gz/2.0 (in rad/s)
        # obs[70..72] : vx_cmd/0.60, vy_cmd/0.50, wz_cmd/2.0
        # obs[73]     : delta_theta / pi in [-1, 1]
        obs = np.zeros(74, dtype=np.float32)
        obs[0:64] = beams_norm
        obs[64] = float(ax) / 3.0
        obs[65] = float(ay) / 3.0
        obs[66] = float(az) / 3.0
        obs[67] = math.radians(gx) / 2.0
        obs[68] = math.radians(gy) / 2.0
        obs[69] = math.radians(gz) / 2.0
        obs[70] = float(self.cmd_linear_x) / 0.60
        obs[71] = float(self.cmd_linear_y) / 0.50
        obs[72] = float(self.cmd_angular_z) / 2.0
        obs[73] = norm_delta_theta
        obs[64:70] = np.clip(obs[64:70], -1., 1.)

        v_cmd = np.array([self.cmd_linear_x, self.cmd_linear_y, self.cmd_angular_z], dtype=np.float32)

        # =====================================================================
        # 4. SAFETY GATE RECOVERY FSM
        # =====================================================================
        if self.safety_gate_active:
            # Hold zero wheel speeds while the stop interval is active
            if (now - self.safety_reverse_start_time) < self.reverse_duration:
                # Disallow FPGA input; hold STOP
                v_safe = np.zeros(3, dtype=np.float32)
                self.pub_safety_alert.publish(Bool(data=True))
            else:
                # Recovery duration elapsed: deactivate safety gate and resume normal inference
                self.safety_gate_active = False
                self.get_logger().info("Safety Gate: Stop interval complete. Resuming inference toward former target.")
                v_safe = np.zeros(3, dtype=np.float32)
                self.pub_safety_alert.publish(Bool(data=False))
        else:
            # 5. Normal AI Inference Path (FPGA or CPU)
            if self.use_fpga:
                # Query FPGA inference
                try:
                    raw_action = self.fpga.infer(obs)
                except FPGACommunicationError as exc:
                    self.mcu.send_motor_speeds(0.0, 0.0, 0.0, 0.0)
                    self.pub_safe_twist.publish(Twist())
                    self.pub_safety_alert.publish(Bool(data=True))
                    self.pub_diag.publish(String(data=json.dumps({
                        'fault': f'FPGA_TRANSPORT: {exc}', 'safety_permit': False,
                        'safe': [0.0, 0.0, 0.0]})))
                    self.get_logger().error(f'FPGA transport failed; motors stopped: {exc}')
                    return
                delta_vx = raw_action[0] * 0.60 if raw_action[0] < 0.0 else raw_action[0] * 0.15
                delta_vy = raw_action[1] * 0.45
                delta_wz = raw_action[2] * 0.80
                v_exec_drl = v_cmd + np.array([delta_vx, delta_vy, delta_wz], dtype=np.float32)

                alpha = float(np.clip((1.40 - d_min) / (1.40 - 0.35), 0.0, 1.0))
                v_blended = (1.0 - alpha) * v_cmd + alpha * v_exec_drl

                allowed_max_vx = self.cpu_controller.compute_speed_envelope(d_min) if self.cpu_controller else 0.60

                if self.algorithm == 'cl_drl_cbf':
                    safe_vx, safe_vy, safe_wz, _ = self.cpu_controller.filter_cbf(
                        cand_vx=float(v_blended[0]),
                        cand_vy=float(v_blended[1]),
                        cand_omega=float(v_blended[2]),
                        robot_pose=(0.0, 0.0, 0.0),
                        obstacles=[{"x":float(r*np.cos(a)), "y":float(r*np.sin(a)), "radius":0.}
                                   for r,a in zip(beams_m,np.linspace(-np.pi/2,np.pi/2,64)) if r<3.50],
                        allowed_max_vx=allowed_max_vx
                    )
                    cand_safe = np.array([safe_vx, safe_vy, safe_wz], dtype=np.float32)
                else:
                    cand_safe = v_blended

                # Evaluate Safety Gate condition on proposed inference output
                collision_risk = self.check_forward_collision_risk(
                    cand_vx=cand_safe[0],
                    cand_vy=cand_safe[1],
                    cand_omega=cand_safe[2],
                    beams_m=beams_m,
                    horizon_dt=0.10,
                    boundary_radius=self.safety_radius
                )

                if collision_risk:
                    # Trigger Safety Gate: block FPGA input and hold STOP
                    self.safety_gate_active = True
                    self.safety_reverse_start_time = now
                    self.safety_events_count += 1
                    self.get_logger().warn(
                        f"Safety Gate Tripped! Obstacle in 0.1s path (< {self.safety_radius*100:.0f}cm). "
                        f"Stopping all wheels for {self.reverse_duration}s."
                    )
                    v_safe = np.zeros(3, dtype=np.float32)
                    self.pub_safety_alert.publish(Bool(data=True))
                else:
                    v_safe = cand_safe
            else:
                # CPU Controller Path
                exec_vx, exec_vy, exec_wz, _ = self.cpu_controller.predict(
                    lidar_ranges=beams_norm,
                    cmd_vel=(self.cmd_linear_x, self.cmd_linear_y, self.cmd_angular_z),
                    imu_data=(ax, ay, az, gx, gy, gz),
                    heading_err=delta_theta
                )
                cand_safe = np.array([exec_vx, exec_vy, exec_wz], dtype=np.float32)

                # Safety gate evaluation for CPU path as well
                collision_risk = self.check_forward_collision_risk(
                    cand_vx=cand_safe[0],
                    cand_vy=cand_safe[1],
                    cand_omega=cand_safe[2],
                    beams_m=beams_m,
                    horizon_dt=0.10,
                    boundary_radius=self.safety_radius
                )
                if collision_risk:
                    self.safety_gate_active = True
                    self.safety_reverse_start_time = now
                    self.safety_events_count += 1
                    v_safe = np.zeros(3, dtype=np.float32)
                    self.pub_safety_alert.publish(Bool(data=True))
                else:
                    v_safe = cand_safe

        # =====================================================================
        # 6. Inverse Kinematics for JetAuto Mecanum Chassis
        # Note: Right motors (FR M3, RR M4) have mechanical sign inversion
        # =====================================================================
        completed = time.monotonic()
        if not np.all(np.isfinite(v_safe)):
            self._stop_for_fault('CONTROLLER_OUTPUT_INVALID')
            return
        if not 0 <= completed-self.last_cmd_time < .5:
            self._stop_for_fault('COMMAND_STALE_AFTER_COMPUTE')
            return
        if not self.use_mock_serial and (not 0 <= completed-self.last_scan_time <= self.freshness_timeout_sec
                or not 0 <= completed-imu_t <= self.freshness_timeout_sec):
            self._stop_for_fault('SENSOR_STALE_AFTER_COMPUTE')
            return
        if not np.any(command) or d_min <= .22 or self.safety_gate_active:
            v_safe = np.zeros(3, dtype=np.float32)
        v_safe = np.clip(v_safe, [-.15,-.50,-2.], [.60,.50,2.])
        linear_x, linear_y, angular_z = float(v_safe[0]), float(v_safe[1]), float(v_safe[2])
        vp = angular_z * (self.kinematics.wheelbase + self.kinematics.track_width) / 2.0
        circ = math.pi * self.kinematics.wheel_diameter

        v1 = linear_x - linear_y - vp   # FL
        v2 = linear_x + linear_y - vp   # RL
        v3 = -linear_x - linear_y - vp  # FR (Mirrored)
        v4 = -linear_x + linear_y - vp  # RR (Mirrored)

        rps1 = np.clip(v1 / circ, -self.kinematics.max_rps, self.kinematics.max_rps)
        rps2 = np.clip(v2 / circ, -self.kinematics.max_rps, self.kinematics.max_rps)
        rps3 = np.clip(v3 / circ, -self.kinematics.max_rps, self.kinematics.max_rps)
        rps4 = np.clip(v4 / circ, -self.kinematics.max_rps, self.kinematics.max_rps)

        # Transmit motor speed packet to STM32
        if not self.mcu.send_motor_speeds(rps1, rps2, rps3, rps4):
            self._stop_for_fault('MCU_TRANSPORT')
            return

        # Publish Safe Twist
        twist_out = Twist()
        twist_out.linear.x = linear_x
        twist_out.linear.y = linear_y
        twist_out.angular.z = angular_z
        self.pub_safe_twist.publish(twist_out)

        # Diagnostics publication (sampled at 5 Hz)
        if hasattr(self, '_diag_cnt'):
            self._diag_cnt += 1
        else:
            self._diag_cnt = 0

        if self._diag_cnt % 10 == 0:
            diag_data = {
                "algo": self.algorithm,
                "safety_permit": True, "mock": self.use_mock_serial,
                "fpga": self.use_fpga,
                "d_min": round(d_min, 3),
                "cmd": [round(float(c), 3) for c in v_cmd],
                "safe": [round(float(s), 3) for s in v_safe],
                "safety_gate": self.safety_gate_active,
                "safety_events": self.safety_events_count,
                "stale_drops": self.stale_sensor_drops,
                "rps": [round(float(r), 2) for r in [rps1, rps2, rps3, rps4]],
                "heading": self.heading_engine.get_diagnostics()
            }
            diag_msg = String()
            diag_msg.data = json.dumps(diag_data)
            self.pub_diag.publish(diag_msg)

    def destroy_node(self):
        """Clean shutdown hook."""
        self.get_logger().info("Shutting down IgorControllerNode: Stopping motors...")
        try:
            self.mcu.close()
        except Exception:
            pass
        if self.fpga:
            try:
                self.fpga.close()
            except Exception:
                pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = IgorControllerNode()
        rclpy.spin(node)
    except RuntimeError as e:
        print(f"\n[FATAL HALT] {e}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
