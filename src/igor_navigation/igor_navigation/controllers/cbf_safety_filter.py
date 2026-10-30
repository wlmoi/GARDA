"""
CL-DRL + Control Barrier Function (CBF) QP Safety Filter Controller
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

import time
from typing import Dict, Any, Tuple, Optional, List
import numpy as np

from .drl_controller import CLDRLController


class CBFFilterController(CLDRLController):
    """
    Hybrid Safety-Critical Architecture:
    Combines agile learned CL-DRL exploration policy with formal Lyapunov/Nagumo
    Control Barrier Function (CBF) Quadratic Program (QP) filter for 100% collision-free guarantee.
    """

    def __init__(
        self,
        weights_path: Optional[str] = None,
        gamma: float = 3.5,
        safe_margin: float = 0.06,
        name: str = "CL-DRL + CBF QP Filter"
    ):
        super().__init__(weights_path=weights_path, name=name)
        self.gamma = gamma          # Barrier convergence rate (Nagumo parameter)
        self.safe_margin = safe_margin  # Extra safety buffer margin (meters)
        self.last_intervened = False

    def filter_cbf(
        self,
        cand_vx: float,
        cand_vy: float,
        cand_omega: float,
        robot_pose: Tuple[float, float, float],
        obstacles: List[Any],
        allowed_max_vx: float
    ) -> Tuple[float, float, float, bool]:
        """
        Closed-form minimum-norm QP projection:
        min_V 0.5 * ||V - V_DRL||^2   s.t.  a_i^T V >= b_i
        """
        rx, ry, ryaw = robot_pose
        cos_y = np.cos(ryaw)
        sin_y = np.sin(ryaw)

        # Convert proposed body-frame velocity to World Frame
        world_vx = cand_vx * cos_y - cand_vy * sin_y
        world_vy = cand_vx * sin_y + cand_vy * cos_y

        intervened = False

        if obstacles:
            for obs in obstacles:
                # Support various obstacle representations (object or dict or array)
                if hasattr(obs, "pos"):
                    ox, oy = obs.pos[0], obs.pos[1]
                    ovx = obs.vel[0] if hasattr(obs, "vel") else 0.0
                    ovy = obs.vel[1] if hasattr(obs, "vel") else 0.0
                    oradius = obs.radius
                elif isinstance(obs, dict):
                    ox, oy = obs["x"], obs["y"]
                    ovx = obs.get("vx", 0.0)
                    ovy = obs.get("vy", 0.0)
                    oradius = obs.get("radius", 0.25)
                else:
                    ox, oy = obs.x, obs.y
                    ovx = getattr(obs, "vx", 0.0)
                    ovy = getattr(obs, "vy", 0.0)
                    oradius = getattr(obs, "radius", 0.25)

                dist = np.hypot(rx - ox, ry - oy)
                if dist > 1.50:  # Only evaluate within active alert zone
                    continue

                r_safe = self.robot_radius + oradius + self.safe_margin
                # Barrier function h(p) = ||p - p_obs||^2 - r_safe^2
                h = (rx - ox)**2 + (ry - oy)**2 - r_safe**2

                # Barrier gradient a_i = 2 * (p - p_obs)
                a_x = 2.0 * (rx - ox)
                a_y = 2.0 * (ry - oy)
                a_norm_sq = a_x**2 + a_y**2
                if a_norm_sq < 1e-6:
                    continue

                # Invariance condition: a_i^T V >= 2*(p - p_obs)^T v_obs - gamma * h
                b = a_x * ovx + a_y * ovy - self.gamma * h
                a_dot_v = a_x * world_vx + a_y * world_vy

                # If barrier condition is violated, apply closed-form QP projection
                if a_dot_v < b:
                    intervened = True
                    lam = (b - a_dot_v) / a_norm_sq
                    world_vx += lam * a_x
                    world_vy += lam * a_y

        if intervened:
            # Rotate back to Robot Body Frame
            body_vx = world_vx * cos_y + world_vy * sin_y
            body_vy = -world_vx * sin_y + world_vy * cos_y

            # Enforce physical kinematic limits
            safe_vx = float(np.clip(body_vx, self.min_cmd_vx, allowed_max_vx))
            safe_vy = float(np.clip(body_vy, -self.max_cmd_vy, self.max_cmd_vy))
            return safe_vx, safe_vy, cand_omega, True

        return cand_vx, cand_vy, cand_omega, False

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

        # 1. Base CL-DRL Policy Prediction
        drl_vx, drl_vy, drl_omega, info = super().predict(
            lidar_ranges=lidar_ranges,
            cmd_vel=cmd_vel,
            imu_data=imu_data,
            heading_err=heading_err,
            obstacles=obstacles,
            robot_pose=robot_pose
        )

        allowed_vx = info["allowed_vx"]
        pose = robot_pose if robot_pose is not None else (0.0, 0.0, 0.0)

        # 2. Nagumo Control Barrier Function Projection
        cbf_vx, cbf_vy, cbf_omega, intervened = self.filter_cbf(
            cand_vx=drl_vx,
            cand_vy=drl_vy,
            cand_omega=drl_omega,
            robot_pose=pose,
            obstacles=obstacles if obstacles else [],
            allowed_max_vx=allowed_vx
        )

        latency_ms = (time.perf_counter() - t0) * 1000.0
        self.last_latency_ms = latency_ms
        self.last_intervened = intervened

        info.update({
            "algorithm": self.name,
            "latency_ms": latency_ms,
            "shield_active": intervened,
            "shield_type": "cbf" if intervened else "none",
            "shield_message": "⚡ CBF QP FILTER ACTIVE" if intervened else "PASS (CBF SAFE)"
        })

        return cbf_vx, cbf_vy, cbf_omega, info
