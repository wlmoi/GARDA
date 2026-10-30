"""
Standalone Dynamic Window Approach (DWA) Controller (Anti-Freeze & Dynamic Rollout)
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

import time
from typing import Dict, Any, Tuple, Optional, List
import numpy as np

from .base_controller import BaseController


class DWAController(BaseController):
    """
    Standalone Mecanum DWA Controller with Anti-Freeze Trajectory Optimization
    and Dynamic Obstacle Velocity Extrapolation.
    """

    def __init__(
        self,
        name: str = "DWA (Anti-Freeze & Dynamic Rollout)"
    ):
        super().__init__(name=name)
        self.delta_vx_max = 0.30
        self.delta_vy_max = 0.45
        self.delta_omega_max = 0.80

        # Discrete action candidates (5 x 7 x 3 = 105 trajectories)
        self.a0_candidates = [-1.0, -0.5, 0.0, 0.5, 1.0]
        self.a1_candidates = [-1.0, -0.6, -0.3, 0.0, 0.3, 0.6, 1.0]
        self.a2_candidates = [-1.0, 0.0, 1.0]

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

        pose = robot_pose if robot_pose is not None else (0.0, 0.0, 0.0)
        rx, ry, ryaw = pose

        # Adaptive simulation horizon based on speed
        current_speed = np.hypot(cmd_vx, cmd_vy)
        sim_time = float(np.clip(0.35 + (current_speed / 0.60) * 0.25, 0.35, 0.60))
        sim_steps = 4
        dt = sim_time / sim_steps

        best_cost = float("inf")
        best_action = [0.0, 0.0, 0.0]

        # Extract parsed obstacles for fast vectorized checking
        parsed_obs = []
        if obstacles:
            for obs in obstacles:
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
                parsed_obs.append((ox, oy, ovx, ovy, oradius))

        # 105 Trajectory Evaluation Loop
        for a0 in self.a0_candidates:
            target_vx = float(np.clip(nom_vx + a0 * self.delta_vx_max, self.min_cmd_vx, allowed_vx))
            for a1 in self.a1_candidates:
                target_vy = float(np.clip(cmd_vy + a1 * self.delta_vy_max, -self.max_cmd_vy, self.max_cmd_vy))
                for a2 in self.a2_candidates:
                    target_w = float(np.clip(cmd_omega + a2 * self.delta_omega_max, -self.max_cmd_omega, self.max_cmd_omega))

                    # Forward rollout in world frame
                    cx, cy, cyaw = rx, ry, ryaw
                    min_dist_to_obs = float("inf")
                    collided = False

                    for s in range(sim_steps):
                        t = (s + 1) * dt
                        cyaw += target_w * dt
                        cx += (target_vx * np.cos(cyaw) - target_vy * np.sin(cyaw)) * dt
                        cy += (target_vx * np.sin(cyaw) + target_vy * np.cos(cyaw)) * dt

                        for ox, oy, ovx, ovy, oradius in parsed_obs:
                            fut_ox = ox + ovx * t
                            fut_oy = oy + ovy * t
                            d = np.hypot(cx - fut_ox, cy - fut_oy) - (oradius + self.robot_radius)
                            if d < min_dist_to_obs:
                                min_dist_to_obs = d
                            if d <= 0.0:
                                collided = True
                                break
                        if collided:
                            break

                    if collided:
                        cost = 1000.0
                    else:
                        track_err = (
                            2.5 * abs(target_vx - cmd_vx) +
                            2.0 * abs(target_vy - cmd_vy) +
                            0.8 * abs(target_w - cmd_omega)
                        )
                        clearance_pen = (0.15 / max(0.04, min_dist_to_obs)) if min_dist_to_obs < 0.45 else 0.0
                        effort_pen = 0.25 * (a0**2 + a1**2 + a2**2)
                        progress_inc = -0.8 * (target_vx / 0.60) if cmd_vx > 0.10 else 0.0
                        cost = track_err + clearance_pen + effort_pen + progress_inc

                    if cost < best_cost:
                        best_cost = cost
                        best_action = [a0, a1, a2]

        delta_vx = best_action[0] * self.delta_vx_max
        delta_vy = best_action[1] * self.delta_vy_max
        delta_omega = best_action[2] * self.delta_omega_max

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
            "delta_twist": (delta_vx, delta_vy, delta_omega),
            "best_action": best_action,
            "cost": best_cost,
            "latency_ms": latency_ms,
            "shield_active": False,
            "shield_type": "none",
            "shield_message": "DWA (ANTI-FREEZE ACTIVE)"
        }

        return exec_vx, exec_vy, exec_omega, info
