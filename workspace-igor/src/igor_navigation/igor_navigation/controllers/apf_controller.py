"""
Standalone Artificial Potential Field (APF) Controller
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

import time
from typing import Dict, Any, Tuple, Optional, List
import numpy as np

from .base_controller import BaseController


class APFController(BaseController):
    """
    Standalone Reactive Artificial Potential Field (APF) Controller.
    Computes repulsive force vector directly from 64 frontal LiDAR beams.
    """

    def __init__(
        self,
        d_safe: float = 1.30,
        k_rep: float = 0.40,
        name: str = "APF (Artificial Potential Field)"
    ):
        super().__init__(name=name)
        self.d_safe = d_safe
        self.k_rep = k_rep
        self.num_rays = 64
        self.lidar_angles = np.linspace(-np.pi / 2.0, np.pi / 2.0, self.num_rays)

    def predict(
        self,
        lidar_ranges: np.ndarray,
        cmd_vel: Tuple[float, float, float],
        imu_data: Optional[Tuple[float, float, float, float, float, float]] = None,
        heading_err: float = 0.0,
        obstacles: Optional[List[Any]] = None,
        robot_pose: Optional[Tuple[float, float, float]] = None,
    ) -> Tuple[float, float, float, Dict[str, Any]]:
        t0 = time.perf_counter()

        # In meters:
        if np.max(lidar_ranges) <= 1.0:
            ranges_m = lidar_ranges * 3.50
        else:
            ranges_m = lidar_ranges
        d_min = float(np.min(ranges_m))

        allowed_vx = self.compute_speed_envelope(d_min)
        alpha = self.compute_gating_alpha(d_min)

        cmd_vx, cmd_vy, cmd_omega = cmd_vel
        nom_vx = min(cmd_vx, allowed_vx)

        # Compute repulsive force from all rays within d_safe
        f_rep_x = 0.0
        f_rep_y = 0.0

        for i in range(self.num_rays):
            dist = float(ranges_m[i])
            if dist < self.d_safe:
                angle = self.lidar_angles[i]
                mag = self.k_rep * ((1.0 / max(0.18, dist)) - (1.0 / self.d_safe)) / (dist**2)
                f_rep_x -= mag * np.cos(angle)
                f_rep_y -= mag * np.sin(angle)

        delta_vx_max = 0.30
        delta_vy_max = 0.45
        delta_omega_max = 0.80

        # Action mapping
        delta_vx = float(np.clip(f_rep_x, -delta_vx_max, delta_vx_max))
        delta_vy = float(np.clip(f_rep_y, -delta_vy_max, delta_vy_max))
        delta_omega = float(np.clip(-1.5 * f_rep_y, -delta_omega_max, delta_omega_max))

        exec_vx = float(np.clip(nom_vx + alpha * delta_vx, self.min_cmd_vx, allowed_vx))
        exec_vy = float(np.clip(cmd_vy + alpha * delta_vy, -self.max_cmd_vy, self.max_cmd_vy))
        exec_omega = float(np.clip(cmd_omega + alpha * delta_omega, -self.max_cmd_omega, self.max_cmd_omega))

        if d_min < 0.22 and exec_vx > 0.0:
            exec_vx = 0.0

        latency_ms = (time.perf_counter() - t0) * 1000.0
        self.last_latency_ms = latency_ms

        info = {
            "algorithm": self.name,
            "d_min": d_min,
            "alpha": alpha,
            "allowed_vx": allowed_vx,
            "f_rep": (f_rep_x, f_rep_y),
            "delta_twist": (delta_vx, delta_vy, delta_omega),
            "latency_ms": latency_ms,
            "shield_active": False,
            "shield_type": "none",
            "shield_message": "APF ACTIVE"
        }

        return exec_vx, exec_vy, exec_omega, info
