#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
retrain_ai.py - Automated CL-DRL Retraining & Multi-Algorithm Benchmark Suite
Target Platform: Hiwonder JetAuto Mecanum AMR (Project IGOR)
PERURI Chip Hackathon 2026

Features:
1. Retrains Gated Residual CL-DRL Actor-Critic policy using PPO (default: 300,000 timesteps).
2. Uses exact Notebook V3 environment: 4-stage progressive curriculum & 8 twist behavior modes.
3. Automatically updates all weight formats directly inside the package:
   - ppo_jetauto_residual_fp32.zip (PyTorch SB3)
   - cl_drl_jetauto_residual_fp32.onnx & .data (ONNX Runtime / TensorRT)
   - model_weights.json (Fast pure NumPy inference)
   - hardware/weights_q8_8.h (C-Header fixed-point Q8.8 for FPGA/C++)
   - hardware/layer{1,2,3}_{w,b}.mem (FPGA BRAM initialization hex)
4. Evaluates all 5 algorithms (CL-DRL, CBF, mini-DWA, DWA, APF) on the global path following benchmark.
5. Exports analytical comparison charts and full-duration animated GIFs directly to:
   igor_navigation/evaluations/
6. Automatically synchronizes new weights and artifacts to igor_ws (if present) and triggers colcon rebuild.

Usage:
  python3 retrain_ai.py --timesteps 300000
  python3 retrain_ai.py --timesteps 10000 --eval
  python3 -m igor_navigation.retrain_ai --timesteps 50000
"""

import os
import sys
import types
import json
import time
import shutil
import random
import argparse
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

# Suppress OpenCV NumPy 2.x incompatibilities for robotics headless environments
if 'cv2' not in sys.modules:
    dummy_cv2 = types.ModuleType('cv2')
    dummy_cv2.ocl = types.SimpleNamespace(setUseOpenCL=lambda x: None)
    sys.modules['cv2'] = dummy_cv2

import numpy as np
import torch
import gymnasium as gym
from gymnasium import spaces

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv

# Package path resolution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from igor_navigation import (
    WEIGHTS_DIR,
    HARDWARE_DIR,
    create_controller,
    MecanumKinematics,
    GlobalPath,
    LookaheadCarrotTracker,
    BenchmarkMetricsTracker
)

EVALUATIONS_DIR = os.path.join(CURRENT_DIR, "evaluations")
os.makedirs(EVALUATIONS_DIR, exist_ok=True)


# ==============================================================================
# 1. SIMULATION ENVIRONMENT: 8 TWIST MODES & 4 CURRICULUM STAGES
# ==============================================================================

class DynamicObstacle:
    """Representation of static or dynamic moving obstacle."""
    def __init__(self, pos, radius, vel=None, bounds=None):
        self.pos = np.array(pos, dtype=np.float32)
        self.radius = float(radius)
        self.vel = np.array(vel if vel is not None else [0.0, 0.0], dtype=np.float32)
        self.bounds = bounds if bounds is not None else [0.5, 5.0, -2.0, 2.0]

    def update(self, dt: float):
        if np.linalg.norm(self.vel) > 1e-4:
            self.pos += self.vel * dt
            if self.pos[0] < self.bounds[0] or self.pos[0] > self.bounds[1]:
                self.vel[0] *= -1.0
                self.pos[0] = np.clip(self.pos[0], self.bounds[0], self.bounds[1])
            if self.pos[1] < self.bounds[2] or self.pos[1] > self.bounds[3]:
                self.vel[1] *= -1.0
                self.pos[1] = np.clip(self.pos[1], self.bounds[2], self.bounds[3])


class JetAutoResidualAvoidanceEnvV3(gym.Env):
    """
    Gymnasium Environment Version 3.0:
    - 8 Twist Command Modes
    - 4-Stage Progressive Curriculum
    - Bit-True JetAuto Mecanum Kinematics
    - Gated Residual Action Space
    """
    metadata = {'render_modes': ['human']}

    def __init__(self, curriculum_enabled: bool = True, target_total_timesteps: int = 300000):
        super(JetAutoResidualAvoidanceEnvV3, self).__init__()

        # Chassis specifications
        self.wheelbase = 0.216
        self.track_width = 0.195
        self.wheel_diameter = 0.0965
        self.robot_radius = 0.22
        self.wheel_circ = np.pi * self.wheel_diameter
        self.geom_arm = (self.wheelbase + self.track_width) / 2.0
        self.max_rps = 3.0
        self.dt = 0.033

        # LiDAR specification
        self.num_lidar_rays = 64
        self.min_lidar_range = 0.15
        self.max_lidar_range = 3.50
        self.lidar_offset_x = 0.096
        self.lidar_angles = np.linspace(-np.pi / 2.0, np.pi / 2.0, self.num_lidar_rays)

        # Limits
        self.max_cmd_vx = 0.60
        self.min_cmd_vx = -0.15
        self.max_cmd_vy = 0.50
        self.max_cmd_omega = 2.0

        # Residual action scales
        self.delta_vx_max = 0.30
        self.delta_vy_max = 0.45
        self.delta_omega_max = 0.80

        # Gating
        self.d_safe_gate = 1.40
        self.d_crit_gate = 0.35
        self.d_env_safe = 1.20
        self.d_env_crit = 0.35
        self.allowed_max_vx = 0.60

        # Spaces
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(74,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(3,), dtype=np.float32)

        # State
        self.robot_pos = np.array([0.0, 0.0], dtype=np.float32)
        self.robot_yaw = 0.0
        self.target_yaw = 0.0
        self.robot_vel = np.array([0.0, 0.0], dtype=np.float32)
        self.robot_omega = 0.0
        self.prev_robot_vel = np.array([0.0, 0.0], dtype=np.float32)
        self.obstacles: List[DynamicObstacle] = []
        self.current_twist_mode = "cruise"
        self.twist_mode_timer = 0.0

        # Curriculum State
        self.curriculum_enabled = curriculum_enabled
        self.target_total_timesteps = target_total_timesteps
        self.global_step_counter = 0
        self.current_stage = 1
        self.domain_randomization_enabled = False
        self.wheel_slip_factors = np.ones(4, dtype=np.float32)

        self.step_count = 0
        self.max_steps = 400

    def sample_twist_command(self) -> Tuple[float, float, float]:
        r = np.random.rand()
        if r < 0.30:
            self.current_twist_mode = "cruise"
            vx = np.random.uniform(0.35, self.max_cmd_vx)
            vy = np.random.uniform(-0.05, 0.05)
            w = np.random.uniform(-0.15, 0.15)
        elif r < 0.45:
            self.current_twist_mode = "lateral_strafe"
            vx = np.random.uniform(-0.05, 0.10)
            vy = np.random.choice([-1, 1]) * np.random.uniform(0.25, self.max_cmd_vy)
            w = np.random.uniform(-0.10, 0.10)
        elif r < 0.60:
            self.current_twist_mode = "diagonal"
            vx = np.random.uniform(0.20, 0.45)
            vy = np.random.choice([-1, 1]) * np.random.uniform(0.20, 0.40)
            w = np.random.uniform(-0.20, 0.20)
        elif r < 0.75:
            self.current_twist_mode = "s_curve"
            vx = np.random.uniform(0.25, 0.45)
            vy = np.random.uniform(-0.15, 0.15)
            w = np.sin(self.twist_mode_timer * 2.5) * np.random.uniform(0.6, self.max_cmd_omega)
        elif r < 0.85:
            self.current_twist_mode = "pivot"
            vx = np.random.uniform(-0.05, 0.05)
            vy = np.random.uniform(-0.05, 0.05)
            w = np.random.choice([-1, 1]) * np.random.uniform(0.8, self.max_cmd_omega)
        elif r < 0.90:
            self.current_twist_mode = "reverse_reflex"
            vx = np.random.uniform(self.min_cmd_vx, -0.05)
            vy = np.random.uniform(-0.10, 0.10)
            w = np.random.uniform(-0.20, 0.20)
        elif r < 0.95:
            self.current_twist_mode = "idle"
            vx, vy, w = 0.0, 0.0, 0.0
        else:
            self.current_twist_mode = "collision_injection"
            vx = np.random.uniform(0.45, self.max_cmd_vx)
            vy = 0.0
            w = 0.0

        return float(vx), float(vy), float(w)

    def spawn_curriculum_obstacles(self):
        progress = float(self.global_step_counter) / float(self.target_total_timesteps) if self.curriculum_enabled else 1.0
        self.obstacles.clear()

        if progress < 0.20:
            self.current_stage = 1
            self.domain_randomization_enabled = False
            self.wheel_slip_factors = np.ones(4, dtype=np.float32)
            n_obs = np.random.randint(2, 4)
            for _ in range(n_obs):
                ox = np.random.uniform(1.2, 4.0)
                oy = np.random.uniform(-0.6, 0.6)
                self.obstacles.append(DynamicObstacle([ox, oy], radius=np.random.uniform(0.18, 0.26)))

        elif progress < 0.45:
            self.current_stage = 2
            self.domain_randomization_enabled = False
            self.wheel_slip_factors = np.ones(4, dtype=np.float32)
            self.obstacles.append(DynamicObstacle([2.0, 0.0], radius=0.22))
            n_ped = np.random.randint(1, 3)
            for i in range(n_ped):
                x_pos = 1.8 + i * 1.2
                direction = np.random.choice([-1.0, 1.0])
                speed = np.random.uniform(0.35, 0.65)
                self.obstacles.append(DynamicObstacle(
                    pos=[x_pos, -direction * 1.5],
                    radius=0.20,
                    vel=[0.0, direction * speed],
                    bounds=[x_pos - 0.2, x_pos + 0.2, -1.8, 1.8]
                ))

        elif progress < 0.70:
            self.current_stage = 3
            self.domain_randomization_enabled = False
            self.wheel_slip_factors = np.ones(4, dtype=np.float32)
            gate_x = 2.4
            self.obstacles.append(DynamicObstacle([gate_x, -0.65], radius=0.25))
            self.obstacles.append(DynamicObstacle([gate_x, 0.65], radius=0.25))
            self.obstacles.append(DynamicObstacle(
                pos=[4.2, 0.0],
                radius=0.24,
                vel=[-np.random.uniform(0.25, 0.45), 0.0],
                bounds=[1.5, 4.5, -0.4, 0.4]
            ))

        else:
            self.current_stage = 4
            self.domain_randomization_enabled = True
            self.wheel_slip_factors = np.random.uniform(0.90, 1.10, size=4).astype(np.float32)
            self.obstacles.append(DynamicObstacle([1.8, np.random.uniform(-0.5, 0.5)], radius=0.20))
            self.obstacles.append(DynamicObstacle(
                pos=[2.8, -1.4], radius=0.20, vel=[0.0, 0.50], bounds=[2.5, 3.2, -1.6, 1.6]
            ))
            self.obstacles.append(DynamicObstacle(
                pos=[3.8, 0.2], radius=0.22, vel=[-0.35, 0.0], bounds=[1.5, 4.5, -0.6, 0.6]
            ))
            self.obstacles.append(DynamicObstacle(
                pos=[3.2, 1.5], radius=0.18, vel=[0.10, -0.40], bounds=[2.0, 4.5, -1.6, 1.6]
            ))

    def compute_lidar_scan(self) -> np.ndarray:
        cos_yaw = np.cos(self.robot_yaw)
        sin_yaw = np.sin(self.robot_yaw)
        lidar_world_x = self.robot_pos[0] + self.lidar_offset_x * cos_yaw
        lidar_world_y = self.robot_pos[1] + self.lidar_offset_x * sin_yaw
        lidar_origin = np.array([lidar_world_x, lidar_world_y], dtype=np.float32)

        ranges = np.full(self.num_lidar_rays, self.max_lidar_range, dtype=np.float32)

        for i, rel_angle in enumerate(self.lidar_angles):
            ray_global_angle = self.robot_yaw + rel_angle
            ray_dir = np.array([np.cos(ray_global_angle), np.sin(ray_global_angle)], dtype=np.float32)

            for obs in self.obstacles:
                p_obs = obs.pos - lidar_origin
                proj = np.dot(p_obs, ray_dir)
                if proj <= 0:
                    continue
                d_sq = np.dot(p_obs, p_obs) - proj**2
                r_sq = obs.radius**2
                if d_sq <= r_sq:
                    hit_dist = proj - np.sqrt(max(0.0, r_sq - d_sq))
                    if self.min_lidar_range <= hit_dist < ranges[i]:
                        ranges[i] = hit_dist

        return ranges

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self.step_count = 0
        self.twist_mode_timer = 0.0
        self.robot_pos = np.array([0.0, 0.0], dtype=np.float32)
        self.robot_yaw = 0.0
        self.target_yaw = 0.0
        self.robot_vel = np.array([0.0, 0.0], dtype=np.float32)
        self.robot_omega = 0.0
        self.prev_robot_vel = np.array([0.0, 0.0], dtype=np.float32)

        self.spawn_curriculum_obstacles()
        self.cmd_vx, self.cmd_vy, self.cmd_omega = self.sample_twist_command()

        obs = self._get_obs()
        return obs, {"curriculum_stage": self.current_stage, "twist_mode": self.current_twist_mode}

    def _get_obs(self) -> np.ndarray:
        lidar_ranges = self.compute_lidar_scan()
        norm_lidar = np.clip(lidar_ranges / self.max_lidar_range, 0.0, 1.0)

        dt_safe = max(self.dt, 1e-4)
        accel_x = (self.robot_vel[0] - self.prev_robot_vel[0]) / dt_safe
        accel_y = (self.robot_vel[1] - self.prev_robot_vel[1]) / dt_safe
        accel_z = 9.81
        norm_imu = np.array([
            np.clip(accel_x / 3.0, -1.0, 1.0),
            np.clip(accel_y / 3.0, -1.0, 1.0),
            np.clip(accel_z / 9.81, -1.0, 1.0),
            0.0,
            0.0,
            np.clip(self.robot_omega / 2.0, -1.0, 1.0),
        ], dtype=np.float32)

        norm_cmd = np.array([
            np.clip(self.cmd_vx / self.max_cmd_vx, -1.0, 1.0),
            np.clip(self.cmd_vy / self.max_cmd_vy, -1.0, 1.0),
            np.clip(self.cmd_omega / self.max_cmd_omega, -1.0, 1.0),
        ], dtype=np.float32)

        delta_theta = (self.target_yaw - self.robot_yaw + np.pi) % (2.0 * np.pi) - np.pi
        norm_head = np.array([np.clip(delta_theta / np.pi, -1.0, 1.0)], dtype=np.float32)

        return np.concatenate([norm_lidar, norm_imu, norm_cmd, norm_head]).astype(np.float32)

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, dict]:
        self.step_count += 1
        self.global_step_counter += 1
        self.twist_mode_timer += self.dt

        a0, a1, a2 = float(action[0]), float(action[1]), float(action[2])
        delta_vx = a0 * self.max_cmd_vx if a0 < 0.0 else a0 * 0.15
        delta_vy = a1 * self.delta_vy_max
        delta_omega = a2 * self.delta_omega_max

        lidar_ranges = self.compute_lidar_scan()
        d_min = float(np.min(lidar_ranges))

        alpha = float(np.clip((self.d_safe_gate - d_min) / (self.d_safe_gate - self.d_crit_gate), 0.0, 1.0))

        v_exec_x = self.cmd_vx + delta_vx
        v_exec_y = self.cmd_vy + delta_vy
        omega_exec = self.cmd_omega + delta_omega

        v_body_x = (1.0 - alpha) * self.cmd_vx + alpha * v_exec_x
        v_body_y = (1.0 - alpha) * self.cmd_vy + alpha * v_exec_y
        w_body = (1.0 - alpha) * self.cmd_omega + alpha * omega_exec

        if d_min < 0.22:
            v_body_x, v_body_y, w_body = 0.0, 0.0, 0.0

        # Mecanum Inverse Kinematics
        vp = w_body * self.geom_arm
        v1 = v_body_x - v_body_y - vp
        v2 = v_body_x + v_body_y - vp
        v3 = v_body_x + v_body_y + vp
        v4 = v_body_x - v_body_y + vp

        wheel_linear = np.array([v1, v2, v3, v4], dtype=np.float32)
        raw_rps = wheel_linear / self.wheel_circ
        max_req_rps = float(np.max(np.abs(raw_rps)))
        if max_req_rps > self.max_rps:
            motor_rps = raw_rps * (self.max_rps / max_req_rps)
        else:
            motor_rps = raw_rps

        # Mecanum Forward Kinematics (with domain randomization slip factors)
        eff_rps = motor_rps * self.wheel_slip_factors if self.domain_randomization_enabled else motor_rps
        v_tang = eff_rps * self.wheel_circ
        real_body_vx = float((v_tang[0] + v_tang[1] + v_tang[2] + v_tang[3]) / 4.0)
        real_body_vy = float((-v_tang[0] + v_tang[1] + v_tang[2] - v_tang[3]) / 4.0)
        real_body_omega = float((-v_tang[0] - v_tang[1] + v_tang[2] + v_tang[3]) / (4.0 * self.geom_arm))

        # Integrate pose
        self.prev_robot_vel = self.robot_vel.copy()
        self.robot_vel = np.array([real_body_vx, real_body_vy], dtype=np.float32)
        self.robot_omega = real_body_omega

        cos_y = np.cos(self.robot_yaw)
        sin_y = np.sin(self.robot_yaw)
        world_dx = (real_body_vx * cos_y - real_body_vy * sin_y) * self.dt
        world_dy = (real_body_vx * sin_y + real_body_vy * cos_y) * self.dt
        self.robot_pos += np.array([world_dx, world_dy], dtype=np.float32)
        self.robot_yaw = (self.robot_yaw + real_body_omega * self.dt + np.pi) % (2.0 * np.pi) - np.pi

        # Update dynamic obstacles
        for obs in self.obstacles:
            obs.update(self.dt)

        # Check collisions
        collision = False
        min_clearance = 999.0
        for obs in self.obstacles:
            dist = np.linalg.norm(self.robot_pos - obs.pos) - (self.robot_radius + obs.radius)
            if dist < min_clearance:
                min_clearance = dist
            if dist <= 0.0:
                collision = True
                break

        # Periodic twist command resample
        if self.step_count % 40 == 0:
            self.cmd_vx, self.cmd_vy, self.cmd_omega = self.sample_twist_command()

        # Reward formulation
        r_prog = 1.8 * real_body_vx * self.dt
        r_clear = 0.0
        if min_clearance < 0.20:
            r_clear = -2.5 * (0.20 - max(0.0, min_clearance))
        r_act = -0.015 * (a0**2 + a1**2 + a2**2)
        r_smooth = -0.02 * np.linalg.norm(self.robot_vel - self.prev_robot_vel)
        r_step = -0.005

        reward = r_prog + r_clear + r_act + r_smooth + r_step

        terminated = False
        if collision:
            reward -= 50.0
            terminated = True
        elif self.robot_pos[0] > 5.5:
            reward += 100.0
            terminated = True

        truncated = (self.step_count >= self.max_steps)
        info = {
            "min_clearance": min_clearance,
            "collision": collision,
            "curriculum_stage": self.current_stage,
            "twist_mode": self.current_twist_mode,
            "alpha_gating": alpha,
            "d_min": d_min
        }

        return self._get_obs(), float(reward), terminated, truncated, info


# ==============================================================================
# 2. TRAINING CALLBACK: RECORDS CONVERGENCE METRICS
# ==============================================================================

class TrainingMetricsCallback(BaseCallback):
    """Tracks episode rewards, episode lengths, and policy training statistics."""
    def __init__(self, verbose=0):
        super(TrainingMetricsCallback, self).__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
        self.timesteps_history = []
        self._curr_ep_reward = 0.0
        self._curr_ep_len = 0

    def _on_step(self) -> bool:
        rewards = self.locals.get("rewards", [0.0])
        dones = self.locals.get("dones", [False])

        self._curr_ep_reward += float(rewards[0])
        self._curr_ep_len += 1

        if dones[0]:
            self.episode_rewards.append(self._curr_ep_reward)
            self.episode_lengths.append(self._curr_ep_len)
            self.timesteps_history.append(self.num_timesteps)
            self._curr_ep_reward = 0.0
            self._curr_ep_len = 0
        return True


# ==============================================================================
# 3. ONNX EXPORT HELPER MODULE
# ==============================================================================

class JetAutoActorONNX(torch.nn.Module):
    """Clean inference-only PyTorch Actor Module for TensorRT / ONNX export."""
    def __init__(self, policy_net, action_net):
        super(JetAutoActorONNX, self).__init__()
        self.net = torch.nn.Sequential(
            policy_net[0],
            policy_net[1],
            policy_net[2],
            policy_net[3],
            action_net
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.net(x)
        return torch.clamp(out, -1.0, 1.0)


# ==============================================================================
# 4. EXPORT ALL WEIGHT FORMATS (PyTorch, ONNX, JSON, C-Header, BRAM MEM)
# ==============================================================================

def export_all_model_weights(model: PPO, target_weights_dir: str, total_timesteps: int):
    """
    Exports all bit-true weights formats directly into target_weights_dir:
    - ppo_jetauto_residual_fp32.zip
    - cl_drl_jetauto_residual_fp32.onnx & .data
    - model_weights.json
    - hardware/weights_q8_8.h
    - hardware/layer{1,2,3}_{w,b}.mem
    """
    os.makedirs(target_weights_dir, exist_ok=True)
    hw_dir = os.path.join(target_weights_dir, "hardware")
    os.makedirs(hw_dir, exist_ok=True)

    # 1. Save PyTorch Model ZIP
    zip_path = os.path.join(target_weights_dir, "ppo_jetauto_residual_fp32")
    model.save(zip_path)
    print(f"✔ PyTorch SB3 Model Saved: {zip_path}.zip")

    # Extract weights tensors
    policy_net = model.policy.mlp_extractor.policy_net
    action_net = model.policy.action_net

    w1 = policy_net[0].weight.detach().cpu().numpy()
    b1 = policy_net[0].bias.detach().cpu().numpy()
    w2 = policy_net[2].weight.detach().cpu().numpy()
    b2 = policy_net[2].bias.detach().cpu().numpy()
    w3 = action_net.weight.detach().cpu().numpy()
    b3 = action_net.bias.detach().cpu().numpy()

    # 2. Save pure JSON for fast NumPy inference
    json_data = {
        "w1": w1.tolist(),
        "b1": b1.tolist(),
        "w2": w2.tolist(),
        "b2": b2.tolist(),
        "w3": w3.tolist(),
        "b3": b3.tolist(),
        "metadata": {
            "source_run": "retrain_ai.py",
            "timestamp": datetime.now().isoformat(),
            "total_timesteps": total_timesteps,
            "architecture": "74 -> 128 (ReLU) -> 64 (ReLU) -> 3"
        }
    }
    json_path = os.path.join(target_weights_dir, "model_weights.json")
    with open(json_path, "w") as f:
        json.dump(json_data, f)
    print(f"✔ NumPy Model Weights JSON Saved: {json_path}")

    # 3. Save ONNX Model
    actor_onnx = JetAutoActorONNX(policy_net, action_net).eval()
    dummy_input = torch.randn(1, 74, dtype=torch.float32)
    onnx_path = os.path.join(target_weights_dir, "cl_drl_jetauto_residual_fp32.onnx")

    try:
        torch.onnx.export(
            actor_onnx,
            dummy_input,
            onnx_path,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=["obs_74"],
            output_names=["action_3"],
            dynamic_axes={"obs_74": {0: "batch_size"}, "action_3": {0: "batch_size"}},
            dynamo=False
        )
    except TypeError:
        torch.onnx.export(
            actor_onnx,
            dummy_input,
            onnx_path,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=["obs_74"],
            output_names=["action_3"],
            dynamic_axes={"obs_74": {0: "batch_size"}, "action_3": {0: "batch_size"}}
        )
    print(f"✔ ONNX FP32 Model Saved: {onnx_path}")

    # 4. Kuantisasi Q8.8 & Export C-Header
    w1_q = np.clip(np.round(w1 * 256.0), -32768, 32767).astype(np.int16)
    b1_q = np.clip(np.round(b1 * 256.0), -32768, 32767).astype(np.int16)
    w2_q = np.clip(np.round(w2 * 256.0), -32768, 32767).astype(np.int16)
    b2_q = np.clip(np.round(b2 * 256.0), -32768, 32767).astype(np.int16)
    w3_q = np.clip(np.round(w3 * 256.0), -32768, 32767).astype(np.int16)
    b3_q = np.clip(np.round(b3 * 256.0), -32768, 32767).astype(np.int16)

    h_path = os.path.join(hw_dir, "weights_q8_8.h")
    with open(h_path, "w") as f:
        f.write("/* weights_q8_8.h - Auto-generated Bit-True Q8.8 Weights for DE10-Nano FPGA / C++ */\n")
        f.write("#ifndef WEIGHTS_Q8_8_H_\n#define WEIGHTS_Q8_8_H_\n\n#include <stdint.h>\n\n")
        f.write("#define LAYER1_IN_DIM   74\n#define LAYER1_OUT_DIM  128\n")
        f.write("#define LAYER2_IN_DIM   128\n#define LAYER2_OUT_DIM  64\n")
        f.write("#define LAYER3_IN_DIM   64\n#define LAYER3_OUT_DIM  3\n\n")

        def write_c_array_2d(name, arr):
            f.write(f"static const int16_t {name}[{arr.shape[0]}][{arr.shape[1]}] = {{\n")
            for r in arr:
                f.write("    {" + ", ".join([str(int(v)) for v in r]) + "},\n")
            f.write("};\n\n")

        def write_c_array_1d(name, arr):
            f.write(f"static const int16_t {name}[{arr.shape[0]}] = {{\n")
            f.write("    " + ", ".join([str(int(v)) for v in arr]) + "\n")
            f.write("};\n\n")

        write_c_array_2d("layer1_weights_q8_8", w1_q)
        write_c_array_1d("layer1_biases_q8_8", b1_q)
        write_c_array_2d("layer2_weights_q8_8", w2_q)
        write_c_array_1d("layer2_biases_q8_8", b2_q)
        write_c_array_2d("layer3_weights_q8_8", w3_q)
        write_c_array_1d("layer3_biases_q8_8", b3_q)
        f.write("#endif // WEIGHTS_Q8_8_H_\n")
    print(f"✔ C-Header Q8.8 Fixed-Point Saved: {h_path}")

    # 5. Export BRAM .mem Hex Files
    def export_mem(fname, arr):
        with open(os.path.join(hw_dir, fname), "w") as mf:
            flat = arr.flatten()
            for v in flat:
                u16 = int(v) & 0xFFFF
                mf.write(f"{u16:04X}\n")

    export_mem("layer1_w.mem", w1_q)
    export_mem("layer1_b.mem", b1_q)
    export_mem("layer2_w.mem", w2_q)
    export_mem("layer2_b.mem", b2_q)
    export_mem("layer3_w.mem", w3_q)
    export_mem("layer3_b.mem", b3_q)
    print(f"✔ FPGA BRAM .mem Hex Files Exported: {hw_dir}")


# ==============================================================================
# 5. BENCHMARK EVALUATOR & FULL-DURATION GIF EXPORTER
# ==============================================================================

def create_eval_obstacles() -> List[DynamicObstacle]:
    """Fixed reproducible obstacle layout for global path tracking benchmark."""
    return [
        DynamicObstacle([1.4, -0.45], radius=0.22),
        DynamicObstacle([1.4, 0.45], radius=0.22),
        DynamicObstacle(pos=[2.6, -1.3], radius=0.20, vel=[0.0, 0.40], bounds=[2.3, 2.9, -1.5, 1.5]),
        DynamicObstacle(pos=[4.2, 0.15], radius=0.24, vel=[-0.30, 0.0], bounds=[2.5, 4.6, -0.4, 0.4]),
        DynamicObstacle([3.5, -0.60], radius=0.22),
        DynamicObstacle([4.8, 0.40], radius=0.20),
    ]


def evaluate_and_generate_artifacts(
    eval_dir: str,
    training_cb: Optional[TrainingMetricsCallback] = None
):
    """
    Evaluates all 5 algorithms on the global path following course,
    saves analytical plots and generates full-duration GIFs.
    """
    os.makedirs(eval_dir, exist_ok=True)
    print(f"\n🏁 Memulai Evaluasi Global Path Following untuk 5 Algoritma...")

    # Global Reference Path (6.0m spline)
    waypoints = [
        [0.0, 0.0],
        [1.2, 0.0],
        [2.2, 0.45],
        [3.6, -0.35],
        [4.8, 0.20],
        [6.0, 0.0]
    ]
    global_path = GlobalPath(waypoints)
    target_goal = (6.0, 0.0)

    kinematics = MecanumKinematics()
    algorithms = ["CL-DRL", "CL-DRL + CBF", "CL-DRL + mini-DWA", "DWA", "APF"]
    algo_key_map = {
        "CL-DRL": "cl_drl",
        "CL-DRL + CBF": "cl_drl_cbf",
        "CL-DRL + mini-DWA": "cl_drl_dwa",
        "DWA": "dwa",
        "APF": "apf"
    }

    results = {}
    controllers = {}

    for name in algorithms:
        controllers[name] = create_controller(algo_key_map[name])

    for algo_name in algorithms:
        controller = controllers[algo_name]
        carrot_tracker = LookaheadCarrotTracker(global_path, cruise_speed=0.45, lookahead_dist=0.60)
        metrics_tracker = BenchmarkMetricsTracker(algorithm_name=algo_name, optimal_path_length=6.0)

        eval_obstacles = create_eval_obstacles()
        num_rays = 64
        lidar_angles = np.linspace(-np.pi / 2.0, np.pi / 2.0, num_rays)

        robot_pos = np.array([0.0, 0.0], dtype=np.float32)
        robot_yaw = 0.0
        robot_vel = np.array([0.0, 0.0], dtype=np.float32)
        robot_omega = 0.0
        prev_vel = np.array([0.0, 0.0], dtype=np.float32)

        frames = []
        dt = 0.033
        max_eval_steps = 750
        reached_goal = False

        print(f"  -> Mengevaluasi {algo_name:18s} ...", end="", flush=True)

        for step in range(max_eval_steps):
            # Compute LiDAR scan
            cos_y = np.cos(robot_yaw)
            sin_y = np.sin(robot_yaw)
            lidar_origin = robot_pos + np.array([0.096 * cos_y, 0.096 * sin_y], dtype=np.float32)

            lidar_ranges = np.full(num_rays, 3.50, dtype=np.float32)
            for i, rel_a in enumerate(lidar_angles):
                ray_dir = np.array([np.cos(robot_yaw + rel_a), np.sin(robot_yaw + rel_a)], dtype=np.float32)
                for obs in eval_obstacles:
                    p_obs = obs.pos - lidar_origin
                    proj = np.dot(p_obs, ray_dir)
                    if proj <= 0:
                        continue
                    d_sq = np.dot(p_obs, p_obs) - proj**2
                    r_sq = obs.radius**2
                    if d_sq <= r_sq:
                        hit = proj - np.sqrt(max(0.0, r_sq - d_sq))
                        if 0.15 <= hit < lidar_ranges[i]:
                            lidar_ranges[i] = hit

            d_min = float(np.min(lidar_ranges))

            # Update Carrot Tracker
            cmd_vx, cmd_vy, cmd_w, head_err, dist_to_goal, goal_reached = carrot_tracker.compute_nominal_twist(
                (float(robot_pos[0]), float(robot_pos[1]), float(robot_yaw))
            )
            cmd_vel = (cmd_vx, cmd_vy, cmd_w)

            # IMU
            ax = (robot_vel[0] - prev_vel[0]) / dt
            ay = (robot_vel[1] - prev_vel[1]) / dt
            imu_data = (ax, ay, 9.81, 0.0, 0.0, robot_omega)

            # Predict Action
            exec_vx, exec_vy, exec_w, info = controller.predict(
                lidar_ranges=lidar_ranges,
                cmd_vel=cmd_vel,
                imu_data=imu_data,
                heading_err=head_err,
                obstacles=eval_obstacles,
                robot_pose=(float(robot_pos[0]), float(robot_pos[1]), float(robot_yaw))
            )

            # Kinematics forward
            vp = exec_w * kinematics.geom_arm
            v1 = exec_vx - exec_vy - vp
            v2 = exec_vx + exec_vy - vp
            v3 = exec_vx + exec_vy + vp
            v4 = exec_vx - exec_vy + vp
            raw_rps = np.array([v1, v2, v3, v4]) / kinematics.wheel_circ
            max_r = float(np.max(np.abs(raw_rps)))
            mot_rps = raw_rps * (kinematics.max_rps / max_r) if max_r > kinematics.max_rps else raw_rps

            v_tang = mot_rps * kinematics.wheel_circ
            real_vx = float((v_tang[0] + v_tang[1] + v_tang[2] + v_tang[3]) / 4.0)
            real_vy = float((-v_tang[0] + v_tang[1] + v_tang[2] - v_tang[3]) / 4.0)
            real_w = float((-v_tang[0] - v_tang[1] + v_tang[2] + v_tang[3]) / (4.0 * kinematics.geom_arm))

            prev_vel = robot_vel.copy()
            robot_vel = np.array([real_vx, real_vy], dtype=np.float32)
            robot_omega = real_w

            w_dx = (real_vx * cos_y - real_vy * sin_y) * dt
            w_dy = (real_vx * sin_y + real_vy * cos_y) * dt
            robot_pos += np.array([w_dx, w_dy], dtype=np.float32)
            robot_yaw = (robot_yaw + real_w * dt + np.pi) % (2.0 * np.pi) - np.pi

            for obs in eval_obstacles:
                obs.update(dt)

            dist_goal = float(np.linalg.norm(robot_pos - np.array(target_goal)))
            cte = global_path.compute_cross_track_error(float(robot_pos[0]), float(robot_pos[1]))
            intervened = bool(info.get('intervened', info.get('shield_active', False)))
            alpha_val = float(info.get('alpha_gating', 0.0))
            collided = (d_min < 0.05)
            reached_goal = (dist_goal < 0.25)

            metrics_tracker.record_step(
                pose=(float(robot_pos[0]), float(robot_pos[1]), float(robot_yaw)),
                cmd_vel=cmd_vel,
                exec_vel=(exec_vx, exec_vy, exec_w),
                d_min=d_min,
                cte=cte,
                heading_err=head_err,
                latency_ms=controller.last_latency_ms,
                motor_rps=mot_rps,
                intervened=intervened,
                alpha=alpha_val,
                collided=collided,
                reached_goal=reached_goal
            )

            frames.append({
                'step': step,
                'time': step * dt,
                'robot_pos': robot_pos.copy(),
                'robot_yaw': robot_yaw,
                'cmd_vel': cmd_vel,
                'exec_vel': (exec_vx, exec_vy, exec_w),
                'lidar_ranges': lidar_ranges.copy(),
                'obstacles': [(o.pos.copy(), o.radius, o.vel.copy()) for o in eval_obstacles],
                'd_min': d_min,
                'dist_to_goal': dist_goal,
                'info': info,
                'reached_goal': (dist_goal < 0.35)
            })

            if dist_goal < 0.35:
                reached_goal = True
                break

        summary = metrics_tracker.compute_summary()
        results[algo_name] = {
            'summary': summary,
            'tracker': metrics_tracker,
            'frames': frames,
            'reached_goal': reached_goal
        }
        print(f" Selesai: Goal Reached={reached_goal}, Steps={len(frames)}, Min Clearance={summary['min_clearance_cm']:.1f} cm")

    # --------------------------------------------------------------------------
    # Render Full-Duration GIFs
    # --------------------------------------------------------------------------
    print("\n🎬 Merender 5 Animasi GIF Durasi Penuh (Start -> Goal)...")
    gif_file_map = {
        "CL-DRL": "eval_1_cl_drl.gif",
        "CL-DRL + CBF": "eval_2_cl_drl_cbf.gif",
        "CL-DRL + mini-DWA": "eval_3_cl_drl_dwa_shield.gif",
        "DWA": "eval_4_dwa.gif",
        "APF": "eval_5_apf.gif"
    }

    for algo_name, fname in gif_file_map.items():
        if algo_name not in results:
            continue
        frames = results[algo_name]['frames']
        out_gif_path = os.path.join(eval_dir, fname)

        # Sample at ~15 fps
        stride = max(1, int(round((1.0 / 0.033) / 15.0)))
        sub_frames = frames[::stride]
        if frames[-1] not in sub_frames:
            sub_frames.append(frames[-1])

        fig, ax = plt.subplots(figsize=(9, 6), dpi=90)
        fig.patch.set_facecolor('#0d1117')
        ax.set_facecolor('#161b22')
        ax.set_xlim(-0.5, 6.8)
        ax.set_ylim(-2.2, 2.2)
        ax.set_aspect('equal')
        ax.grid(True, linestyle='--', alpha=0.3, color='#8b949e')

        pts = global_path.points
        ax.plot(pts[:, 0], pts[:, 1], color='#58a6ff', linestyle='--', linewidth=2.0, alpha=0.85)
        ax.scatter([0.0], [0.0], color='#2ea043', s=140, marker='*', zorder=10)
        ax.scatter([6.0], [0.0], color='#d29922', s=140, marker='X', zorder=10)

        trail_line, = ax.plot([], [], color='#3fb950', linewidth=2.2, alpha=0.9, zorder=5)
        robot_patch = patches.Circle((0, 0), 0.22, edgecolor='#3fb950', facecolor='#238636', alpha=0.6, zorder=7)
        ax.add_patch(robot_patch)
        heading_line, = ax.plot([], [], color='#ffffff', linewidth=2.5, zorder=8)

        first_f = sub_frames[0]
        obs_patches = []
        for opos, orad, ovel in first_f['obstacles']:
            is_dyn = np.linalg.norm(ovel) > 0.01
            col = '#f85149' if is_dyn else '#8b949e'
            p = patches.Circle(opos, orad, edgecolor=col, facecolor=col, alpha=0.5, zorder=6)
            ax.add_patch(p)
            obs_patches.append(p)

        lidar_lines = [ax.plot([], [], linewidth=0.7, alpha=0.5, zorder=4)[0] for _ in range(num_rays)]

        hud_title = ax.text(0.02, 0.95, '', transform=ax.transAxes, color='#ffffff', fontsize=10, fontweight='bold',
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='#21262d', edgecolor='#30363d', alpha=0.9))
        hud_stats = ax.text(0.02, 0.85, '', transform=ax.transAxes, color='#7ee787', fontsize=8, fontfamily='monospace',
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='#161b22', edgecolor='#30363d', alpha=0.85))

        traj_x, traj_y = [], []

        def update_frame(idx):
            f = sub_frames[idx]
            rx, ry = f['robot_pos']
            ryaw = f['robot_yaw']
            traj_x.append(rx)
            traj_y.append(ry)

            trail_line.set_data(traj_x, traj_y)
            robot_patch.center = (rx, ry)
            heading_line.set_data([rx, rx + 0.28 * np.cos(ryaw)], [ry, ry + 0.28 * np.sin(ryaw)])

            lidar_x = rx + 0.096 * np.cos(ryaw)
            lidar_y = ry + 0.096 * np.sin(ryaw)
            for i, rel_a in enumerate(lidar_angles):
                global_a = ryaw + rel_a
                ray_dist = f['lidar_ranges'][i]
                x_end = lidar_x + ray_dist * np.cos(global_a)
                y_end = lidar_y + ray_dist * np.sin(global_a)
                lidar_lines[i].set_data([lidar_x, x_end], [lidar_y, y_end])
                col = '#f85149' if ray_dist < 0.50 else ('#d29922' if ray_dist < 1.20 else '#3fb950')
                lidar_lines[i].set_color(col)

            for p, (opos, _, _) in zip(obs_patches, f['obstacles']):
                p.center = opos

            info = f['info']
            status_msg = info.get('shield_message', 'OK')
            if f.get('reached_goal', False):
                status_msg = '🏁 GOAL REACHED'

            hud_title.set_text(f"🤖 {algo_name} | Step {f['step']:03d} ({f['time']:.2f}s)")
            hud_stats.set_text(
                f"V_cmd : ({f['cmd_vel'][0]:+.2f}, {f['cmd_vel'][1]:+.2f}) m/s\n"
                f"V_exec: ({f['exec_vel'][0]:+.2f}, {f['exec_vel'][1]:+.2f}) m/s\n"
                f"Clearance: {f['d_min']*100:.1f} cm | Goal Dist: {f['dist_to_goal']:.2f} m\n"
                f"Status: {status_msg}"
            )
            return [trail_line, robot_patch, heading_line, hud_title, hud_stats] + lidar_lines

        anim = animation.FuncAnimation(fig, update_frame, frames=len(sub_frames), interval=1000.0/15.0, blit=False)
        anim.save(out_gif_path, writer='pillow', fps=15)
        plt.close(fig)
        print(f"  ✔ GIF Diekspor: {fname} ({len(sub_frames)} frames)")

    # --------------------------------------------------------------------------
    # Render Analytical Plots
    # --------------------------------------------------------------------------
    print("\n📊 Membuat Grafik Komparatif & Kurva Konvergensi...")

    # Plot 1: Trajectory Comparison
    fig1, ax1 = plt.subplots(figsize=(10, 6), dpi=100)
    fig1.patch.set_facecolor('#0f172a')
    ax1.set_facecolor('#0f172a')

    ax1.plot(pts[:, 0], pts[:, 1], color='#38bdf8', linestyle='--', linewidth=2.5, alpha=0.9, label='Global Path')
    ax1.scatter([0.0], [0.0], color='#22c55e', s=160, marker='*', zorder=10, label='Start (0,0)')
    ax1.scatter([6.0], [0.0], color='#eab308', s=160, marker='X', zorder=10, label='Goal (6,0)')

    sample_obs = create_eval_obstacles()
    for obs in sample_obs:
        is_dyn = np.linalg.norm(obs.vel) > 0.01
        col = '#ef4444' if is_dyn else '#94a3b8'
        c = patches.Circle(obs.pos, obs.radius, edgecolor=col, facecolor=col, alpha=0.45, zorder=6)
        ax1.add_patch(c)

    algo_colors = {
        "CL-DRL": "#3b82f6",
        "CL-DRL + CBF": "#10b981",
        "CL-DRL + mini-DWA": "#a855f7",
        "DWA": "#f97316",
        "APF": "#ec4899"
    }

    for name, r in results.items():
        traj = np.array(r['tracker'].robot_trajectory)
        c = algo_colors.get(name, '#ffffff')
        ax1.plot(traj[:, 0], traj[:, 1], color=c, linewidth=2.2, label=f"{name} ({r['summary']['min_clearance_cm']:.1f} cm)")

    ax1.set_xlim(-0.4, 6.6)
    ax1.set_ylim(-2.0, 2.0)
    ax1.set_title("Perbandingan Lintasan Navigasi Global Path 5 Algoritma", color='#ffffff', fontsize=13, fontweight='bold', pad=12)
    ax1.set_xlabel("X Koordinat Dunia (m)", color='#94a3b8')
    ax1.set_ylabel("Y Koordinat Dunia (m)", color='#94a3b8')
    ax1.tick_params(colors='#94a3b8')
    ax1.legend(loc='lower left', facecolor='#1e293b', edgecolor='#334155', labelcolor='#ffffff', fontsize=9)
    ax1.grid(True, linestyle=':', alpha=0.25, color='#475569')

    p1_path = os.path.join(eval_dir, "trajectories_comparison.png")
    fig1.savefig(p1_path, bbox_inches='tight')
    plt.close(fig1)
    print(f"  ✔ Trajectories Plot: {p1_path}")

    # Plot 2: Metrics Bar Chart
    fig2, axes = plt.subplots(1, 4, figsize=(16, 4.5), dpi=100)
    fig2.patch.set_facecolor('#0f172a')

    metric_keys = [
        ('min_clearance_cm', 'Min Clearance (cm)', '#10b981', 'cm'),
        ('mean_cte_m', 'Mean CTE (m)', '#38bdf8', 'm'),
        ('time_to_goal_s', 'Waktu Tempuh (s)', '#f59e0b', 's'),
        ('avg_latency_ms', 'Latensi Inferensi (ms)', '#ec4899', 'ms')
    ]

    for ax, (m_key, title, color, unit) in zip(axes, metric_keys):
        ax.set_facecolor('#1e293b')
        vals = [results[algo]['summary'][m_key] for algo in algorithms if algo in results]
        names = [algo.replace("CL-DRL", "DRL") for algo in algorithms if algo in results]

        bars = ax.bar(names, vals, color=color, alpha=0.85, edgecolor='#ffffff', linewidth=0.5, width=0.55)
        ax.set_title(title, color='#ffffff', fontsize=11, fontweight='bold')
        ax.tick_params(colors='#94a3b8', labelsize=8)
        ax.set_xticklabels(names, rotation=35, ha='right')
        ax.grid(axis='y', linestyle=':', alpha=0.3, color='#475569')

        for b in bars:
            h = b.get_height()
            ax.annotate(f"{h:.2f}", xy=(b.get_x() + b.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points", ha='center', va='bottom',
                        color='#ffffff', fontsize=8, fontweight='bold')

    fig2.suptitle("Benchmarking Komparatif 5 Algoritma Obstacle Avoidance", color='#ffffff', fontsize=14, fontweight='bold')
    plt.tight_layout()
    p2_path = os.path.join(eval_dir, "comparative_metrics_bar_chart.png")
    fig2.savefig(p2_path, bbox_inches='tight')
    plt.close(fig2)
    print(f"  ✔ Comparative Bar Chart: {p2_path}")

    # Plot 3: Training Convergence Curves (if callback available)
    if training_cb and len(training_cb.episode_rewards) > 5:
        fig3, ax3 = plt.subplots(figsize=(10, 5), dpi=100)
        fig3.patch.set_facecolor('#0f172a')
        ax3.set_facecolor('#1e293b')

        r_hist = np.array(training_cb.episode_rewards)
        # Moving average
        window = min(25, len(r_hist))
        r_smooth = np.convolve(r_hist, np.ones(window)/window, mode='valid')

        ax3.plot(r_hist, color='#64748b', alpha=0.35, label='Raw Episode Reward')
        ax3.plot(np.arange(window - 1, len(r_hist)), r_smooth, color='#22c55e', linewidth=2.5, label=f'Smooth Reward (MA-{window})')

        ax3.set_title("Kurva Konvergensi Pelatihan PPO CL-DRL Residual", color='#ffffff', fontsize=13, fontweight='bold', pad=12)
        ax3.set_xlabel("Episode", color='#94a3b8')
        ax3.set_ylabel("Total Reward", color='#94a3b8')
        ax3.tick_params(colors='#94a3b8')
        ax3.legend(facecolor='#0f172a', edgecolor='#334155', labelcolor='#ffffff')
        ax3.grid(True, linestyle=':', alpha=0.25, color='#475569')

        p3_path = os.path.join(eval_dir, "training_convergence_curves.png")
        fig3.savefig(p3_path, bbox_inches='tight')
        plt.close(fig3)
        print(f"  ✔ Training Curves: {p3_path}")

    print(f"🎉 Seluruh artefak evaluasi dan GIF berhasil disimpan di: {eval_dir}")


# ==============================================================================
# 6. WORKSPACE SYNCHRONIZATION HELPER
# ==============================================================================

def sync_to_ros2_workspace():
    """Synchronizes weights and evaluations to igor_ws if present."""
    ws_pkg_weights = "/home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/src/igor_navigation/igor_navigation/weights"
    ws_pkg_eval = "/home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/src/igor_navigation/igor_navigation/evaluations"

    if os.path.exists(os.path.dirname(ws_pkg_weights)):
        print("\n🔄 Menyinkronkan bobot dan evaluasi ke workspace ROS 2 igor_ws...")
        shutil.copytree(WEIGHTS_DIR, ws_pkg_weights, dirs_exist_ok=True)
        shutil.copytree(EVALUATIONS_DIR, ws_pkg_eval, dirs_exist_ok=True)
        print("✔ Berkas berhasil disalin ke igor_ws/src/igor_navigation.")

        # Trigger colcon build
        ws_root = "/home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws"
        cmd = f'bash -c "source /opt/ros/humble/setup.bash && cd {ws_root} && colcon build --symlink-install --packages-select igor_navigation"'
        ret = os.system(cmd)
        if ret == 0:
            print("✔ Colcon build berhasil meregistrasi bobot baru di workspace igor_ws!")
        else:
            print(f"⚠ Catatan: Colcon build mengembalikan kode keluar {ret}.")


# ==============================================================================
# 7. MAIN RUNNER
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Retrain CL-DRL residual actor and update igor_navigation package weights."
    )
    parser.add_argument("--timesteps", type=int, default=300000, help="Total training timesteps (default: 300,000)")
    parser.add_argument("--n_envs", type=int, default=4, help="Number of parallel environments (default: 4)")
    parser.add_argument("--seed", type=int, default=2026, help="Random seed for reproducibility (default: 2026)")
    parser.add_argument("--eval", action="store_true", default=True, help="Run 5-algorithm global benchmark and render GIFs")
    parser.add_argument("--no-eval", action="store_false", dest="eval", help="Skip benchmark evaluation")
    parser.add_argument("--sync-ws", action="store_true", default=True, help="Sync to igor_ws and rebuild (default: True)")
    args = parser.parse_args()

    # Reproducibility
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    print("==================================================================")
    print("  PROJECT IGOR: RETRAIN CL-DRL RESIDUAL PPO (Hiwonder JetAuto AMR)")
    print(f"  Target Timesteps  : {args.timesteps:,}")
    print(f"  Parallel Envs     : {args.n_envs}")
    print(f"  Random Seed       : {args.seed}")
    print(f"  Update Weights Dir: {WEIGHTS_DIR}")
    print(f"  Evaluations Dir   : {EVALUATIONS_DIR}")
    print("==================================================================")

    # Inisialisasi Vectorized Environment
    def make_env():
        return JetAutoResidualAvoidanceEnvV3(
            curriculum_enabled=True,
            target_total_timesteps=args.timesteps
        )

    vec_env = DummyVecEnv([make_env for _ in range(args.n_envs)])

    # Setup PPO Model
    policy_kwargs = dict(
        net_arch=dict(
            pi=[128, 64],
            vf=[128, 64]
        ),
        activation_fn=torch.nn.ReLU
    )

    training_cb = TrainingMetricsCallback()

    model = PPO(
        "MlpPolicy",
        vec_env,
        policy_kwargs=policy_kwargs,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.001,
        verbose=1
    )

    print(f"\n🚀 Memulai training {args.timesteps:,} timesteps...")
    t0 = time.time()
    model.learn(total_timesteps=args.timesteps, callback=training_cb, log_interval=20)
    dur = time.time() - t0
    print(f"\n⏱️ Pelatihan selesai dalam {dur:.1f} detik ({dur/60.0:.2f} menit, FPS: {args.timesteps/dur:.0f})!")

    # Update Bobot di dalam package
    print("\n📦 Memperbarui berkas bobot di igor_navigation/weights...")
    export_all_model_weights(model, WEIGHTS_DIR, args.timesteps)

    # Jalankan Evaluasi & Render GIF
    if args.eval:
        evaluate_and_generate_artifacts(EVALUATIONS_DIR, training_cb=training_cb)

    # Sinkronisasi ke ROS 2 Workspace jika tersedia
    if args.sync_ws:
        sync_to_ros2_workspace()

    print("\n" + "="*66)
    print("  RETRAINING & ARTIFACT EXPORT COMPLETE SUCCESSFULLY!")
    print(f"  Weights Updated    : {WEIGHTS_DIR}")
    print(f"  Visualizations/GIFs: {EVALUATIONS_DIR}")
    print("="*66)


if __name__ == "__main__":
    main()
