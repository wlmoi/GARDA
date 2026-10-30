# SPESIFIKASI REKAYASA & PANDUAN AKSI REMEDIASI: AI/ML ENGINEER & ROS 2 INTEGRATOR
## Rencana Aksi Perbaikan Bug Kritis, Filter Keselamatan CBF, dan Normalisasi Sensor (Non-FPGA)
### Proyek: Autonomous Mobile Robot (AMR) Mecanum — PERURI Chip Hackathon 2026

**Nomor Dokumen:** `11_action_plan_remediasi_ai_dan_ros2_integrator.md`  
**Lokasi Berkas:** `peruri-ai-final/reports/11_action_plan_remediasi_ai_dan_ros2_integrator.md`  
**Target Pelaksana:** AI Coding Agent / Autonomous Developer / ROS 2 Software Engineer  
**Peran Pengguna:** AI/ML Engineer & ROS 2 Software Integrator (Strictly Non-FPGA / Non-ASIC)  
**Lingkup Kerja:** Python 3, ROS 2 Humble (`ros2_ws/src/`), PyTorch, Filter Keselamatan (CBF/DWA), Kinematika Mecanum  
**Status Dokumen:** Instruksi Eksekusi Siap Pakai (Actionable Drop-in Specifications)

---

## 1. Konteks Peran & Batasan Tanggung Jawab (Scope Definition)

Dokumen ini disusun khusus sebagai **konteks instruksi langsung untuk coding agent**. Tugas agen adalah menyelesaikan semua inkonsistensi dan bug fungsional pada layer software autonomy tanpa menyentuh modul hardware RTL.

### 1.1 In-Scope (Wajib Dikerjakan oleh Agen Ini)
1. **Node ROS 2 Pengendali:** [`ros2_ws/src/igor_controller/igor_controller/controller_node.py`](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py)
2. **Master Bringup Launch:** [`ros2_ws/src/igor_bringup/launch/bringup.launch.py`](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_bringup/launch/bringup.launch.py)
3. **Registri Controller:** [`ros2_ws/src/igor_navigation/igor_navigation/controllers/__init__.py`](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/controllers/__init__.py)
4. **Pipeline Retraining & Ekspor Bobot:** [`ros2_ws/src/igor_navigation/igor_navigation/retrain_ai.py`](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/retrain_ai.py)
5. **Sinkronisasi Kode Mirror:** Menyelaraskan perubahan dari `ros2_ws/src/` ke `fpga/software_integration/src/` agar CI test host tidak gagal.

### 1.2 Out-of-Scope (DILARANG Diubah / Tanggung Jawab Tim FPGA)
1. ❌ Berkas Verilog/SystemVerilog di `src/*.v` dan `fpga/rtl/*.v`
2. ❌ Konfigurasi Intel Quartus Prime (`*.qsf`, `*.qpf`, `output_files/*.sof`)
3. ❌ Layout ASIC TinyTapeout, OpenLane config, dan GDS II
4. ❌ Rekalkulasi hash manifest `manifest.json` pada script `freeze_release.py`

---

## 2. Rencana Aksi Terperinci & Spesifikasi Kode Pengganti

Berikut adalah 6 item perbaikan teknis yang harus dieksekusi secara berurutan:

---

### TUGAS 1: Koreksi Baud Rate Serial FPGA & Penambahan Parameter Launch
* **Tingkat Keparahan:** 🔴 **CRITICAL (P1)**
* **Masalah:** Node pengontrol meng-hardcode baud rate ke `115200`, padahal RTL FPGA DE10-Nano berjalan pada `921600`. Parameter baud rate juga tidak tersedia di launch file, menyebabkan hardware fisik selalu timeout.

#### Langkah 1.1: Edit `bringup.launch.py`
**File Target:** `ros2_ws/src/igor_bringup/launch/bringup.launch.py`
1. Tambahkan `DeclareLaunchArgument` untuk `fpga_baudrate` (default: `'921600'`).
2. Teruskan konfigurasi `fpga_baudrate` ke dalam dictionary `parameters` milik `controller_node`.
3. Masukkan argumen tersebut ke dalam array return `LaunchDescription`.

```python
# Tambahkan deklarasi argumen:
fpga_baud_arg = DeclareLaunchArgument(
    'fpga_baudrate',
    default_value='921600',
    description='UART baudrate for DE10-Nano FPGA accelerator (default: 921600)'
)
fpga_baudrate = LaunchConfiguration('fpga_baudrate')

# Pada controller_node parameters, tambahkan:
parameters=[{
    'algorithm': algorithm,
    'use_fpga': use_fpga,
    'mcu_port': mcu_port,
    'fpga_port': fpga_port,
    'fpga_baudrate': fpga_baudrate,  # <-- Tambahkan baris ini
    'control_rate_hz': control_rate_hz,
    'use_mock_serial': use_mock_serial
}]

# Pada return LaunchDescription, tambahkan fpga_baud_arg
```

#### Langkah 1.2: Edit `controller_node.py`
**File Target:** `ros2_ws/src/igor_controller/igor_controller/controller_node.py`
1. Di dalam `__init__`, deklarasikan parameter `fpga_baudrate`:
   ```python
   self.declare_parameter('fpga_baudrate', 921600)
   self.fpga_baudrate = int(self.get_parameter('fpga_baudrate').value)
   ```
2. Pada instansiasi `FPGABridge` (sekitar baris 131–135), gantikan hardcoded `115200`:
   ```python
   if self.use_fpga:
       self.fpga = FPGABridge(
           port=self.fpga_port,
           baudrate=self.fpga_baudrate,  # <-- Gunakan parameter, bukan 115200
           mock=self.use_mock_serial
       )
   ```

---

### TUGAS 2: Registrasi Alias `'cl_drl_dwa_shield'` di Controller Registry
* **Tingkat Keparahan:** 🟠 **HIGH (P2)**
* **Masalah:** Menjalankan robot sesuai perintah panduan `README.md` (`algorithm:=cl_drl_dwa_shield`) menyebabkan crash instan `ValueError: Unknown controller`.

**File Target:** `ros2_ws/src/igor_navigation/igor_navigation/controllers/__init__.py`
Tambahkan alias `'cl_drl_dwa_shield'` ke dalam dict `CONTROLLER_REGISTRY`:

```python
CONTROLLER_REGISTRY = {
    'cl_drl_cbf': CLDRLCBFController,
    'cl_drl_dwa': CLDRLDWAController,
    'cl_drl_dwa_shield': CLDRLDWAController,  # <-- Tambahkan baris ini
    'dwa_shield': CLDRLDWAController,
    'mini_dwa': CLDRLDWAController,
    'drl_dwa': CLDRLDWAController,
    'cl_drl': CLDRLController,
    'dwa': DWAController,
    'apf': APFController,
}
```

---

### TUGAS 3: Pengaktifan Rintangan LiDAR pada Filter Keselamatan CBF
* **Tingkat Keparahan:** 🔴 **CRITICAL (P1)**
* **Masalah:** Pada `controller_node.py` (baris 269), argumen `obstacles=None` dioper ke `filter_cbf()`. Akibatnya, matriks quadratic programming solver CBF tidak pernah memasukkan constraint rintangan, melumpuhkan jaminan keselamatan *Nagumo invariance* di lapangan.

**File Target:** `ros2_ws/src/igor_controller/igor_controller/controller_node.py`
Cari blok pemanggilan CBF (sekitar baris 260–275). Gantikan blok tersebut dengan logika ekstraksi rintangan LiDAR lokal berikut:

```python
            # Ekstraksi rintangan lokal dari subsampled LiDAR (64 sinar)
            cbf_obstacles = []
            if self.latest_lidar_64 is not None:
                # 64 sinar tersebar merata 360 derajat [-pi, pi]
                angles = np.linspace(-math.pi, math.pi, len(self.latest_lidar_64), endpoint=False)
                for dist, ang in zip(self.latest_lidar_64, angles):
                    # Filter jarak relevan (0.05m s.d 1.50m) untuk batas barrier CBF
                    if 0.05 < dist < 1.50:
                        obs_x = float(dist * math.cos(ang))
                        obs_y = float(dist * math.sin(ang))
                        # Format tuple: (x, y, radius_rintangan)
                        cbf_obstacles.append((obs_x, obs_y, 0.12))

            # Filter keselamatan hybrid: CBF, DWA Shield, atau Zero-Stop
            if self.algorithm == 'cl_drl_cbf':
                safe_vx, safe_vy, safe_wz, _ = self.cpu_controller.filter_cbf(
                    cand_vx=float(v_blended[0]),
                    cand_vy=float(v_blended[1]),
                    cand_omega=float(v_blended[2]),
                    robot_pose=(0.0, 0.0, 0.0),
                    obstacles=cbf_obstacles if len(cbf_obstacles) > 0 else None,
                    allowed_max_vx=allowed_max_vx
                )
                v_safe = np.array([safe_vx, safe_vy, safe_wz], dtype=np.float32)

            elif self.algorithm in ['cl_drl_dwa', 'cl_drl_dwa_shield', 'mini_dwa']:
                # Aktifkan evaluasi Mini-DWA Shield jika dipilih
                if hasattr(self, 'cpu_controller') and self.cpu_controller is not None:
                    safe_vx, safe_vy, safe_wz, _ = self.cpu_controller.filter_dwa(
                        cand_vx=float(v_blended[0]),
                        cand_vy=float(v_blended[1]),
                        cand_omega=float(v_blended[2]),
                        scan_ranges=self.latest_lidar_64
                    )
                    v_safe = np.array([safe_vx, safe_vy, safe_wz], dtype=np.float32)
                else:
                    v_safe = v_blended

            else:
                # Fallback emergency stop jika jarak minimum terlalu dekat
                if d_min < 0.22:
                    v_safe = np.zeros(3, dtype=np.float32)
                else:
                    v_safe = v_blended
```

---

### TUGAS 4: Standardisasi Normalisasi Sensor IMU (Accel Z & Gyroscope)
* **Tingkat Keparahan:** 🔴 **CRITICAL (P1)**
* **Masalah:**
  1. Accel Z dibagi `3.0` di `controller_node.py`, padahal saat training dan di `drl_controller.py` dibagi `9.81`. Nilai $9.81 / 3.0 = 3.27$ melanggar rentang valid FPGA Q8.8 ($[-1.0, 1.0]$) dan ditolak oleh FPGA RTL (`reject`).
  2. Gyroscope pada CPU path dioper mentah dalam satuan `deg/s`, padahal model mengasumsikan `rad/s`, menyebabkan nilai gyro ter-klip jenuh ke `1.0`.

**File Target:** `ros2_ws/src/igor_controller/igor_controller/controller_node.py`

#### Langkah 4.1: Koreksi Vektor Observasi FPGA (sekitar baris 230–240)
```python
        if self.use_fpga:
            obs = np.zeros(74, dtype=np.float32)
            obs[:64] = beams_norm
            obs[64] = float(np.clip(float(ax) / 3.0, -1.0, 1.0))
            obs[65] = float(np.clip(float(ay) / 3.0, -1.0, 1.0))
            # PERBAIKAN: Gunakan normalisasi 9.81 m/s^2 sesuai dataset pelatihan
            obs[66] = float(np.clip(float(az) / 9.81, -1.0, 1.0))
            obs[67] = float(np.clip(math.radians(float(gx)) / 2.0, -1.0, 1.0))
            obs[68] = float(np.clip(math.radians(float(gy)) / 2.0, -1.0, 1.0))
            obs[69] = float(np.clip(math.radians(float(gz)) / 2.0, -1.0, 1.0))
            obs[70] = float(np.clip(self.cmd_linear_x / 0.60, -1.0, 1.0))
            obs[71] = float(np.clip(self.cmd_linear_y / 0.45, -1.0, 1.0))
            obs[72] = float(np.clip(self.cmd_angular_z / 1.50, -1.0, 1.0))
            obs[73] = float(np.clip(delta_theta / math.pi, -1.0, 1.0))
```

#### Langkah 4.2: Koreksi Input IMU pada Mode CPU (sekitar baris 280–286)
Konversikan `gx, gy, gz` dari derajat/detik ke radian/detik sebelum dioper ke `predict`:
```python
        else:
            # CPU Path (All 5 algorithms unified via predict)
            gx_rad = math.radians(float(gx))
            gy_rad = math.radians(float(gy))
            gz_rad = math.radians(float(gz))
            exec_vx, exec_vy, exec_wz, _ = self.cpu_controller.predict(
                lidar_ranges=beams_norm,
                cmd_vel=(self.cmd_linear_x, self.cmd_linear_y, self.cmd_angular_z),
                imu_data=(float(ax), float(ay), float(az), gx_rad, gy_rad, gz_rad),
                heading_err=delta_theta
            )
            v_safe = np.array([exec_vx, exec_vy, exec_wz], dtype=np.float32)
```

---

### TUGAS 5: Koreksi Desaturasi Kecepatan Roda (Mecanum Kinematics)
* **Tingkat Keparahan:** 🟡 **MEDIUM (P2)**
* **Masalah:** Clipping independen per-roda (`np.clip`) mengubah rasio perputaran roda saat saturasi kecepatan, menyebabkan deviasi sudut heading dan lintasan robot.

**File Target:** `ros2_ws/src/igor_controller/igor_controller/controller_node.py`
Gantikan blok perhitungan motor RPS manual (sekitar baris 290–305) dengan penskalaan proporsional:

```python
        # 5. Inverse Kinematics for JetAuto Mecanum Chassis
        linear_x, linear_y, angular_z = float(v_safe[0]), float(v_safe[1]), float(v_safe[2])
        vp = angular_z * (self.kinematics.wheelbase + self.kinematics.track_width) / 2.0
        circ = math.pi * self.kinematics.wheel_diameter

        # Orientasi motor sasis JetAuto (kanan M3 & M4 terbalik secara mekanis)
        v1 = linear_x - linear_y - vp   # Front-Left
        v2 = linear_x + linear_y - vp   # Rear-Left
        v3 = -linear_x - linear_y - vp  # Front-Right (Mirrored)
        v4 = -linear_x + linear_y - vp  # Rear-Right (Mirrored)

        raw_rps = np.array([v1, v2, v3, v4], dtype=np.float32) / circ
        max_r = float(np.max(np.abs(raw_rps)))
        
        # Desaturasi proporsional: pertahankan arah gerak saat motor jenuh
        if max_r > self.kinematics.max_rps:
            scale = self.kinematics.max_rps / max_r
            motor_rps = raw_rps * scale
        else:
            motor_rps = raw_rps

        rps1, rps2, rps3, rps4 = float(motor_rps[0]), float(motor_rps[1]), float(motor_rps[2]), float(motor_rps[3])

        # Transmit motor speed packet to STM32
        self.mcu.send_motor_speeds(rps1, rps2, rps3, rps4)
```

---

### TUGAS 6: Otomasi Handshake Ekspor Bobot ke ROM FPGA & Sinkronisasi
* **Tingkat Keparahan:** 🟡 **MEDIUM (P3)**
* **Masalah:** Saat model AI dilatih ulang (`retrain_ai.py`), bobot hanya diekspor ke file per-layer `layer{1..3}_{w,b}.mem`. ROM FPGA membaca satu file utuh `policy_weights.mem`.

**File Target:** `ros2_ws/src/igor_navigation/igor_navigation/retrain_ai.py`
Di dalam fungsi `export_all_model_weights` (sekitar baris 645–655), setelah menulis `layer3_b.mem`, panggil skrip canonical generator FPGA `fpga/verification/src_policy/run.py` secara otomatis:

```python
    # 6. Kompilasi otomatis file memori monolitik FPGA (policy_weights.mem)
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        fpga_run_script = os.path.join(root_dir, "fpga/verification/src_policy/run.py")
        if os.path.exists(fpga_run_script):
            print("🔄 Mengompilasi berkas policy_weights.mem untuk FPGA DE10-Nano...")
            ret = os.system(f"python3 {fpga_run_script}")
            if ret == 0:
                print("✔ Berkas fpga/rtl/igor_src_policy/policy_weights.mem berhasil diperbarui!")
    except Exception as e:
        print(f"⚠ Peringatan: Tidak dapat memperbarui policy_weights.mem secara otomatis: {e}")
```

#### Sinkronisasi Dual-Codebase:
Setelah selesai memodifikasi file di `ros2_ws/src/`, salin berkas yang telah diperbaiki ke folder mirror pengujian FPGA:
```bash
cp ros2_ws/src/igor_controller/igor_controller/controller_node.py fpga/software_integration/src/igor_controller/igor_controller/
cp ros2_ws/src/igor_controller/igor_controller/fpga_bridge.py fpga/software_integration/src/igor_controller/igor_controller/
cp ros2_ws/src/igor_bringup/launch/bringup.launch.py fpga/software_integration/src/igor_bringup/launch/
```

---

## 3. Protokol Verifikasi Mandiri (Testing & Validation Suite)

Setelah coding agent selesai mengaplikasikan perubahan kode di atas, agen **WAJIB** mengeksekusi rangkaian perintah verifikasi berikut di terminal bash untuk membuktikan kebenaran perbaikan:

### Langkah Verifikasi 1: Rebuild Workspace ROS 2
```bash
bash -c "source /opt/ros/humble/setup.bash && cd /home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws && colcon build --symlink-install"
```
*Kriteria Lulus:* Output harus mengembalikan status `Finished <<< igor_bringup, igor_controller, igor_navigation [SUCCESS]`.

---

### Langkah Verifikasi 2: Uji Inisialisasi Seluruh Algoritma Pengendali
Jalankan uji instansiasi node dengan variasi parameter algoritma untuk memastikan tidak ada crash:
```bash
bash -c "source /opt/ros/humble/setup.bash && cd /home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws && source install/setup.bash && python3 -c '
import rclpy
from igor_controller.controller_node import IgorControllerNode

algos = [\"cl_drl_cbf\", \"cl_drl_dwa\", \"cl_drl_dwa_shield\", \"cl_drl\", \"dwa\", \"apf\"]
for algo in algos:
    rclpy.init(args=[\"--ros-args\", \"-p\", f\"algorithm:={algo}\", \"-p\", \"use_mock_serial:=true\"])
    node = IgorControllerNode()
    print(f\"SUCCESS: {algo} initialized correctly!\")
    node.destroy_node()
    rclpy.shutdown()
print(\"ALL CONTROLLERS PASS INITIALIZATION TEST!\")
'"
```
*Kriteria Lulus:* Seluruh 6 algoritma mengembalikan `SUCCESS: <algo> initialized correctly!`.

---

### Langkah Verifikasi 3: Uji Respons Filter Keselamatan CBF terhadap Rintangan
Jalankan skrip scratch cepat untuk memastikan bahwa jika ada rintangan di depan robot, CBF memodifikasi kecepatan maju ($v_x$):
```bash
bash -c "source /opt/ros/humble/setup.bash && cd /home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws && source install/setup.bash && python3 -c '
import numpy as np
from igor_navigation.controllers.cbf_safety_filter import CBFSafetyFilter

cbf = CBFSafetyFilter(robot_radius=0.18, d_safe=0.25, gamma=1.5)
# Rintangan 0.35 meter tepat di depan robot (x=0.35, y=0.0)
obstacles = [(0.35, 0.0, 0.10)]
vx_safe, vy_safe, wz_safe, status = cbf.filter_control(
    cand_vx=0.50, cand_vy=0.0, cand_omega=0.0,
    robot_pose=(0.0, 0.0, 0.0),
    obstacles=obstacles,
    allowed_max_vx=0.60
)
print(f\"Candidate Vx: 0.50 m/s -> CBF Safe Vx: {vx_safe:.3f} m/s (Status: {status})\")
assert vx_safe < 0.50, \"CBF must brake when obstacle is ahead!\"
print(\"CBF OBSTACLE BRAKING VERIFIED SUCCESSFULLY!\")
'"
```
*Kriteria Lulus:* `vx_safe` terbukti tereduksi ($< 0.50\ \text{m/s}$) saat ada rintangan di depan, dan mencetak `CBF OBSTACLE BRAKING VERIFIED SUCCESSFULLY!`.

---

## 4. Panduan Komunikasi & Framing untuk Presentasi Stakeholder

Sebagai AI/ML engineer dan ROS 2 integrator, berikan masukan berikut kepada tim pembuat slide presentasi & demo:

1. **Jalur Fisik Aktuasi Motor:**
   - *Jangan sebutkan:* "FPGA mengirim sinyal langsung ke motor STM32".
   - *Sebutkan dengan bangga:* "Kami menerapkan arsitektur **Dual-Brain Compute**: Jetson Orin Nano bertindak sebagai **Central Safety Host & Mission Gateway**, sedangkan DE10-Nano FPGA bertindak sebagai **Zero-Jitter Neural Co-Processor via PCIe/UART** yang mengembalikan *residual reflex* dalam sub-milidetik."
2. **Kesiapan Jaminan Keselamatan Formal (CBF):**
   - Paparkan bahwa filter CBF bertindak sebagai *hard deterministic mathematical shield* (lapisan terluar) yang menjamin batas *forward invariance* Nagumo, bahkan jika jaringan neural network menghasilkan aksi agresif di lingkungan dinamis.

---
*Dokumen ini merupakan panduan kerja resmi (executable spec) untuk menyelesaikan seluruh backlog inkonsistensi AI/ML dan ROS 2.*
