#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
heading_estimator.py - High-Precision Orientation & Heading Difference Engine
Target Platform: Hiwonder JetAuto Mecanum (MPU-6050 6-DOF IMU via STM32)
PERURI Chip Hackathon 2026 - Project IGOR

This module performs:
1. Static zero-bias autocalibration of gyro Z-axis (default: 100 samples ~ 2 seconds).
2. Numerical integration of yaw angle theta_robot (rad) with drift compensation.
3. Course-Lock tracking logic: locks target yaw when translational motion is commanded
   with near-zero angular velocity (|omega_cmd| < 0.02 rad/s) to eliminate holonomic drift,
   or dynamically slews target yaw when angular velocity is intentionally commanded.
4. Normalized Heading Difference computation:
   Delta_theta = wrap_to_pi(theta_target - theta_robot)
   obs[73] = clip(Delta_theta / pi, -1.0, 1.0)
"""

import math
import time
from typing import Optional, Tuple, Dict, Any


def wrap_to_pi(angle_rad: float) -> float:
    """Wraps an angle in radians to the interval [-pi, pi]."""
    return math.atan2(math.sin(angle_rad), math.cos(angle_rad))


class HeadingEstimator:
    """
    Heading Estimator & Course-Lock Tracker for Hiwonder JetAuto.
    """
    def __init__(
        self,
        calib_samples: int = 100,
        omega_deadband: float = 0.02,
        initial_yaw: float = 0.0
    ):
        """
        Args:
            calib_samples: Number of initial static samples for gyro zero-bias calibration.
            omega_deadband: Threshold below which omega_cmd is treated as pure translation (Course-Lock).
            initial_yaw: Initial orientation in radians (default: 0.0).
        """
        self.calib_samples = calib_samples
        self.omega_deadband = omega_deadband

        # Calibration state
        self._samples_collected = 0
        self._gyro_z_sum = 0.0
        self.gyro_bias_z = 0.0  # rad/s
        self.is_calibrated = False

        # Integrated Robot State
        self.theta_robot = float(initial_yaw)
        self.theta_target = float(initial_yaw)
        self.last_update_time: Optional[float] = None

        # Course-Lock status
        self.course_locked = True
        self.external_target_mode = False

    def update_imu(self, gz_deg_s: float, current_time: Optional[float] = None) -> bool:
        """
        Process a new gyro Z reading from the IMU.
        
        Args:
            gz_deg_s: Z-axis angular velocity in degrees per second from MPU-6050.
            current_time: Timestamp in seconds (uses time.time() if None).
            
        Returns:
            True if calibrated and integrated, False if still in calibration phase.
        """
        if current_time is None:
            current_time = time.time()

        gz_rad_s = math.radians(gz_deg_s)

        # Calibration phase
        if not self.is_calibrated:
            self._gyro_z_sum += gz_rad_s
            self._samples_collected += 1
            if self._samples_collected >= self.calib_samples:
                self.gyro_bias_z = self._gyro_z_sum / self._samples_collected
                self.is_calibrated = True
                self.last_update_time = current_time
            return False

        # Integration phase
        if self.last_update_time is None:
            self.last_update_time = current_time
            return True

        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Guard against abnormal dt (e.g. pause or clock skip)
        if dt <= 0.0 or dt > 0.5:
            return True

        # Subtract zero-bias drift
        omega_z_clean = gz_rad_s - self.gyro_bias_z
        self.theta_robot = wrap_to_pi(self.theta_robot + omega_z_clean * dt)
        return True

    def update_command(self, omega_cmd: float, dt: float = 0.02) -> None:
        """
        Update the target heading using commanded angular velocity (Course-Lock).
        
        If external target mode is active, this does not overwrite theta_target.
        Otherwise:
        - If |omega_cmd| < omega_deadband: Course-Lock is active, theta_target remains fixed.
        - If |omega_cmd| >= omega_deadband: User/planner is steering; theta_target advances with omega_cmd.
        
        Args:
            omega_cmd: Commanded angular velocity in rad/s.
            dt: Time step in seconds.
        """
        if self.external_target_mode:
            return

        if abs(omega_cmd) < self.omega_deadband:
            self.course_locked = True
        else:
            self.course_locked = False
            self.theta_target = wrap_to_pi(self.theta_target + omega_cmd * dt)

    def set_target_heading(self, target_rad: float) -> None:
        """
        Explicitly set target heading (e.g. towards carrot waypoint from global planner).
        Enables external target mode.
        """
        self.external_target_mode = True
        self.course_locked = False
        self.theta_target = wrap_to_pi(target_rad)

    def clear_external_target(self) -> None:
        """Revert back to Course-Lock teleop tracking mode."""
        self.external_target_mode = False
        self.theta_target = self.theta_robot
        self.course_locked = True

    def reset_heading(self, yaw_rad: float = 0.0) -> None:
        """Reset both robot yaw and target yaw to a specific angle."""
        self.theta_robot = wrap_to_pi(yaw_rad)
        self.theta_target = wrap_to_pi(yaw_rad)
        self.course_locked = True
        self.external_target_mode = False

    def get_heading_difference(self) -> float:
        """
        Compute the heading error: Delta_theta = theta_target - theta_robot.
        Wrapped strictly to [-pi, pi].
        
        Returns:
            Delta_theta in radians in [-pi, pi].
        """
        return wrap_to_pi(self.theta_target - self.theta_robot)

    def get_normalized_heading_error(self) -> float:
        """
        Returns normalized heading error for obs[73]:
        obs[73] = clip(Delta_theta / pi, -1.0, 1.0)
        """
        delta_theta = self.get_heading_difference()
        norm_val = delta_theta / math.pi
        return max(-1.0, min(1.0, norm_val))

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns diagnostic telemetry dictionary."""
        return {
            "calibrated": self.is_calibrated,
            "calib_progress": f"{self._samples_collected}/{self.calib_samples}",
            "gyro_bias_z_rad_s": self.gyro_bias_z,
            "theta_robot_rad": self.theta_robot,
            "theta_robot_deg": math.degrees(self.theta_robot),
            "theta_target_rad": self.theta_target,
            "theta_target_deg": math.degrees(self.theta_target),
            "delta_theta_rad": self.get_heading_difference(),
            "delta_theta_deg": math.degrees(self.get_heading_difference()),
            "normalized_obs_73": self.get_normalized_heading_error(),
            "course_locked": self.course_locked,
            "external_target": self.external_target_mode,
        }
