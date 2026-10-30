"""
Comprehensive Benchmark Metrics Evaluator for Obstacle Avoidance Algorithms.
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np


class BenchmarkMetricsTracker:
    """
    Records and calculates standardized benchmark metrics across all 5 obstacle avoidance algorithms.
    """

    def __init__(self, algorithm_name: str, optimal_path_length: float = 6.0):
        self.algo_name = algorithm_name
        self.optimal_path_length = optimal_path_length

        self.robot_trajectory: List[Tuple[float, float]] = []
        self.robot_yaws: List[float] = []
        self.cmd_vels: List[Tuple[float, float, float]] = []
        self.exec_vels: List[Tuple[float, float, float]] = []
        self.clearances: List[float] = []
        self.ctes: List[float] = []
        self.heading_errors: List[float] = []
        self.latencies: List[float] = []
        self.motor_rps_history: List[np.ndarray] = []
        self.interventions: List[bool] = []
        self.alphas: List[float] = []
        self.danger_steps = 0
        self.collided = False
        self.reached_goal = False
        self.total_steps = 0
        self.dt = 0.033

    def record_step(
        self,
        pose: Tuple[float, float, float],
        cmd_vel: Tuple[float, float, float],
        exec_vel: Tuple[float, float, float],
        d_min: float,
        cte: float,
        heading_err: float,
        latency_ms: float,
        motor_rps: np.ndarray,
        intervened: bool,
        alpha: float = 0.0,
        collided: bool = False,
        reached_goal: bool = False
    ):
        self.total_steps += 1
        self.robot_trajectory.append((pose[0], pose[1]))
        self.robot_yaws.append(pose[2])
        self.cmd_vels.append(cmd_vel)
        self.exec_vels.append(exec_vel)
        self.clearances.append(d_min)
        self.ctes.append(cte)
        self.heading_errors.append(abs(heading_err))
        self.latencies.append(latency_ms)
        self.motor_rps_history.append(motor_rps.copy())
        self.interventions.append(intervened)
        self.alphas.append(alpha)

        if d_min < 0.35:
            self.danger_steps += 1
        if collided:
            self.collided = True
        if reached_goal:
            self.reached_goal = True

    def compute_summary(self) -> Dict[str, Any]:
        """ Compute full summary dictionary of benchmark metrics """
        traj = np.array(self.robot_trajectory)
        if len(traj) > 1:
            diffs = np.diff(traj, axis=0)
            path_len = float(np.sum(np.hypot(diffs[:, 0], diffs[:, 1])))
        else:
            path_len = 0.0

        tortuosity = float(path_len / max(0.1, self.optimal_path_length))
        time_to_goal = float(self.total_steps * self.dt)
        min_clearance_cm = float(np.min(self.clearances) * 100.0) if self.clearances else 0.0
        danger_time_s = float(self.danger_steps * self.dt)

        mean_cte = float(np.mean(self.ctes)) if self.ctes else 0.0
        max_cte = float(np.max(self.ctes)) if self.ctes else 0.0
        mean_heading_err_deg = float(np.degrees(np.mean(self.heading_errors))) if self.heading_errors else 0.0

        execs = np.array(self.exec_vels) if self.exec_vels else np.zeros((1, 3))
        mean_vx = float(np.mean(execs[:, 0]))

        # Smoothness: jerk proxy
        if len(execs) > 1:
            accels = np.diff(execs[:, :2], axis=0) / self.dt
            jerks = np.diff(accels, axis=0) / self.dt if len(accels) > 1 else np.zeros(1)
            jerk_metric = float(np.mean(np.linalg.norm(jerks, axis=1))) if len(jerks) > 0 else 0.0
        else:
            jerk_metric = 0.0

        # Motor saturation percentage (|rps| >= 3.0)
        if self.motor_rps_history:
            all_rps = np.abs(np.array(self.motor_rps_history))
            motor_sat_pct = float(np.mean(all_rps >= 2.95) * 100.0)
        else:
            motor_sat_pct = 0.0

        intervention_pct = float(np.mean(self.interventions) * 100.0) if self.interventions else 0.0
        mean_latency = float(np.mean(self.latencies)) if self.latencies else 0.0
        max_latency = float(np.max(self.latencies)) if self.latencies else 0.0

        return {
            "algorithm": self.algo_name,
            "success": self.reached_goal and not self.collided,
            "collided": self.collided,
            "time_to_goal_s": round(time_to_goal, 2),
            "total_steps": self.total_steps,
            "path_length_m": round(path_len, 2),
            "tortuosity": round(tortuosity, 2),
            "min_clearance_cm": round(min_clearance_cm, 1),
            "danger_time_s": round(danger_time_s, 2),
            "mean_cte_m": round(mean_cte, 3),
            "max_cte_m": round(max_cte, 3),
            "mean_heading_err_deg": round(mean_heading_err_deg, 1),
            "mean_vx_mps": round(mean_vx, 2),
            "jerk_smoothness": round(jerk_metric, 2),
            "motor_sat_pct": round(motor_sat_pct, 1),
            "intervention_pct": round(intervention_pct, 1),
            "avg_latency_ms": round(mean_latency, 3),
            "max_latency_ms": round(max_latency, 3)
        }
