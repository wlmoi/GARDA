# LAPORAN AUDIT TEKNIS: INKONSISTENSI ARSITEKTUR HARDWARE, SOFTWARE STACK, LOGIKA AI, DAN VERIFIKASI SISTEM
## Evaluasi Kritis Kesiapan Sistem Otonom AMR Mecanum (iSeeDesignITB) — PERURI Chip Hackathon 2026

**Nomor Dokumen:** `10_laporan_audit_inkonsistensi_arsitektur_hardware_software_dan_verifikasi.md`  
**Lokasi Berkas:** `peruri-ai-final/reports/10_laporan_audit_inkonsistensi_arsitektur_hardware_software_dan_verifikasi.md`  
**Tanggal Audit:** 17 Oktober 2026  
**Auditor / Penelaah:** Lead Autonomous Systems & Hardware Co-Design Auditor  
**Klasifikasi:** Laporan Audit Kritis & Rencana Remediasi Rekayasa (Engineering Quality Assurance)  
**Status Tindakan:** Mendesak (Action Required Before Hardware & Live Demo Validation)

---

## DAFTAR ISI

1. [Ringkasan Eksekutif & Ringkasan Temuan](#1-ringkasan-eksekutif--ringkasan-temuan)
2. [Audit Temuan Kategori 1: Arsitektur Hardware & Aliran Data Aktuasi](#2-audit-temuan-kategori-1-arsitektur-hardware--aliran-data-aktuasi)
   - [2.1 Mismatch Jalur Aktuasi Motor: Klaim FPGA $\to$ STM32 vs Realita Jetson USB](#21-mismatch-jalur-aktuasi-motor-klaim-fpga-to-stm32-vs-realita-jetson-usb)
   - [2.2 Status Disparitas Hardware Safety Gate (`igor_safety_security_gate.v`)](#22-status-disparitas-hardware-safety-gate-igor_safety_security_gatev)
   - [2.3 Dualitas & Fragmen Kode ASIC TinyTapeout yang Tidak Terintegrasi](#23-dualitas--fragmen-kode-asic-tinytapeout-yang-tidak-terintegrasi)
3. [Audit Temuan Kategori 2: Komunikasi Serial & Baud Rate (Fatal Operational Bug)](#3-audit-temuan-kategori-2-komunikasi-serial--baud-rate-fatal-operational-bug)
   - [3.1 Konflik Baud Rate Kritis: 921,600 bps vs 115,200 bps](#31-konflik-baud-rate-kritis-921600-bps-vs-115200-bps)
   - [3.2 Ketiadaan Parameter `fpga_baudrate` pada ROS 2 Launch File](#32-ketiadaan-parameter-fpga_baudrate-pada-ros-2-launch-file)
   - [3.3 Mekanisme Fail-Closed vs Silent Mock Fallback](#33-mekanisme-fail-closed-vs-silent-mock-fallback)
4. [Audit Temuan Kategori 3: Desinkronisasi Dual-Codebase Software Stack](#4-audit-temuan-kategori-3-desinkronisasi-dual-codebase-software-stack)
   - [4.1 Disparitas `ros2_ws/src/` vs `fpga/software_integration/src/`](#41-disparitas-ros2_wssrc-vs-fpgasoftware_integrationsrc)
   - [4.2 Skrip CI/CD Test Menguji Kode Mirror yang Usang (Blind Verification)](#42-skrip-cicd-test-menguji-kode-mirror-yang-usang-blind-verification)
5. [Audit Temuan Kategori 4: Logika AI, Kontrol Keselamatan & Normalisasi Sensor](#5-audit-temuan-kategori-4-logika-ai-kontrol-keselamatan--normalisasi-sensor)
   - [5.1 Bypass Total Filter Keselamatan CBF (`obstacles=None`) di Runtime ROS 2](#51-bypass-total-filter-keselamatan-cbf-obstaclesnone-di-runtime-ros-2)
   - [5.2 Dead Code Mini-DWA Shield pada Jalur Eksekusi FPGA](#52-dead-code-mini-dwa-shield-pada-jalur-eksekusi-fpga)
   - [5.3 Runtime Crash Akibat Ketidakcocokan Registri Algoritma (`cl_drl_dwa_shield`)](#53-runtime-crash-akibat-ketidakcocokan-registri-algoritma-cl_drl_dwa_shield)
   - [5.4 Inkonsistensi Kritis Normalisasi Akselerasi Z (IMU): 3.0 vs 9.81](#54-inkonsistensi-kritis-normalisasi-akselerasi-z-imu-30-vs-981)
   - [5.5 Inkonsistensi Satuan Gyroscope (rad/s vs deg/s) antara Mode CPU & FPGA](#55-inkonsistensi-satuan-gyroscope-rads-vs-degs-antara-mode-cpu--fpga)
   - [5.6 Kontradiksi Tahapan Kurikulum Pelatihan (Klaim 3-Stage vs Kode 4-Stage)](#56-kontradiksi-tahapan-kurikulum-pelatihan-klaim-3-stage-vs-kode-4-stage)
   - [5.7 Inkonsistensi Parameter & Inversi Kinematika Mecanum](#57-inkonsistensi-parameter--inversi-kinematika-mecanum)
6. [Audit Temuan Kategori 5: Integritas Verifikasi (Cryptographic Provenance)](#6-audit-temuan-kategori-5-integritas-verifikasi-cryptographic-provenance)
   - [6.1 Kegagalan Verifikasi Integritas Rilis (`freeze_release.py --check`)](#61-kegagalan-verifikasi-integritas-rilis-freeze_releasepy---check)
   - [6.2 Retraining Pipeline Terputus dari RTL Memory ROM FPGA](#62-retraining-pipeline-terputus-dari-rtl-memory-rom-fpga)
7. [Audit Temuan Kategori 6: Dokumentasi, Broken Links, dan Metadata Package](#7-audit-temuan-kategori-6-dokumentasi-broken-links-dan-metadata-package)
   - [7.1 Broken Links pada Dokumentasi Utama & Absolute Path Leak](#71-broken-links-pada-dokumentasi-utama--absolute-path-leak)
   - [7.2 Metadata Penulis TinyTapeout `info.yaml` (Jane Street Upstream Artifact)](#72-metadata-penulis-tinytapeout-infoyaml-jane-street-upstream-artifact)
   - [7.3 Konflik Versi Dependensi Python Environment](#73-konflik-versi-dependensi-python-environment)
8. [Matriks Remediasi & Rencana Aksi Terstruktur (Actionable Fixes)](#8-matriks-remediasi--rencana-aksi-terstruktur-actionable-fixes)

---

## 1. Ringkasan Eksekutif & Ringkasan Temuan

Audit ini dilakukan dengan meneliti secara komprehensif seluruh komponen repositori proyek: kode Verilog/RTL di `src/` dan `fpga/`, node pengendali dan paket ROS 2 di `ros2_ws/` dan `fpga/software_integration/`, skrip pipeline pelatihan di `retrain_ai.py`, skrip uji verifikasi/CI di `.github/workflows/`, berkas pengunci integritas rilis (`manifest.json`, `model_provenance.json`), serta dokumentasi teknis di `README.md` dan `docs/`.

### Matriks Kategori Temuan & Tingkat Keparahan (Severity)

| ID | Domain Masalah | Tingkat Keparahan | Dampak Utama | Status |
|---|---|---|---|---|
| **ISSUE-01** | **Baud Rate Mismatch FPGA Bridge** | 🔴 **CRITICAL (P1)** | Komunikasi UART host-FPGA timeout seketika pada hardware fisik; fallback ke mock. | Teridentifikasi Solusi |
| **ISSUE-02** | **Bypass Filter CBF (`obstacles=None`)** | 🔴 **CRITICAL (P1)** | Jaminan keselamatan formal Nagumo Invariance 0% collision gugur total di runtime ROS 2. | Teridentifikasi Solusi |
| **ISSUE-03** | **Skala Akselerasi Z IMU (3.0 vs 9.81)** | 🔴 **CRITICAL (P1)** | Nilai sensor melanggar batas rentang Q8.8 FPGA $\to$ penolakan paket inferensi (*reject*). | Teridentifikasi Solusi |
| **ISSUE-04** | **Mismatch Jalur Aktuasi Motor** | 🟠 **HIGH (P2)** | Diskrepansi klaim arsitektur (FPGA $\to$ STM32) vs realita (Jetson $\to$ STM32). | Rencana Reframing |
| **ISSUE-05** | **Safety Gate Tidak Terintegrasi di Policy RTL** | 🟠 **HIGH (P2)** | Hardware gate zero-latency tidak memproteksi keluaran neural policy di bitstream aktif. | Klarifikasi Scope |
| **ISSUE-06** | **Desinkronisasi Dual-Codebase ROS 2** | 🟠 **HIGH (P2)** | Pengujian CI/CD memverifikasi kode di `software_integration`, bukan di `ros2_ws`. | Sinkronisasi File |
| **ISSUE-07** | **Crash Nama Algoritma `cl_drl_dwa_shield`** | 🟠 **HIGH (P2)** | Node ROS 2 crash saat dijalankan sesuai perintah resmi di README. | Perbaikan Registry |
| **ISSUE-08** | **Kegagalan `freeze_release.py --check`** | 🟡 **MEDIUM (P3)** | Audit reproduksibilitas rilis gagal akibat drift hash sha256 pada file dokumen/build. | Re-freeze Manifest |
| **ISSUE-09** | **Retraining Disconnected dari FPGA ROM** | 🟡 **MEDIUM (P3)** | Model retrain CPU tidak otomatis terinjeksi ke `policy_weights.mem` FPGA. | Otomasi Export |
| **ISSUE-10** | **Broken Links & Metadata `info.yaml`** | 🟡 **MEDIUM (P3)** | Tautan dokumen rusak dan nama penulis upstream hackathon masih tertinggal. | Pembersihan Dokumen |

---

## 2. Audit Temuan Kategori 1: Arsitektur Hardware & Aliran Data Aktuasi

### 2.1 Mismatch Jalur Aktuasi Motor: Klaim FPGA $\to$ STM32 vs Realita Jetson USB

#### Deskripsi Permasalahan:
Pada dokumen [README.md (Baris 48–82)](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/README.md#L48-L82), arsitektur sistem dipaparkan menggunakan diagram ASCII berikut:
```text
+---------------------------------------------------------------------------------+
| Layer 1: High-Level Planning & Perception (NVIDIA Jetson Orin Nano)            |
+---------------------------------------------------------------------------------+
                                      |
         Observation Vector (74-D Q8.8, 921,600 bps UART)
                                      v
+---------------------------------------------------------------------------------+
| Layer 2: Fast Reactive Control & Policy Inference (Terasic DE10-Nano FPGA)      |
|                                                                                 |
|  [UART RX] -> [Input Regs] -> [Fully Pipelined MLP] -> [Q8.8 to Motor RPS]     |
|                                                            |                    |
|  [Hardware Safety & Security Gate (Dual-Core Interlock)] <-+                    |
+---------------------------------------------------------------------------------+
                                      |
         Verified Motor RPS Packets (1,000,000 bps binary UART)
                                      v
+---------------------------------------------------------------------------------+
| Layer 3: Low-Level Motor Control & Telemetry (STM32 Chassis Controller)         |
+---------------------------------------------------------------------------------+
```

#### Realita pada Kode Implementasi:
1. **Node ROS 2 Pengendali ([controller_node.py](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L247-L305)):**
   - Host (Jetson) mengumpulkan observasi sensor 74-D.
   - Host mengirim observasi ke FPGA melalui port serial `/dev/fpga`.
   - FPGA mengembalikan 3 nilai *residual action* $(\Delta v_x, \Delta v_y, \Delta \omega_z)$ ke Jetson.
   - Host (Jetson) melakukan blending aksi dasar + residual, menjalankan evaluasi keselamatan, dan menghitung inversi kinematika mecanum menjadi target RPS 4 roda:
     $$(\text{rps}_{fl}, \text{rps}_{fr}, \text{rps}_{rl}, \text{rps}_{rr})$$
   - Host (Jetson) mengemas paket biner motor dan mengirimkannya langsung ke STM32 melalui port serial `/dev/ttyACM0` (`1,000,000 bps`) via modul `JetAutoSerialDriver` ([mcu_driver.py](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/mcu_driver.py#L183-L208)).
2. **Ketiadaan Jalur Fisik FPGA $\to$ STM32:**
   Pada modul FPGA ([igor_src_policy_uart.v](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/rtl/igor_src_policy/igor_src_policy_uart.v)), modul hanya memiliki 1 pasang pin UART: `uart_rx` dan `uart_tx` yang terhubung ke pin GPIO header DE10-Nano menuju Jetson UART. **Tidak ada UART transmitter kedua yang memancarkan paket 1,000,000 bps ke STM32.**
3. **Pengakuan Tim Internal FPGA ([fpga/docs/IMPLEMENTATION_READINESS.md](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/docs/IMPLEMENTATION_READINESS.md#L15)):**
   > *"The hardware safety gate is currently not wired to the new policy's output or to STM32 messages."*

#### Analisis Dampak:
Klaim bahwa FPGA bertindak sebagai gateway langsung yang memutus aktuasi ke STM32 secara fisik (*in-line physical motor interlock*) adalah diskrepansi faktual. Bila juri teknis meminta demonstrasi kabel fisik dari DE10-Nano langsung ke STM32, sistem tidak akan terbukti karena motor terhubung ke kabel USB Host Jetson.

---

### 2.2 Status Disparitas Hardware Safety Gate (`igor_safety_security_gate.v`)

#### Deskripsi Permasalahan:
Dokumen root `README.md` dan `fpga/README.md` mempromosikan `igor_safety_security_gate.v` sebagai komponen unggulan:
> *"Safety & Security: Hardware safety & security gate (igor_safety_security_gate.v) enforcing hardware-level interlocks on motor commands with zero CPU overhead."*

#### Realita pada RTL:
- Modul inferensi utama yang aktif di bitstream DE10-Nano ([igor_src_policy_uart.v](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/rtl/igor_src_policy/igor_src_policy_uart.v)) **tidak menginstansiasi `igor_safety_security_gate.v`**. Modul ini hanya membungkus `uart_rx`, `uart_tx`, `protocol_fsm`, dan `igor_src_policy_core`.
- Eksperimen parallel 8-DSP ([fpga/experiments/parallel8/igor_src_policy_core.v](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/experiments/parallel8/igor_src_policy_core.v)) juga tidak menginstansiasi safety gate.
- `igor_safety_security_gate.v` hanya diinstansiasi pada arsitektur lama berbasis path planner grid map ([rtl/igor_top.v](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/rtl/igor_top.v)) dan testbench terisolasi.

---

### 2.3 Dualitas & Fragmen Kode ASIC TinyTapeout yang Tidak Terintegrasi

#### Deskripsi Permasalahan:
Di direktori `src/` (root ASIC workspace), terdapat dua klaster berkas yang kontradiktif:
1. **Desain Aktif TinyTapeout (`tt_um_igorchip` di [igorchip_top.v](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/src/igorchip_top.v)):**
   Hanya menghubungkan `program_host.v`, `program_memory.v`, dan macro SRAM IHP `sram_256x16_bb.v`.
2. **Koleksi File RTL Warisan (10 berkas di `src/`):**
   `bit_engine.v`, `dm.v`, `edge_units.v`, `fifo.v`, `gpio.v`, `host_if.v`, `prog_mem.v`, `scheduler.v`, `thread.v`, `timing.v`.

#### Kontradiksi Dokumentasi:
- Pada [README.md baris 168](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/README.md#L168), tabel dokumentasi mencantumkan:
  `bit_engine.v` $\to$ *"Multi-thread protocol engine core"*.
- Namun pada [docs/ARCHITECTURE.md baris 48–51](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/docs/ARCHITECTURE.md#L48-L51), dinyatakan secara tegas:
  > *"The repository also contains legacy/in-progress design files that are NOT integrated into tt_um_igorchip: bit_engine.v, thread.v, dm.v, edge_units.v, fifo.v, gpio.v, host_if.v, prog_mem.v, scheduler.v, timing.v. These files are preserved for future extension but are not part of the current implemented ISA or tapeout configuration."*
- Selain itu, di `fpga/src/project.v` terdapat modul TinyTapeout lain bernama `tt_um_wlmoi_igor_gate` yang berisi neural core dan safety gate terpisah, menciptakan kebingungan mengenai modul ASIC mana yang mewakili sistem final.

---

## 3. Audit Temuan Kategori 2: Komunikasi Serial & Baud Rate (Fatal Operational Bug)

### 3.1 Konflik Baud Rate Kritis: 921,600 bps vs 115,200 bps

Ini adalah **bug operasional fatal tingkat P1** yang menyebabkan hardware fisik tidak dapat berfungsi:

1. **RTL Hardware FPGA ([igor_src_policy_uart.v baris 7](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/rtl/igor_src_policy/igor_src_policy_uart.v#L7)):**
   ```verilog
   module igor_src_policy_uart #(
       parameter integer CLK_FREQ = 50000000,
       parameter integer BAUD     = 921600   // Hardware Baud Generator diatur ke 921,600 bps
   )( ... );
   ```
2. **Spesifikasi Protokol di Dokumentasi ([README.md](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/README.md#L60) & [ros2_ws/README.md](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/README.md#L186)):**
   Mendokumentasikan koneksi serial FPGA pada **921,600 baud**.
3. **Implementasi Node ROS 2 ([controller_node.py baris 131–135](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L131-L135)):**
   ```python
   if self.use_fpga:
       self.fpga = FPGABridge(
           port=self.fpga_port,
           baudrate=115200,   # <-- HARDCODED SECARA SALAH KE 115200!
           mock=self.use_mock_serial
       )
   ```
4. **Dampak Langsung:**
   Ketika robot dijalankan di lapangan dengan flag `--ros-args -p use_fpga:=true -p use_mock_serial:=false`, node driver Host mengirim bit UART pada durasi pulsa $8.68\ \mu\text{s}$ (115.2 kbps), sementara FPGA men-sampling pulsa pada durasi $1.085\ \mu\text{s}$ (921.6 kbps).
   Akibatnya:
   - FSM UART RX pada FPGA akan mendeteksi framing error / invalid magic byte.
   - FPGA tidak pernah merespons paket inferensi.
   - Node Python mengalami `Timeout waiting for FPGA response` secara terus menerus.

---

### 3.2 Ketiadaan Parameter `fpga_baudrate` pada ROS 2 Launch File

Pada berkas peluncuran utama [bringup.launch.py](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_bringup/launch/bringup.launch.py):
- Parameter `use_fpga`, `fpga_port`, dan `use_mock_serial` dideklarasikan sebagai argumen launch.
- Namun parameter `fpga_baudrate` **sama sekali tidak dideklarasikan** dan tidak diteruskan ke `controller_node`.
- Pengguna tidak memiliki opsi untuk mengoreksi baud rate melalui command line interface ROS 2 tanpa memodifikasi kode sumber Python secara manual.

---

### 3.3 Mekanisme Fail-Closed vs Silent Mock Fallback

Terdapat perbedaan filosofi penanganan kesalahan fatal antara spesifikasi keamanan dan implementasi aktual:
- **Klaim Desain Keamanan:** Jika terjadi anomali transmisi atau hardware failure, sistem harus *fail-closed* (menghentikan robot secara instan untuk mencegah tabrakan).
- **Implementasi di [fpga_bridge.py (ros2_ws)](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/fpga_bridge.py#L85-L100):**
  Saat `serial.Serial()` gagal membuka port fisik, fungsi langsung menangkap `SerialException`, mencetak peringatan di log, lalu diam-diam mengalihkan diri ke `mock = True`:
  ```python
  except serial.SerialException as e:
      self.logger.warn(f"Failed to open FPGA serial port '{port}': {e}. Using MOCK mode.")
      self.mock = True
  ```
- **Dampak:** Operator di lapangan mungkin mengira inferensi sedang dihitung oleh chip FPGA DE10-Nano, padahal sistem diam-diam beralih ke kalkulasi mock CPU lokal tanpa peringatan keras (*silent failure*).

---

## 4. Audit Temuan Kategori 3: Desinkronisasi Dual-Codebase Software Stack

### 4.1 Disparitas `ros2_ws/src/` vs `fpga/software_integration/src/`

Repositori memiliki dua pohon kode paket ROS 2 yang terduplikasi secara penuh:
1. `ros2_ws/src/` (workspace aktif yang dibangun oleh `colcon build`)
2. `fpga/software_integration/src/` (tree internal yang disimpan di subdirektori FPGA)

Analisis `diff` mendalam menunjukkan divergensi fungsional yang signifikan:

```
diff -u fpga/software_integration/src/igor_controller/igor_controller/fpga_bridge.py \
        ros2_ws/src/igor_controller/igor_controller/fpga_bridge.py
```

| Fitur / Parameter | `fpga/software_integration/` | `ros2_ws/` | Evaluasi Kritis |
|---|---|---|---|
| **Default Baud Rate** | `921600` | `115200` | Versi `software_integration` benar, versi `ros2_ws` salah/rusak. |
| **Penanganan Serial Error** | Melempar `FPGACommunicationError` (Fail-Closed) | Menelan exception & fallback ke Mock (Silent) | Versi `software_integration` mematuhi kaidah *safety-critical*. |
| **Validasi Rentang Observasi** | Ada validasi `np.any(obs[:64] < 0)` sebelum transmisi | Validasi dihapus | Versi `ros2_ws` berisiko mengirim data out-of-range ke FPGA. |
| **Argumen Launch File** | Mendeklarasikan `fpga_baudrate` | Menghapus `fpga_baudrate` | Regresi fitur konfigurasi pada `ros2_ws`. |

---

### 4.2 Skrip CI/CD Test Menguji Kode Mirror yang Usang (Blind Verification)

Skrip verifikasi host otomatis [run_host_regression.py (Baris 20–22)](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/verification/run_host_regression.py#L20-L22) mendefinisikan path impor modul sebagai berikut:
```python
ROOT = Path(__file__).resolve().parents[2]
SW_DIR = ROOT / "fpga" / "software_integration" / "src" / "igor_controller"
sys.path.insert(0, str(SW_DIR))
from igor_controller.fpga_bridge import FPGABridge
```

#### Analisis Dampak:
Pipeline CI (`rtl-verification.yml` dan `run_all_checks.py`) melakukan pengujian terhadap `fpga/software_integration`, sehingga seluruh automated test di GitHub Actions melaporkan status **PASS (Hijau)**. Padahal kode yang sebenarnya dieksekusi di robot adalah kode di `ros2_ws/src/` yang memiliki bug baud rate 115,200. Ini menciptakan ilusi integritas (*false sense of security*).

---

## 5. Audit Temuan Kategori 4: Logika AI, Kontrol Keselamatan & Normalisasi Sensor

### 5.1 Bypass Total Filter Keselamatan CBF (`obstacles=None`) di Runtime ROS 2

Ini adalah **temuan audit konseptual dan implementasi paling kritis pada stack AI**:

#### Klaim Ilmiah & Pemasaran:
Pada [README.md baris 135](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/README.md#L135) dan [ros2_ws/README.md baris 103–115](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/README.md#L103-L115), tim mengklaim:
> *"Safety Layer: Control Barrier Function (CBF) Safety Filter providing formal Nagumo forward invariance guarantees with Quadratic Programming (QP) solver ensuring 100% collision-free navigation."*

#### Kode Aktual pada Loop Pengendali ([controller_node.py baris 263–272](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L263-L272)):
```python
if self.algorithm == 'cl_drl_cbf':
    safe_vx, safe_vy, safe_wz, _ = self.cpu_controller.filter_cbf(
        cand_vx=float(v_blended[0]),
        cand_vy=float(v_blended[1]),
        cand_omega=float(v_blended[2]),
        robot_pose=(0.0, 0.0, 0.0),
        obstacles=None,               # <--- NILAI OBSTACLES DIOPER SEBAGAI NONE!
        allowed_max_vx=allowed_max_vx
    )
```

#### Implementasi Fungsi Filter ([cbf_safety_filter.py baris 55–60](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/controllers/cbf_safety_filter.py#L55-L60)):
```python
# Evaluate barrier constraints
G_rows = []
h_rows = []
if obstacles:
    for obs in obstacles:
        # compute barrier derivative L_f h + L_g h u + gamma * h
        ...
```

#### Analisis Dampak:
Karena parameter `obstacles` selalu dioper sebagai `None`, blok `if obstacles:` tidak pernah dieksekusi. 
- Constraint matriks kuadratik $G \mathbf{u} \le h$ **kosong melompong** terhadap seluruh rintangan LiDAR.
- Filter CBF hanya melakukan pembatasan akselerasi sederhana tanpa mempertimbangkan jarak ke dinding atau rintangan.
- Jaminan formal *"100% collision-free Nagumo invariance"* **sama sekali tidak aktif di lingkungan ROS 2 fisik**.
- Sebaliknya, dalam skrip simulasi benchmark offline ([retrain_ai.py baris 771](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/retrain_ai.py#L771)), parameter `obstacles=eval_obstacles` dioper secara benar sehingga menghasilkan metrik 0% collision pada simulasi.

---

### 5.2 Dead Code Mini-DWA Shield pada Jalur Eksekusi FPGA

Pada [controller_node.py baris 108–114](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L108-L114), algoritma `cl_drl_dwa` didaftarkan dalam `VALID_FPGA_ALGORITHMS` dan objek `MiniDWAShieldController` berhasil diinisialisasi.

Namun di dalam callback eksekusi kontrol utama ([controller_node.py baris 263–274](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L263-L274)):
```python
if self.algorithm == 'cl_drl_cbf':
    safe_vx, safe_vy, safe_wz, _ = self.cpu_controller.filter_cbf(...)
else:
    # plain zero stop
    safe_vx = float(v_blended[0]) if min_lidar > 0.15 else 0.0
    safe_vy = float(v_blended[1]) if min_lidar > 0.15 else 0.0
    safe_wz = float(v_blended[2]) if min_lidar > 0.15 else 0.0
```
Tidak ada cabang `elif self.algorithm == 'cl_drl_dwa':` untuk memanggil filter DWA shield. Jika pengguna memilih algoritma `cl_drl_dwa` dengan mode FPGA, DWA Shield tidak pernah dieksekusi dan hanya menggunakan pemotongan kecepatan nol primitif (`min_lidar > 0.15`).

---

### 5.3 Runtime Crash Akibat Ketidakcocokan Registri Algoritma (`cl_drl_dwa_shield`)

- Pada panduan resmi [ros2_ws/README.md baris 140](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/README.md#L140):
  ```bash
  ros2 launch igor_bringup bringup.launch.py algorithm:=cl_drl_dwa_shield
  ```
- Namun pada registri modul pengendali ([controllers/__init__.py baris 13–27](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/controllers/__init__.py#L13-L27)):
  ```python
  CONTROLLER_REGISTRY = {
      'cl_drl_cbf': CLDRLCBFController,
      'cl_drl_dwa': CLDRLDWAController,
      'dwa_shield': CLDRLDWAController,
      'mini_dwa': CLDRLDWAController,
      'drl_dwa': CLDRLDWAController,
      'cl_drl': CLDRLController,
      ...
  }
  ```
- String `"cl_drl_dwa_shield"` **tidak terdaftar**.
- Mengeksekusi perintah sesuai dokumentasi resmi akan langsung memicu eksepsi:
  `ValueError: Unknown controller 'cl_drl_dwa_shield'. Available: ['cl_drl_cbf', 'cl_drl_dwa', ...]` dan mematikan seluruh stack bringup robot.

---

### 5.4 Inkonsistensi Kritis Normalisasi Akselerasi Z (IMU): 3.0 vs 9.81

Vektor observasi input AI memiliki 74 elemen, di mana indeks 64..66 adalah akselerasi linier $(a_x, a_y, a_z)$:

1. **Pipeline Pelatihan ([retrain_ai.py baris 337](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/retrain_ai.py#L337)):**
   ```python
   norm_imu[2] = np.clip(accel_z / 9.81, -1.0, 1.0)
   ```
2. **Controller Inferensi CPU ([drl_controller.py baris 143](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/controllers/drl_controller.py#L143)):**
   ```python
   norm_imu[2] = np.clip(az / 9.81, -1.0, 1.0)
   ```
3. **Controller Node ROS 2 untuk FPGA ([controller_node.py baris 235](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L235)):**
   ```python
   obs[66] = float(az) / 3.0   # <--- DIBAGI 3.0, BUKAN 9.81!
   ```

#### Analisis Dampak Kuantitatif:
- Jika telemetri STM32 mengirim akselerasi dalam satuan standar $\text{m/s}^2$ ($a_z \approx 9.81\ \text{m/s}^2$ pada kondisi diam):
  $$\text{obs}[66] = \frac{9.81}{3.0} = 3.27$$
  Protokol FPGA Q8.8 mensyaratkan setiap elemen observasi berada pada rentang $[-1.0, +1.0]$. Nilai $3.27$ melanggar rentang validasi hardware dan memicu modul FSM FPGA menolak frame input dengan status `reject(8'd8)`.
- Jika telemetri STM32 mengirim dalam satuan $g$ ($a_z \approx 1.0\ g$):
  $$\text{obs}[66] = \frac{1.0}{3.0} = 0.333$$
  Sedangkan saat pelatihan, $1.0\ g$ dinormalisasi menjadi $1.0 / 9.81 \approx 0.102$ (jika satuan $\text{m/s}^2$) atau $1.0$ (jika $g$). Mismatch skala sebesar $\mathbf{3.27\times}$ lipat menyebabkan drift distribusi fitur yang merusak inferensi neural network.

---

### 5.5 Inkonsistensi Satuan Gyroscope (rad/s vs deg/s) antara Mode CPU & FPGA

Pada modul telemetri serial STM32 ([mcu_driver.py baris 172](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/mcu_driver.py#L172)), sensor gyroscope dibaca dalam satuan **derajat per detik (deg/s)**:
```python
self.gyro = [gx * 0.01, gy * 0.01, gz * 0.01]  # deg/s
```

Di [controller_node.py](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py):
- **Jalur FPGA (Baris 236–238):**
  ```python
  obs[67] = math.radians(gx) / 2.0
  obs[68] = math.radians(gy) / 2.0
  obs[69] = math.radians(gz) / 2.0
  ```
  Di sini nilai dikonversi ke radian terlebih dahulu. Misal rotasi $30^\circ/\text{s} \to 0.523\ \text{rad/s} \to \text{obs}[69] = 0.261$ (masuk akal dalam rentang $[-1, 1]$).
- **Jalur CPU (Baris 283):**
  `self.cpu_controller.predict(...)` menerima `gx, gy, gz` mentah tanpa `math.radians()`.
  Di dalam [drl_controller.py baris 144](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/controllers/drl_controller.py#L144):
  `norm_imu[5] = np.clip(wz / 2.0, -1.0, 1.0)`.
  Rotasi $30^\circ/\text{s}$ dibagi 2 menjadi $15.0$, yang langsung terpotong (*clipped*) secara jenuh ke batas maksimum `1.0`. Model CPU mengalami saturasi konstan pada sinyal yaw rate.

---

### 5.6 Kontradiksi Tahapan Kurikulum Pelatihan (Klaim 3-Stage vs Kode 4-Stage)

- **Klaim Dokumentasi ([README.md baris 92](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/README.md#L92) & [ros2_ws/README.md baris 88](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/README.md#L88)):**
  Mendokumentasikan *"Progressive Curriculum Learning across 3 progressive difficulty stages (Stage 1 Kinematic Goal Reaching, Stage 2 Dense Static Clutter, Stage 3 Dynamic Stress & Chaos)"*.
- **Implementasi Kode ([retrain_ai.py baris 227–268](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/retrain_ai.py#L227-L268)):**
  Kurikulum pelatihan menggunakan **4 tahapan (Stage 1 s.d. Stage 4)**:
  - *Stage 1:* Basic Goal Reaching
  - *Stage 2:* Static Obstacle Avoidance
  - *Stage 3:* Moving Obstacles
  - *Stage 4:* Complex Dynamic Environment with Tight Corridors

---

### 5.7 Inkonsistensi Parameter & Inversi Kinematika Mecanum

1. **Batas Kecepatan Roda Maksimum (`max_rps`):**
   - Di [kinematics.py baris 25](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/utils/kinematics.py#L25), default `max_rps = 3.0` putaran/detik.
   - Di [controller_node.py baris 99](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L99), didefinisikan `max_rps = 5.0` putaran/detik.
2. **Algoritma Desaturasi Vektor Kecepatan Roda:**
   - [kinematics.py](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/utils/kinematics.py#L51-L54) menggunakan **desaturasi proporsional**:
     ```python
     if max_motor_rps > self.max_rps:
         scale = self.max_rps / max_motor_rps
         motor_rps = [rps * scale for rps in motor_rps]
     ```
     Ini mempertahankan arah heading dan vektor translasi robot meskipun salah satu roda mengalami saturasi.
   - [controller_node.py baris 298–302](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L298-L302) menggunakan **clipping independen**:
     ```python
     raw_rps = [np.clip(r, -self.max_motor_rps, self.max_motor_rps) for r in raw_rps]
     ```
     Clipping independen mengubah rasio kecepatan antar roda, sehingga robot akan berbelok secara liar (*trajectory distortion*) saat mendekati batas kecepatan maksimum.

---

## 6. Audit Temuan Kategori 5: Integritas Verifikasi (Cryptographic Provenance)

### 6.1 Kegagalan Verifikasi Integritas Rilis (`freeze_release.py --check`)

Dokumen [README.md baris 256](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/README.md#L256) menginstruksikan pengujian integritas rilis resmi:
```bash
cd fpga
python scripts/freeze_release.py --check
```

#### Hasil Eksekusi Aktual:
Perintah tersebut mengalami **kegagalan fatal (crash)**:
```text
RuntimeError: Changed or missing recorded files:
- bitstreams/igor_planner.sof
- bitstreams/igor_src_policy.sof
- docs/BUILD_STATUS.md
- docs/CHIP_ADVANTAGES.md
- ...
```

#### Analisis Penyebab:
File [fpga/evidence/current_release/manifest.json](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/evidence/current_release/manifest.json) mengunci hash SHA-256 berkas bitstream dan puluhan file dokumentasi. Pada commit `2329cf5`, file-file markdown dokumentasi dan catatan kompilasi telah diperbarui, tetapi manifest pelepasan (*frozen manifest*) tidak diperbarui (*re-freeze*). Akibatnya, verifikasi jaminan anti-tampering gagal.

---

### 6.2 Retraining Pipeline Terputus dari RTL Memory ROM FPGA

Ketika pengguna mengeksekusi pipeline pelatihan ulang model AI:
```bash
python3 ros2_ws/src/igor_navigation/igor_navigation/retrain_ai.py
```
1. Skrip menyimpan bobot PyTorch ke `best_policy.pth` dan mengekspor bobot kuantisasi Q8.8 ke berkas memori terpisah per layer:
   `ros2_ws/src/igor_navigation/igor_navigation/weights/hardware/layer{1,2,3}_{w,b}.mem`.
2. **Keterputusan ke FPGA RTL:**
   - Modul Verilog FPGA monolitik ([igor_src_policy_core.v](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/rtl/igor_src_policy/igor_src_policy_core.v)) membaca berkas memori gabungan:
     `fpga/rtl/igor_src_policy/policy_weights.mem`.
   - Modul Parallel8 membaca:
     `fpga/experiments/parallel8/mem/bank{0..7}.mem`.
   - `retrain_ai.py` **tidak mengompilasi ulang maupun menyalin** bobot baru ke dalam `policy_weights.mem` atau bank Parallel8.
   - `retrain_ai.py` juga tidak memperbarui `model_provenance.json`.
3. **Dampak:** Model CPU akan berjalan dengan bobot baru, sedangkan bitstream FPGA tetap menjalankan bobot lama, menyebabkan diskrepansi inferensi yang masif antara mode simulasi dan mode FPGA.

---

## 7. Audit Temuan Kategori 6: Dokumentasi, Broken Links, dan Metadata Package

### 7.1 Broken Links pada Dokumentasi Utama & Absolute Path Leak

1. **Broken Link Repositori Root ([README.md baris 8 & 213](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/README.md#L8)):**
   - Tautan `[parallel8](experiments/parallel8/README.md)` rusak (seharusnya `fpga/experiments/parallel8/README.md`).
   - Tautan `experiments/parallel8/igor_src_policy.qpf` rusak (seharusnya `fpga/experiments/parallel8/igor_src_policy.qpf`).
2. **Kebocoran Absolute Path Lokal Pengembang:**
   Pada file [fpga/robot/jetauto/motor_data_flow_original.md](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/robot/jetauto/motor_data_flow_original.md), terdapat 8 tautan absolut yang merujuk ke direktori pribadi laptop pengembang:
   `file:///home/karol/jetauto_backup/...` yang tidak ada di sistem repositori publik.
3. **Broken Links Bukti Verifikasi:**
   Pada [fpga/docs/EVIDENCE.md](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/docs/EVIDENCE.md), terdapat lebih dari 20 tautan relatif ke folder `evidence/audit/` dan `evidence/waveforms/` yang tidak tersedia di tree git.

---

### 7.2 Metadata Penulis TinyTapeout `info.yaml` (Jane Street Upstream Artifact)

Pada [info.yaml baris 4–5](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/info.yaml#L4-L5):
```yaml
author:       "wlmoi"
discord:      "icdesignboi"
```
Metadata penulis masih mencantumkan identitas pengembang repositori sumber upstream kompetisi Jane Street UK, bertentangan dengan identitas tim resmi lomba (**iSeeDesignITB**).

Selain itu, pada `info.yaml` baris 19–25, daftar `source_files` hanya mencakup 5 berkas:
```yaml
source_files:
  - "igorchip_top.v"
  - "program_host.v"
  - "program_memory.v"
  - "sram_256x16_bb.v"
  - "sram_256x16.v"
```
Sedangkan pada [test/Makefile baris 9](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/test/Makefile#L9), berkas `top.v` dimasukkan dalam kompilasi (`PROJECT_SOURCES`).

---

### 7.3 Konflik Versi Dependensi Python Environment

Terdapat ketidakcocokan versi paket pengetesan pada berkas dependensi:
- Root ASIC Test ([test/requirements.txt](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/test/requirements.txt)):
  `cocotb==2.0.1`, `pytest==8.4.2`.
- FPGA Test ([fpga/requirements.txt](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/fpga/requirements.txt)):
  `cocotb==1.9.2`, `pytest==8.3.5`.
Perbedaan versi mayor cocotb (v1.x vs v2.x) memiliki breaking changes pada API trigger dan clock generator.

---

## 8. Matriks Remediasi & Rencana Aksi Terstruktur (Actionable Fixes)

Untuk memastikan sistem siap 100% sebelum live demonstration di hadapan dewan juri PERURI, berikut adalah langkah remediasi kode konkret berdasarkan prioritas:

### 8.1 Tindakan Remediasi Prioritas 1 (P1 - Kritis & Wajib)

#### A. Perbaikan Baud Rate & Expose Parameter Launch File
1. Edit [controller_node.py](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L58-L62):
   ```python
   # Tambahkan deklarasi parameter baudrate
   self.declare_parameter('fpga_baudrate', 921600)
   self.fpga_baudrate = self.get_parameter('fpga_baudrate').value
   
   # Ganti instansiasi FPGABridge
   if self.use_fpga:
       self.fpga = FPGABridge(
           port=self.fpga_port,
           baudrate=self.fpga_baudrate,
           mock=self.use_mock_serial
       )
   ```
2. Edit [bringup.launch.py](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_bringup/launch/bringup.launch.py):
   ```python
   DeclareLaunchArgument('fpga_baudrate', default_value='921600', description='FPGA UART baudrate'),
   # teruskan ke parameters controller_node:
   parameters=[{..., 'fpga_baudrate': LaunchConfiguration('fpga_baudrate')}]
   ```

#### B. Pengaktifan Rintangan LiDAR pada Filter CBF
Edit [controller_node.py baris 263–272](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L263-L272):
```python
# Ekstraksi titik rintangan dari subsampled LiDAR (64 rays)
cbf_obstacles = []
if self.latest_lidar_64 is not None:
    angles = np.linspace(-math.pi, math.pi, len(self.latest_lidar_64), endpoint=False)
    for dist, ang in zip(self.latest_lidar_64, angles):
        if 0.05 < dist < 1.5:  # hanya rintangan dalam jangkauan pengaruh CBF
            obs_x = dist * math.cos(ang)
            obs_y = dist * math.sin(ang)
            cbf_obstacles.append((obs_x, obs_y, 0.12))  # (x, y, radius)

if self.algorithm == 'cl_drl_cbf':
    safe_vx, safe_vy, safe_wz, _ = self.cpu_controller.filter_cbf(
        cand_vx=float(v_blended[0]),
        cand_vy=float(v_blended[1]),
        cand_omega=float(v_blended[2]),
        robot_pose=(0.0, 0.0, 0.0),
        obstacles=cbf_obstacles if len(cbf_obstacles) > 0 else None,
        allowed_max_vx=allowed_max_vx
    )
```

#### C. Standardisasi Normalisasi Akselerasi Z IMU
Edit [controller_node.py baris 235](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_controller/igor_controller/controller_node.py#L235):
```python
# Ubah pembagi dari 3.0 menjadi 9.81 sesuai distribusi training
obs[66] = float(np.clip(float(az) / 9.81, -1.0, 1.0))
```

---

### 8.2 Tindakan Remediasi Prioritas 2 (P2 - Tinggi)

#### A. Registrasi Alias `cl_drl_dwa_shield`
Edit [controllers/__init__.py](file:///home/karol/ITB/lomba/chip-peruri/peruri-ai-final/igor_ws/ros2_ws/src/igor_navigation/igor_navigation/controllers/__init__.py):
```python
CONTROLLER_REGISTRY = {
    'cl_drl_cbf': CLDRLCBFController,
    'cl_drl_dwa': CLDRLDWAController,
    'cl_drl_dwa_shield': CLDRLDWAController,  # <-- Tambahkan alias ini
    'dwa_shield': CLDRLDWAController,
    ...
}
```

#### B. Sinkronisasi Dual-Codebase
Jalankan sinkronisasi dari `ros2_ws/src` ke `fpga/software_integration/src` atau jadikan `ros2_ws/src` sebagai target import tunggal pada `fpga/verification/run_host_regression.py`.

#### C. Reframing Arsitektur Aliran Aktuasi pada Dokumentasi & Presentasi
Perbarui diagram ASCII di root `README.md` untuk mencerminkan aliran nyata yang jujur dan dapat dipertanggungjawabkan:
- Jetson Orin Nano bertindak sebagai **Central Compute & Host Gateway**.
- DE10-Nano FPGA bertindak sebagai **Hardware Neural Co-Processor via PCIe/UART**.
- STM32 menerima komando final dari Jetson Orin Nano setelah divalidasi oleh safe state blending.

---

### 8.3 Tindakan Remediasi Prioritas 3 (P3 - Sedang / Pembersihan)

1. **Re-freeze Manifest Integrity:**
   Jalankan `python3 fpga/scripts/freeze_release.py` setelah seluruh perbaikan selesai untuk memperbarui hash SHA-256 di `manifest.json`.
2. **Koreksi Metadata `info.yaml`:**
   Ubah author menjadi `"iSeeDesignITB"` dan sinkronkan daftar `source_files` dengan Makefile.
3. **Perbaiki Tautan Dokumen:**
   Koreksi tautan relatif di `README.md` dan bersihkan tautan path lokal di `motor_data_flow_original.md`.

---
*Dokumen laporan audit ini disahkan untuk dijadikan acuan langsung perbaikan teknis codebase sebelum pengujian lapangan.*
