"""
CL-DRL Controller (PPO Gated Residual with Asymmetric Braking & Hard Zero-Stop Envelope)
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

import os
import json
import time
from typing import Dict, Any, Tuple, Optional, List
import numpy as np

from .base_controller import BaseController


class CLDRLController(BaseController):
    """
    Closed-Loop Deep Reinforcement Learning (CL-DRL) Controller.
    Implements Shared Autonomy Gated Residual Policy with asymmetric braking authority.
    """

    def __init__(
        self,
        weights_path: Optional[str] = None,
        use_torch: bool = False,
        use_onnx: bool = False,
        name: str = "CL-DRL (PPO Gated Residual)"
    ):
        super().__init__(name=name)

        # Default weights search path
        default_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weights"))
        if weights_path is None:
            json_candidate = os.path.join(default_dir, "model_weights.json")
            zip_candidate = os.path.join(default_dir, "ppo_jetauto_residual_fp32.zip")
            onnx_candidate = os.path.join(default_dir, "cl_drl_jetauto_residual_fp32.onnx")

            if use_onnx and os.path.exists(onnx_candidate):
                weights_path = onnx_candidate
            elif use_torch and os.path.exists(zip_candidate):
                weights_path = zip_candidate
            elif os.path.exists(json_candidate):
                weights_path = json_candidate
            elif os.path.exists(zip_candidate):
                weights_path = zip_candidate
            else:
                raise FileNotFoundError(f"No valid weights found in {default_dir}")

        self.weights_path = weights_path
        self.backend = "numpy"
        self._load_weights()

        # Telemetry variables
        self.last_alpha = 0.0
        self.last_delta = (0.0, 0.0, 0.0)
        self.last_allowed_vx = 0.60

    def _load_weights(self):
        """ Load network weights from JSON, ONNX, or PyTorch ZIP """
        if self.weights_path.endswith(".json"):
            with open(self.weights_path, "r") as f:
                w = json.load(f)
            self.w1 = np.array(w["w1"], dtype=np.float32)  # (128, 74)
            self.b1 = np.array(w["b1"], dtype=np.float32)  # (128,)
            self.w2 = np.array(w["w2"], dtype=np.float32)  # (64, 128)
            self.b2 = np.array(w["b2"], dtype=np.float32)  # (64,)
            self.w3 = np.array(w["w3"], dtype=np.float32)  # (3, 64)
            self.b3 = np.array(w["b3"], dtype=np.float32)  # (3,)
            self.backend = "numpy"

        elif self.weights_path.endswith(".zip"):
            try:
                from stable_baselines3 import PPO
                self.torch_model = PPO.load(self.weights_path, device="cpu")
                # Also extract numpy weights for ultra-low latency fallback
                policy_net = self.torch_model.policy.mlp_extractor.policy_net
                action_net = self.torch_model.policy.action_net
                self.w1 = policy_net[0].weight.detach().cpu().numpy()
                self.b1 = policy_net[0].bias.detach().cpu().numpy()
                self.w2 = policy_net[2].weight.detach().cpu().numpy()
                self.b2 = policy_net[2].bias.detach().cpu().numpy()
                self.w3 = action_net.weight.detach().cpu().numpy()
                self.b3 = action_net.bias.detach().cpu().numpy()
                self.backend = "torch_or_numpy"
            except Exception as e:
                raise RuntimeError(f"Failed to load PyTorch model from {self.weights_path}: {e}")

        elif self.weights_path.endswith(".onnx"):
            try:
                import onnxruntime as ort
                self.ort_session = ort.InferenceSession(self.weights_path)
                self.ort_input_name = self.ort_session.get_inputs()[0].name
                self.backend = "onnx"
            except Exception as e:
                raise RuntimeError(f"Failed to load ONNX model from {self.weights_path}: {e}")
        else:
            raise ValueError(f"Unsupported weights format: {self.weights_path}")

    def forward_mlp(self, obs74: np.ndarray) -> np.ndarray:
        """
        Pure NumPy forward inference: 74 -> 128 (ReLU) -> 64 (ReLU) -> 3 (Clip [-1, 1])
        Execution latency: ~0.05 ms.
        """
        if self.backend == "onnx":
            inp = obs74.reshape(1, -1).astype(np.float32)
            out = self.ort_session.run(None, {self.ort_input_name: inp})
            return np.clip(out[0].flatten()[:3], -1.0, 1.0)

        # Standard pure NumPy forward pass
        h1 = np.maximum(0.0, np.dot(self.w1, obs74) + self.b1)
        h2 = np.maximum(0.0, np.dot(self.w2, h1) + self.b2)
        action = np.dot(self.w3, h2) + self.b3
        return np.clip(action, -1.0, 1.0)

    def build_observation(
        self,
        lidar_ranges: np.ndarray,
        cmd_vel: Tuple[float, float, float],
        imu_data: Optional[Tuple[float, float, float, float, float, float]] = None,
        heading_err: float = 0.0
    ) -> np.ndarray:
        """
        Construct standard 74-dimensional observation vector:
        - 0..63: 64 frontal lidar beams normalized to [0, 1] (capped at 3.5m)
        - 64..69: 6-DOF IMU telemetry [ax, ay, az, gx, gy, gz] normalized
        - 70..72: Commanded twist [cmd_vx/0.60, cmd_vy/0.50, cmd_omega/2.0]
        - 73: Heading error normalized [heading_err / pi]
        """
        # Ensure 64 beams in range [0.0, 1.0]
        if np.max(lidar_ranges) > 1.5:
            # Ranges provided in meters
            norm_lidar = np.clip(lidar_ranges / 3.50, 0.0, 1.0).astype(np.float32)
        else:
            norm_lidar = np.clip(lidar_ranges, 0.0, 1.0).astype(np.float32)

        if len(norm_lidar) != 64:
            raise ValueError(f"Expected 64 LiDAR beams, got {len(norm_lidar)}")

        if imu_data is not None and len(imu_data) >= 6:
            ax, ay, az, gx, gy, gz = imu_data[:6]
            norm_imu = np.array([
                np.clip(ax / 3.0, -1.0, 1.0),
                np.clip(ay / 3.0, -1.0, 1.0),
                np.clip(az / 9.81, -1.0, 1.0),
                np.clip(gx / 2.0, -1.0, 1.0),
                np.clip(gy / 2.0, -1.0, 1.0),
                np.clip(gz / 2.0, -1.0, 1.0),
            ], dtype=np.float32)
        else:
            norm_imu = np.zeros(6, dtype=np.float32)

        norm_cmd = np.array([
            np.clip(cmd_vel[0] / self.max_cmd_vx, -1.0, 1.0),
            np.clip(cmd_vel[1] / self.max_cmd_vy, -1.0, 1.0),
            np.clip(cmd_vel[2] / self.max_cmd_omega, -1.0, 1.0),
        ], dtype=np.float32)

        norm_head = np.array([np.clip(heading_err / np.pi, -1.0, 1.0)], dtype=np.float32)

        return np.concatenate([norm_lidar, norm_imu, norm_cmd, norm_head]).astype(np.float32)

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

        # Dynamic Speed Envelope & Hard Zero-Stop
        allowed_vx = self.compute_speed_envelope(d_min)
        alpha = self.compute_gating_alpha(d_min)

        # Build observation and forward through policy
        obs74 = self.build_observation(ranges_m, cmd_vel, imu_data, heading_err)
        action = self.forward_mlp(obs74)

        # Asymmetric Braking Authority
        # Brake has high authority (-0.60 m/s) to cancel forward speed; forward acceleration is limited (+0.15 m/s)
        delta_vx = float(action[0] * 0.60 if action[0] < 0 else action[0] * 0.15)
        delta_vy = float(action[1] * 0.45)
        delta_omega = float(action[2] * 0.80)

        nom_vx = min(cmd_vel[0], allowed_vx)
        nom_vy = cmd_vel[1]
        nom_omega = cmd_vel[2]

        exec_vx = float(np.clip(nom_vx + alpha * delta_vx, self.min_cmd_vx, allowed_vx))
        exec_vy = float(np.clip(nom_vy + alpha * delta_vy, -self.max_cmd_vy, self.max_cmd_vy))
        exec_omega = float(np.clip(nom_omega + alpha * delta_omega, -self.max_cmd_omega, self.max_cmd_omega))

        # Critical zero-stop override
        if d_min < 0.22 and exec_vx > 0.0:
            exec_vx = 0.0

        latency_ms = (time.perf_counter() - t0) * 1000.0
        self.last_latency_ms = latency_ms
        self.last_alpha = alpha
        self.last_delta = (delta_vx, delta_vy, delta_omega)
        self.last_allowed_vx = allowed_vx

        info = {
            "algorithm": self.name,
            "d_min": d_min,
            "alpha": alpha,
            "allowed_vx": allowed_vx,
            "delta_twist": (delta_vx, delta_vy, delta_omega),
            "raw_action": action,
            "latency_ms": latency_ms,
            "shield_active": False,
            "shield_type": "none",
            "shield_message": "PASS (DRL CLEAR)" if alpha < 0.05 else "CL-DRL INTERVENING"
        }

        return exec_vx, exec_vy, exec_omega, info
