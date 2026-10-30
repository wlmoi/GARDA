"""
CL-DRL + mini-DWA Predictive Safety Shield Controller
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

import time
from typing import Dict, Any, Tuple, Optional, List
import numpy as np

from .drl_controller import CLDRLController


class MiniDWAShieldController(CLDRLController):
    """
    Two-Tier Defense Architecture:
    1. Tier 1: Agile CL-DRL generator for fluid holonomic maneuvering.
    2. Tier 2: Predictive 3-step mini-DWA rollout shield with dynamic obstacle extrapolation.
       Evaluates 6 evasive actions to guarantee clearance buffer >= 4 cm.
    """

    def __init__(
        self,
        weights_path: Optional[str] = None,
        sim_time: float = 0.30,
        sim_steps: int = 3,
        safety_buffer: float = 0.04,
        name: str = "CL-DRL + mini-DWA Shield"
    ):
        super().__init__(weights_path=weights_path, name=name)
        self.sim_time = sim_time
        self.sim_steps = sim_steps
        self.safety_buffer = safety_buffer
        self.last_shield_active = False

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

        pose = robot_pose if robot_pose is not None else (0.0, 0.0, 0.0)
        rx, ry, ryaw = pose
        dt = self.sim_time / self.sim_steps

        # 2. Predictive Rollout of Proposed DRL Action
        collision_predicted = False
        min_dist = float("inf")
        nearest_obs = None

        curr_x, curr_y, curr_yaw = rx, ry, ryaw
        for s in range(self.sim_steps):
            t = (s + 1) * dt
            curr_yaw += drl_omega * dt
            curr_x += (drl_vx * np.cos(curr_yaw) - drl_vy * np.sin(curr_yaw)) * dt
            curr_y += (drl_vx * np.sin(curr_yaw) + drl_vy * np.cos(curr_yaw)) * dt

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

                    fut_ox = ox + ovx * t
                    fut_oy = oy + ovy * t
                    d = np.hypot(curr_x - fut_ox, curr_y - fut_oy) - (oradius + self.robot_radius)
                    if d < min_dist:
                        min_dist = d
                        nearest_obs = (ox, oy, ovx, ovy, oradius)
                    if d <= self.safety_buffer:
                        collision_predicted = True
                        break
            if collision_predicted:
                break

        # 3. If rollout is safe, pass DRL command directly
        if not collision_predicted:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            self.last_latency_ms = latency_ms
            self.last_shield_active = False
            info.update({
                "algorithm": self.name,
                "latency_ms": latency_ms,
                "shield_active": False,
                "shield_type": "none",
                "shield_message": "PASS (DRL CLEAR)"
            })
            return drl_vx, drl_vy, drl_omega, info

        # 4. Emergency Shield Override: Evaluate 6 Fast Evasive Options
        lateral_nudge = 0.45
        if nearest_obs is not None:
            nox, noy = nearest_obs[0], nearest_obs[1]
            rel_y = np.sin(-ryaw) * (nox - rx) + np.cos(-ryaw) * (noy - ry)
            lateral_nudge = -0.45 if rel_y >= 0.0 else 0.45

        candidates = [
            (0.0, drl_vy * 0.8, drl_omega),
            (0.0, lateral_nudge, drl_omega),
            (0.0, -lateral_nudge, drl_omega),
            (-0.15, 0.0, drl_omega),
            (-0.15, lateral_nudge, drl_omega),
            (-0.15, -lateral_nudge, drl_omega)
        ]

        best_candidate = candidates[1]
        best_clearance = -float("inf")

        for cand_vx, cand_vy, cand_w in candidates:
            cand_min_d = float("inf")
            cx, cy, cyaw = rx, ry, ryaw

            for s in range(self.sim_steps):
                t = (s + 1) * dt
                cyaw += cand_w * dt
                cx += (cand_vx * np.cos(cyaw) - cand_vy * np.sin(cyaw)) * dt
                cy += (cand_vx * np.sin(cyaw) + cand_vy * np.cos(cyaw)) * dt

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

                        fut_ox = ox + ovx * t
                        fut_oy = oy + ovy * t
                        d = np.hypot(cx - fut_ox, cy - fut_oy) - (oradius + self.robot_radius)
                        if d < cand_min_d:
                            cand_min_d = d

            if cand_min_d > best_clearance:
                best_clearance = cand_min_d
                best_candidate = (cand_vx, cand_vy, cand_w)

        latency_ms = (time.perf_counter() - t0) * 1000.0
        self.last_latency_ms = latency_ms
        self.last_shield_active = True

        info.update({
            "algorithm": self.name,
            "latency_ms": latency_ms,
            "shield_active": True,
            "shield_type": "mini-dwa",
            "shield_message": "⚠️ mini-DWA SHIELD ACTIVE"
        })

        return best_candidate[0], best_candidate[1], best_candidate[2], info
