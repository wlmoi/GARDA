"""GARDA Physical AI simulator loop (sensors -> neural -> safety gate -> mecanum robot).

Backends
  fpga  : inference on the DE10-Lite (NN_LOAD x24, NN_START, NN_READ raw) and the HARDWARE
          neural command gate (opcode 0x2D) decides what reaches the wheels.   -> LIVE HARDWARE
  model : bit-exact Python model of the neural core + the same clamp/gate rule. -> SOFTWARE SIMULATION
Inputs
  golden: the 100 reference sensor frames of the model (outputs checked bit-exact every step)
  lidar : 24 virtual LiDAR rays from the simulated arena (closed loop, experimental: the legacy
          24-64-64-4 model was not trained on this simulator)
Demo mapping (shown on screen): neural outputs 0, 1, 2 are displayed as Vx, Vy, omega.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from pathlib import Path

import garda_protocol as p
from garda_nn_model import ASSETS, NeuralModel, gate

ARENA_W, ARENA_H = 8.0, 5.0                 # metres
OBSTACLES = [(2.2, 1.3, 0.45), (5.6, 3.6, 0.55), (4.1, 2.2, 0.35), (6.6, 1.2, 0.4), (1.4, 3.8, 0.4)]  # (x, y, r)
V_MAX, W_MAX = 0.7, 1.6                     # m/s and rad/s at |command| = 1.0
LX, LY, R_WHEEL = 0.20, 0.17, 0.05          # mecanum geometry (m)
LIDAR_RANGE = 3.0


def _s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class PhysAI:
    def __init__(self, link):
        self.link = link
        self.model = NeuralModel()
        self.ins = [int(x, 16) for x in (ASSETS / "test_inputs.mem").read_text().split()]
        self.gold = [_s16(int(x, 16)) for x in (ASSETS / "test_outputs.mem").read_text().split()]
        self.lock = threading.Lock()
        self.thread = None
        self.stop_evt = threading.Event()
        self.sim_estop = False
        self.reset_state()
        self.running = False
        self.backend = "model"
        self.inputs = "golden"
        self.error = None

    # ------------------------------------------------------------------ control
    def reset_state(self):
        self.pose = [1.0, 2.5, 0.0]
        self.trail = deque(maxlen=400)
        self.history = deque(maxlen=240)
        self.step_n = 0
        self.frame = 0
        self.exact_ok = self.exact_total = 0
        self.sensors = [0] * 24
        self.rays = []
        self.raw = [0, 0, 0]
        self.gated = [0, 0, 0]
        self.permit = False
        self.reasons = []
        self.wheels = [0.0] * 4
        self.hz = 0.0
        self.cycles = None
        self.last_t = None

    def start(self, backend: str, inputs: str) -> tuple[bool, str]:
        if self.running:
            return False, "already running"
        if backend == "fpga" and not (self.link.connected and self.link.ident):
            return False, "LIVE HARDWARE needs a connected FPGA that answered IDENT"
        if backend == "fpga" and self.link.ident.get("interface_version", 0) < 2:
            return False, "this FPGA image has no neural command gate (0x2D): program the current build"
        self.backend, self.inputs, self.error = backend, inputs, None
        self.reset_state()
        self.stop_evt.clear()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return True, "started"

    def stop(self):
        self.stop_evt.set()
        self.running = False

    def estop(self):
        if self.backend == "fpga" and self.link.connected:
            self.link.transact(p.OP_HOST_ESTOP)
        self.sim_estop = True

    def safe_reset(self):
        if self.backend == "fpga" and self.link.connected:
            try:
                self.link.transact(p.OP_SAFE_RESET, p.SAFE_RESET_MAGIC)
            except p.ProtocolError:
                pass
            time.sleep(0.05)
        self.sim_estop = False

    # ------------------------------------------------------------------ world
    def _lidar(self):
        x, y, th = self.pose
        rays, vals = [], []
        for i in range(24):
            a = th + i * 2 * math.pi / 24
            dx, dy = math.cos(a), math.sin(a)
            d = LIDAR_RANGE
            for t_wall in ((-x / dx) if dx < 0 else ((ARENA_W - x) / dx) if dx > 0 else 1e9,
                           (-y / dy) if dy < 0 else ((ARENA_H - y) / dy) if dy > 0 else 1e9):
                if 0 < t_wall < d:
                    d = t_wall
            for ox, oy, r in OBSTACLES:
                fx, fy = x - ox, y - oy
                b = fx * dx + fy * dy
                c = fx * fx + fy * fy - r * r
                disc = b * b - c
                if disc >= 0:
                    t = -b - math.sqrt(disc)
                    if 0 < t < d:
                        d = t
            rays.append(round(d, 3))
            vals.append(int(round((1.0 - 2.0 * d / LIDAR_RANGE) * 256)) & 0xFFFF)   # near = +1, far = -1 (Q8.8)
        return vals, rays

    def _move(self, dt):
        vx, vy, w = (g / 256.0 for g in self.gated)
        vx, vy, w = vx * V_MAX, vy * V_MAX, w * W_MAX
        x, y, th = self.pose
        gx = vx * math.cos(th) - vy * math.sin(th)
        gy = vx * math.sin(th) + vy * math.cos(th)
        nx, ny = x + gx * dt, y + gy * dt
        m = 0.36                                   # robot radius incl. mecanum wheels (m)
        hit = not (m < nx < ARENA_W - m and m < ny < ARENA_H - m) or \
            any((nx - ox) ** 2 + (ny - oy) ** 2 < (r + m) ** 2 for ox, oy, r in OBSTACLES)
        if not hit:
            x, y = nx, ny
        th = (th + w * dt) % (2 * math.pi)
        self.pose = [x, y, th]
        self.trail.append((round(x, 3), round(y, 3)))
        k = LX + LY
        self.wheels = [round((vx - vy - k * w) / R_WHEEL, 2), round((vx + vy + k * w) / R_WHEEL, 2),
                       round((vx + vy - k * w) / R_WHEEL, 2), round((vx - vy + k * w) / R_WHEEL, 2)]
        return hit

    # ------------------------------------------------------------------ inference
    def _infer_fpga(self, vec):
        lk = self.link
        for i, v in enumerate(vec):
            lk.transact(p.OP_NN_LOAD, i | ((v & 0xFFFF) << 8), quiet=True)
        lk.transact(p.OP_NN_START, quiet=True)
        for _ in range(20):
            if p.decode_nn(lk.transact(p.OP_NN_READ, 0, quiet=True).value)["done"]:
                break
        raw = [p.decode_nn(lk.transact(p.OP_NN_READ, i, quiet=True).value)["value"] for i in range(4)]
        g = [lk.transact(p.OP_NN_CMD, i, quiet=True).value for i in range(3)]
        permit = all(v >> 28 & 1 for v in g)
        gated = [_s16(v & 0xFFFF) for v in g]
        ext = p.decode_ext_status(lk.transact(p.OP_EXT_STATUS, quiet=True).value)
        reasons = [n for n, on in (("E-STOP (host)", ext["host_estop"]), ("E-STOP (KEY1)", ext["key_estop"]),
                                   ("SW3 protective stop", ext["sw3_protective_stop"]), ("SW2 not ready", ext["sw2_not_ready"]),
                                   ("watchdog", ext["watchdog_trip"]), ("protocol fault", ext["protocol_fault"]),
                                   ("invalid command", ext["invalid_command"])) if on]
        if self.cycles is None:
            self.cycles = lk.transact(p.OP_NN_CYCLES, quiet=True).value
        return raw, gated, permit, reasons

    def _infer_model(self, vec):
        raw, fault = self.model.infer(vec)
        reasons = (["E-STOP (simulated)"] if self.sim_estop else []) + (["neural fault"] if fault else [])
        permit = not reasons
        self.cycles = 18192
        return raw, [gate(v, permit) for v in raw[:3]], permit, reasons

    def _loop(self):
        while not self.stop_evt.is_set():
            t0 = time.perf_counter()
            try:
                if self.inputs == "golden":
                    n = self.frame % 100
                    vec = self.ins[n * 24:n * 24 + 24]
                    expect = self.gold[n * 4:n * 4 + 4]
                    rays = []
                else:
                    vec, rays = self._lidar()
                    expect = self.model.infer(vec)[0]
                raw, gated, permit, reasons = (self._infer_fpga if self.backend == "fpga" else self._infer_model)(vec)
            except p.ProtocolError as e:
                self.error = f"FPGA link error: {e}"
                self.gated, self.permit = [0, 0, 0], False      # no valid answer = no motion
                self.running = False
                break
            now = time.perf_counter()
            dt = 0.05 if self.last_t is None else min(now - self.last_t, 0.25)
            self.last_t = now
            with self.lock:
                self.sensors = [_s16(v) for v in vec]
                self.rays = rays
                self.raw, self.gated, self.permit, self.reasons = raw[:3], gated, permit, reasons
                match = raw == expect
                self.exact_ok += int(match)
                self.exact_total += 1
                bump = self._move(dt)
                self.step_n += 1
                self.frame += 1
                inst = 1.0 / max(dt, 1e-3)                          # real loop rate (steps per second)
                self.hz = round(0.8 * self.hz + 0.2 * inst, 1) if self.hz else round(inst, 1)
                self.history.append({"raw": raw[:3], "gated": gated, "permit": permit, "bump": bump, "exact": match})
            if self.backend == "model":
                time.sleep(max(0.0, 0.06 - (time.perf_counter() - t0)))
        self.running = False

    # ------------------------------------------------------------------ view
    def snapshot(self) -> dict:
        with self.lock:
            return {
                "running": self.running, "backend": self.backend, "inputs": self.inputs, "error": self.error,
                "provenance": "LIVE HARDWARE" if self.backend == "fpga" else "SOFTWARE SIMULATION",
                "mapping": "demo mapping: neural outputs 0,1,2 of the 24-64-64-4 model shown as Vx, Vy, omega",
                "pose": self.pose, "trail": list(self.trail)[-200:], "rays": self.rays, "sensors": self.sensors,
                "raw": self.raw, "gated": self.gated, "permit": self.permit, "reasons": self.reasons,
                "wheels": self.wheels, "history": list(self.history)[-120:], "step": self.step_n,
                "frame": self.frame % 100, "exact_ok": self.exact_ok, "exact_total": self.exact_total,
                "hz": self.hz, "cycles": self.cycles, "sim_estop": self.sim_estop,
                "arena": {"w": ARENA_W, "h": ARENA_H, "obstacles": OBSTACLES, "lidar_range": LIDAR_RANGE},
                "limits": {"q_min": -256, "q_max": 253, "v_max": V_MAX, "w_max": W_MAX},
            }
