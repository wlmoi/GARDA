"""
Global Path and Lookahead Carrot Tracker for JetAuto Mecanum.
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

from typing import Tuple, List, Optional
import numpy as np


class GlobalPath:
    """
    Continuous or discretized 2D global path with interpolation,
    closest point projection, and lookahead point extraction.
    """

    def __init__(self, waypoints: np.ndarray, num_interp: int = 300):
        """
        waypoints: Nx2 array of (x, y) coordinates
        """
        self.raw_waypoints = np.array(waypoints, dtype=np.float32)
        self.num_interp = num_interp
        self._interpolate_path()

    def _interpolate_path(self):
        """ Linear / cumulative distance parameterization interpolation """
        diffs = np.diff(self.raw_waypoints, axis=0)
        seg_lengths = np.hypot(diffs[:, 0], diffs[:, 1])
        s = np.concatenate([[0.0], np.cumsum(seg_lengths)])
        self.total_length = float(s[-1])

        s_dense = np.linspace(0.0, self.total_length, self.num_interp)
        dense_x = np.interp(s_dense, s, self.raw_waypoints[:, 0])
        dense_y = np.interp(s_dense, s, self.raw_waypoints[:, 1])
        self.points = np.stack([dense_x, dense_y], axis=1)

    def find_closest_index(self, robot_x: float, robot_y: float) -> int:
        """ Find index of closest point on path to current robot position """
        dists = np.hypot(self.points[:, 0] - robot_x, self.points[:, 1] - robot_y)
        return int(np.argmin(dists))

    def compute_cross_track_error(self, robot_x: float, robot_y: float) -> float:
        """ Compute minimum orthogonal distance from robot position to global path """
        dists = np.hypot(self.points[:, 0] - robot_x, self.points[:, 1] - robot_y)
        return float(np.min(dists))

    def get_lookahead_point(
        self,
        robot_x: float,
        robot_y: float,
        lookahead_dist: float = 0.60
    ) -> Tuple[float, float, float, bool]:
        """
        Find target carrot point at lookahead_dist ahead of robot along the path.
        Returns (target_x, target_y, dist_to_goal, is_near_goal).
        """
        closest_idx = self.find_closest_index(robot_x, robot_y)
        n = len(self.points)

        # Walk forward from closest index until distance >= lookahead_dist
        accum_dist = 0.0
        target_idx = closest_idx

        for i in range(closest_idx, n - 1):
            seg_d = np.hypot(self.points[i+1, 0] - self.points[i, 0], self.points[i+1, 1] - self.points[i, 1])
            accum_dist += seg_d
            target_idx = i + 1
            if accum_dist >= lookahead_dist:
                break

        target_x, target_y = self.points[target_idx]
        goal_x, goal_y = self.points[-1]
        dist_to_goal = float(np.hypot(goal_x - robot_x, goal_y - robot_y))
        is_near_goal = dist_to_goal < 0.25

        return float(target_x), float(target_y), dist_to_goal, is_near_goal


class LookaheadCarrotTracker:
    """
    Nominal Path Following Controller for Holonomic Mecanum Chassis.
    Generates nominal (cmd_vx, cmd_vy, cmd_omega) towards the lookahead point.
    """

    def __init__(
        self,
        global_path: GlobalPath,
        cruise_speed: float = 0.45,
        lookahead_dist: float = 0.65,
        kp_heading: float = 2.2,
        kp_lateral: float = 1.4
    ):
        self.path = global_path
        self.cruise_speed = cruise_speed
        self.lookahead_dist = lookahead_dist
        self.kp_heading = kp_heading
        self.kp_lateral = kp_lateral

    def compute_nominal_twist(
        self,
        robot_pose: Tuple[float, float, float]
    ) -> Tuple[float, float, float, float, float, bool]:
        """
        Computes nominal commanded twist (cmd_vx, cmd_vy, cmd_omega) to follow the path.

        Returns:
            (cmd_vx, cmd_vy, cmd_omega, heading_err, dist_to_goal, goal_reached)
        """
        rx, ry, ryaw = robot_pose
        target_x, target_y, dist_to_goal, is_near_goal = self.path.get_lookahead_point(
            rx, ry, self.lookahead_dist
        )

        if dist_to_goal < 0.20:
            # Goal reached!
            return 0.0, 0.0, 0.0, 0.0, dist_to_goal, True

        # Desired heading to lookahead point
        desired_yaw = np.arctan2(target_y - ry, target_x - rx)
        heading_err = float((desired_yaw - ryaw + np.pi) % (2.0 * np.pi) - np.pi)

        # Smooth deceleration ramp near goal
        if dist_to_goal < 1.0:
            speed = max(0.12, self.cruise_speed * (dist_to_goal / 1.0))
        else:
            speed = self.cruise_speed

        # Convert target direction into Robot Body Frame
        cos_y = np.cos(ryaw)
        sin_y = np.sin(ryaw)
        dx_world = target_x - rx
        dy_world = target_y - ry
        dx_body = dx_world * cos_y + dy_world * sin_y
        dy_body = -dx_world * sin_y + dy_world * cos_y

        dist_body = np.hypot(dx_body, dy_body)
        if dist_body > 1e-4:
            unit_vx = dx_body / dist_body
            unit_vy = dy_body / dist_body
        else:
            unit_vx, unit_vy = 1.0, 0.0

        # Nominal holonomic commands
        cmd_vx = float(np.clip(speed * unit_vx, -0.15, 0.60))
        cmd_vy = float(np.clip(speed * unit_vy * self.kp_lateral, -0.40, 0.40))
        cmd_omega = float(np.clip(self.kp_heading * heading_err, -1.8, 1.8))

        return cmd_vx, cmd_vy, cmd_omega, heading_err, dist_to_goal, False
