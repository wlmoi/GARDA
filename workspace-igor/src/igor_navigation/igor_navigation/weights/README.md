# IGOR Navigation - Model Weights & Hardware Export Artifacts

Direktori ini menyimpan seluruh artefak bobot model neural network untuk **CL-DRL (PPO Gated Residual)** pada robot holonomik Hiwonder JetAuto Mecanum.

## 1. Arsitektur Jaringan (Bit-for-Bit MLP)
- **Input Layer**: 74 dimensi (64 berkas frontal LiDAR $[-\pi/2, +\pi/2]$, 6-DOF IMU, 3-dim teleop command $[v_x, v_y, \omega]$, 1 heading error $\Delta \theta$).
- **Hidden Layer 1**: $74 \to 128$ (Aktivasi: ReLU). Bobot: $W_1 \in \mathbb{R}^{128 \times 74}$, $b_1 \in \mathbb{R}^{128}$.
- **Hidden Layer 2**: $128 \to 64$ (Aktivasi: ReLU). Bobot: $W_2 \in \mathbb{R}^{64 \times 128}$, $b_2 \in \mathbb{R}^{64}$.
- **Output Layer**: $64 \to 3$ (Aksi Delta Tak-Terdimensi $[-1.0, 1.0]^3$). Bobot: $W_3 \in \mathbb{R}^{3 \times 64}$, $b_3 \in \mathbb{R}^{3}$.

## 2. Format Bobot yang Tersedia

| Nama File | Format | Target Platform | Keterangan |
|---|---|---|---|
| `model_weights.json` | JSON Dictionary (FP32) | CPU / Python / JS / MicroPython | Sangat ringan, inferensi murni NumPy/C tanpa PyTorch |
| `cl_drl_jetauto_residual_fp32.onnx` & `.data` | ONNX Model (FP32) | Jetson Orin Nano (TensorRT / ONNXRuntime) | Format deployment standar industri untuk inferensi hardware terakselerasi |
| `ppo_jetauto_residual_fp32.zip` | Stable-Baselines3 Zip | PyTorch / Python Environment | Checkpoint model lengkap PyTorch SB3 |
| `hardware/weights_q8_8.h` | C Header (Signed int16) | Embedded STM32 / ESP32 / C++ SDK | Bobot terkuantisasi bit-true fixed-point Q8.8 ($x_{\text{int}} = \text{round}(x \times 256)$) |
| `hardware/layer{1,2,3}_{w,b}.mem` | Hex ASCII Memory File | FPGA BRAM / Verilog Accelerator | File inisialisasi memori sintesis FPGA (`$readmemh`) |

## 3. Contoh Cara Load di Python Murni (NumPy)

```python
import json
import numpy as np

with open("model_weights.json", "r") as f:
    w = json.load(f)

w1 = np.array(w["w1"], dtype=np.float32) # (128, 74)
b1 = np.array(w["b1"], dtype=np.float32) # (128,)
w2 = np.array(w["w2"], dtype=np.float32) # (64, 128)
b2 = np.array(w["b2"], dtype=np.float32) # (64,)
w3 = np.array(w["w3"], dtype=np.float32) # (3, 64)
b3 = np.array(w["b3"], dtype=np.float32) # (3,)

def forward(obs74):
    h1 = np.maximum(0.0, np.dot(w1, obs74) + b1)
    h2 = np.maximum(0.0, np.dot(w2, h1) + b2)
    action = np.clip(np.dot(w3, h2) + b3, -1.0, 1.0)
    return action
```
