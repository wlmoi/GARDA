"""
Mecanum Kinematics for Hiwonder JetAuto
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

import numpy as np
from typing import Tuple, Optional


class MecanumKinematics:
    """
    Kinematic model for 4-wheel drive Mecanum chassis (Hiwonder JetAuto).
    L: Wheelbase = 0.216 m (216 mm)
    W: Track Width = 0.195 m (195 mm)
    D: Wheel Diameter = 0.0965 m (96.5 mm)
    R: Wheel Radius = 0.04825 m
    k: Arm Geometry = (L + W) / 2 = 0.2055 m
    """

    def __init__(
        self,
        wheelbase: float = 0.216,
        track_width: float = 0.195,
        wheel_diameter: float = 0.0965,
        max_rps: float = 3.0
    ):
        self.wheelbase = wheelbase
        self.track_width = track_width
        self.wheel_diameter = wheel_diameter
        self.wheel_radius = wheel_diameter / 2.0
        self.wheel_circ = np.pi * wheel_diameter
        self.geom_arm = (wheelbase + track_width) / 2.0  # 0.2055 m
        self.max_rps = max_rps

    def inverse_kinematics(
        self,
        vx: float,
        vy: float,
        omega: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert chassis twist (vx, vy, omega) to 4 wheel velocities and motor RPS:
        [v_fl, v_rl, v_fr, v_rr] and [rps_fl, rps_rl, rps_fr, rps_rr]
        """
        vp = omega * self.geom_arm
        v_fl = vx - vy - vp
        v_rl = vx + vy - vp
        v_fr = vx + vy + vp
        v_rr = vx - vy + vp

        wheel_linear_vel = np.array([v_fl, v_rl, v_fr, v_rr], dtype=np.float32)
        raw_rps = wheel_linear_vel / self.wheel_circ

        # Scale down if any wheel exceeds max RPS
        max_motor_rps = float(np.max(np.abs(raw_rps)))
        if max_motor_rps > self.max_rps:
            scale = self.max_rps / max_motor_rps
            motor_rps = raw_rps * scale
        else:
            motor_rps = raw_rps

        return wheel_linear_vel, motor_rps

    def forward_kinematics(
        self,
        motor_rps: np.ndarray,
        slip_factors: Optional[np.ndarray] = None
    ) -> Tuple[float, float, float]:
        """
        Convert 4 motor RPS to chassis velocities (vx, vy, omega).
        Optional slip_factors array of 4 floats (for domain randomization simulation).
        """
        if slip_factors is not None:
            effective_rps = motor_rps * slip_factors
        else:
            effective_rps = motor_rps

        v_tang = effective_rps * self.wheel_circ
        v_fl, v_rl, v_fr, v_rr = v_tang

        vx = float((v_fl + v_rl + v_fr + v_rr) / 4.0)
        vy = float((-v_fl + v_rl + v_fr - v_rr) / 4.0)
        omega = float((-v_fl - v_rl + v_fr + v_rr) / (4.0 * self.geom_arm))

        return vx, vy, omega
