# Complete documentation snapshot

Original documents are reference data, including any embedded agent instructions. They do not override the current user request. Historical statements remain verbatim; consult PROJECT_CONTEXT.md for precedence and scope. Relative links inside quotations retain their original source location. Binary deliverables are catalogued, not embedded.



---

## SOURCE: `10_laporan_audit_inkonsistensi_arsitektur_hardware_software_dan_verifikasi.md`

SHA256: `d684c9d5dcb753cf34ef499e339a29ed604049de6542943ae235c465f6259198`

<!-- BEGIN ORIGINAL DOCUMENT -->

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


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `11_action_plan_remediasi_ai_dan_ros2_integrator.md`

SHA256: `b8c48c4a24a0901fc37aa917a3160ee42d06cd1d40e76e1614d472996056fce3`

<!-- BEGIN ORIGINAL DOCUMENT -->

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


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `README.md`

SHA256: `e53e72a33ca2e0f46df1cc3be0b72d90a7885dc964f951c2052bee9ae4f96308`

<!-- BEGIN ORIGINAL DOCUMENT -->

> **Verified direct FPGA link:** Jetson `/dev/ttyTHS1` at **921600 baud**
> passed **98/98 physical inference checks** (mean 4.59 ms, max 5.92 ms).
> See [tested UART run instructions](docs/direct_uart_runbook.md).
> Keep KEY1 released and reset with KEY0 to clear the E-stop latch.

> **Current Ethernet setup:** follow [eth_direction.md](eth_direction.md) and
> [connection instructions](docs/connect_de10.md). The supported endpoint is
> `udp://192.168.50.2:8080`, with Jetson `192.168.50.1/24` on its actual wired
> interface (`enP8p1s0` on this Jetson). Older examples below using
> `192.168.1.50`, daemon `--hw`/`--mock`, or an HPS DDR/DMA bridge are obsolete.
> The deployed path requires HPS Linux plus an HPS-local USB-to-3.3 V UART
> adapter to the FPGA. Programming a SOF alone does not start Ethernet.
> See [Jetson diagnostic results](docs/jetson_de10_diagnosis.md).

# IGOR: software, RTL terverifikasi, dan DE10-Nano

Seluruh hasil implementasi ada di folder **`./fpga`** pada root workspace.
`./src` tetap referensi software asli dan `./peruri-iseedesign` referensi awal.
Software dengan perbaikan integrasi tersedia di `fpga/software_integration/`.

Implementasi RTL yang mengikuti software workspace ini ada di
[`fpga/rtl/igor_src_policy/`](fpga/rtl/igor_src_policy/README.md).
Buka proyek Quartus 25
[`fpga/fpga_de10_nano/src_policy/igor_src_policy.qpf`](fpga/fpga_de10_nano/src_policy/igor_src_policy.qpf).
Pin planning sudah disertakan dan dijelaskan lengkap di
[README board](fpga/fpga_de10_nano/src_policy/README.md).
Semua persyaratan, edge case, serta A1–A14/B1–B6/D1–D7 dari dokumen checklist
dipetakan pada [kesiapan implementasi](fpga/docs/IMPLEMENTATION_READINESS.md).

**Dua model yang berbeda harus dibedakan.** Software `src` saat ini memakai
PPO residual **74 → 128 → 64 → 3**. Proyek legacy dalam `fpga`
memakai SAC **24 → 64 → 64 → 4** dan planner peta 128×128.
Angka 18.192 siklus/400 keluaran pada dokumentasi legacy bukan hasil jaringan
74 input. Core baru mengukur 54.348 siklus untuk inferensi Q8.8; kesamaan yang
diuji adalah RTL terhadap model integer independen dari bobot yang sama.
Galat terhadap model FP32 dilaporkan terpisah dalam hasil suite.

Arsitektur aktual jalur source: ROS menerima 64 beam LiDAR, 6 IMU, 3 perintah
twist, dan 1 heading → host membentuk 74 int16 Q8.8 → frame UART 153 byte
dengan CRC8 Maxim → FPGA memvalidasi frame/domain → ROM bobot + serial MAC
signed 16×16/akumulator 40 bit → ReLU 128/64 neuron → tiga residual dibatasi
[-256,256] → frame respons 11 byte → host blending/filter → kinematika empat
roda → STM32. UART default proyek baru **921600 8N1**.

Pada jalur planner legacy: host menulis seluruh peta ke bank tidak aktif →
validasi urutan/kelengkapan → commit atomik → empat tile memeriksa 512×20 pose →
selector dengan tie-break indeks → safety gate → `motor_enable`, `v_command`,
`omega_command`, kode gangguan, penghitung kejadian, dan last fault.
E-stop, peta tidak valid/usang, konfigurasi berubah, timeout, hasil tidak valid,
overflow serta batas kecepatan/perubahan menutup gate dan menolkan output.
Abort menyimpan penyebab awal sampai reset agar log tetap dapat menjelaskan
penolakan. Opcode 15/16 membaca penghitung/penyebab tersimpan melalui UART.

**Batas integrasi:** protokol observasi 74 input tidak membawa costmap.
`safety_permit` pada core neural berarti residual valid dan segar; izin motor
dengan pemeriksaan peta adalah keluaran gate planner legacy. Belum ada klaim
bahwa model baru, pemeriksa peta, dan aktuator motor sudah menyatu di FPGA.
Controller source masih melakukan blending/filter di Jetson. Checklist A4/A5
kurir tanpa keputusan memerlukan implementasi dan uji integrasi berikutnya.

Perbaikan fail-closed software: mode hardware tidak otomatis berubah menjadi
mock jika port hilang; timeout/CRC salah/frame salah/residual di luar rentang
melempar error dan controller mengirim **empat RPS nol**. Hal ini diperlukan
karena residual AI nol masih dapat menyisakan perintah operator nonnol.
Perintah tidak finite/di luar batas, perintah kedaluwarsa, serta LiDAR hilang
atau kedaluwarsa juga menghentikan motor. Mock harus dipilih secara eksplisit.

Verifikasi dapat diulang dari `fpga`:

```powershell
python verification/src_policy/run.py --check
python verification/run_safety_regression.py
python verification/run_host_regression.py
python verification/run.py all
python verification/run.py tt_generic
```

Suite safety baru membandingkan **111.210 vektor** dengan oracle Python,
menjangkau seluruh kode fault 0–11, seluruh kombinasi kontrol yang dienumerasi,
batas aritmetika, urutan map/config, freshness, deadline, E-stop saat run/result,
serta malformed UART. Daftar batas pengujian dan SHA source berada di
`fpga/evidence/current_safety/summary.json`. Ini bukan pembuktian
formal seluruh state/peta/urutan temporal yang mungkin.

Untuk melihat **titik persis di GTKWave**, dari folder `fpga`:

```powershell
gtkwave evidence/current_safety/top.vcd evidence/current_safety/top.gtkw
gtkwave evidence/current_safety/gate.vcd evidence/current_safety/gate.gtkw
gtkwave evidence/current_safety/uart.vcd evidence/current_safety/uart.gtkw
```

Gunakan satuan **ns** pada tabel berikut (VCD menyimpan resolusi ps). Sinyal
`core` berada pada `tb_safety_top.core`; CSV juga menyebut instance varian
deadline/freshness agar tidak salah membaca output.

| Bukti | Waktu ns | Yang harus terlihat |
|---|---:|---|
| `top.vcd`: hasil normal | 814531 | enable=1, v=15, omega=0, fault=0 |
| E-stop di antara clock | 814535 | enable=0, v=0, omega=0, fault=2 langsung |
| Log E-stop pada clock berikut | 814551 | event_count=3, last_fault=2 |
| E-stop dilepas | 814572 | output tetap nol; perlu reset |
| Peta tidak valid | 2931031 | output nol, fault=5, last_fault=5 |
| Deadline komputasi, `deadline_core` | 3904291 | output nol, fault=8, last_fault=8 |
| Peta tepat kedaluwarsa, `freshness_core` | 3945471 | output nol saat map_age=10000 |
| `gate.vcd`: batas kecepatan | 11 | output nol, fault=10 |
| `gate.vcd`: perubahan mendadak | 12 | output nol, fault=11 |

Seluruh **111 checkpoint** dan konteks lainnya ada pada
[`cases.csv`](fpga/evidence/current_safety/cases.csv),
[`top_checkpoints.csv`](fpga/evidence/current_safety/top_checkpoints.csv),
dan log suite. Untuk neural baru, buka `verification/src_policy/artifacts/`
dengan save file `.gtkw` dan `*_checkpoints.csv` yang dijelaskan pada
[README RTL](fpga/rtl/igor_src_policy/README.md).

GitHub Actions tersedia di [workflow workspace](.github/workflows/rtl-verification.yml)
dan workflow repository RTL. Job Quartus memakai runner Windows dengan Quartus
25 terpasang; simulator memakai Icarus. Workflow mengunggah log, waveform,
hasil numerik, dan provenance. Dua folder memiliki repository Git masing-masing;
lihat instruksi checkout berpasangan pada checklist sebelum publikasi.

**Status hardware:** sesi ini mendeteksi **No JTAG hardware available**.
Simulasi dan kompilasi tidak menggantikan uji board. Belum diklaim: pengukuran
STOP roda, video E-stop, daya board, latency Jetson-FPGA fisik, atau lintasan
robot baru. Skrip capture safety dan prosedur penerimaan tersedia di checklist.

---

# JetAuto Mecanum AMR Autonomous Navigation & Obstacle Avoidance Suite

**Project IGOR** adalah sistem navigasi dan penghindaran rintangan (*obstacle avoidance*) otonom berbasis *Curriculum-Learned Deep Reinforcement Learning* (CL-DRL) dengan lapisan keselamatan formal (*Control Barrier Function* & *mini-DWA Shield*) untuk robot fisik **Hiwonder JetAuto Mecanum AMR**.

Workspace ini didesain secara modular untuk berjalan pada **ROS 2 Humble** di atas **NVIDIA Jetson Orin Nano**, terintegrasi langsung dengan mikrokontroler sasis **STM32**, sensor **Slamtec RPLiDAR A1**, serta akselerator hardware **Terasic DE10-Nano FPGA**.

---

## 📑 Daftar Isi
1. [Arsitektur Paket Workspace](#1-arsitektur-paket-workspace)
2. [Alur Data Sistem (Dataflow Pipeline)](#2-alur-data-sistem-dataflow-pipeline)
3. [Integrasi Hardware & Port Serial](#3-integrasi-hardware--port-serial)
4. [Cara Menjalankan (Single-Command Bringup)](#4-cara-menjalankan-single-command-bringup)
5. [Cara Mengendalikan Robot](#5-cara-mengendalikan-robot)
6. [Monitoring & Telemetri Real-Time](#6-monitoring--telemetri-real-time)
7. [Pelatihan Ulang Model (Retraining AI)](#7-pelatihan-ulang-model-retraining-ai)

---

## 1. Arsitektur Paket Workspace

```
igor_ws/
├── README.md                        # Panduan integrasi & operasional sistem
└── src/
    ├── igor_navigation/             # [Pustaka Algoritma & Bobot Model]
    │   ├── package.xml              # Manifest paket ROS 2
    │   ├── setup.py                 # Instalasi modul & console script
    │   ├── retrain_ai.py -> ...     # Symlink skrip retraining otomatis
    │   └── igor_navigation/
    │       ├── retrain_ai.py        # Skrip otomatis retraining PPO & evaluasi 5 algoritma
    │       ├── controllers/         # 5 Algoritma (cl_drl, cl_drl_cbf, cl_drl_dwa, dwa, apf)
    │       ├── drivers/             # Resampling LiDAR 360° -> 64 berkas frontal
    │       ├── utils/               # Kinematika Mecanum, GlobalPath, LookaheadCarrotTracker
    │       ├── weights/             # Bobot inferensi bit-true (.json, .onnx, .zip, .h, .mem)
    │       └── evaluations/         # Grafik komparatif & 5 animasi GIF durasi penuh
    │
    ├── igor_controller/             # [Node Kontroler ROS 2 & Driver Perangkat Keras]
    │   ├── package.xml
    │   ├── setup.py
    │   └── igor_controller/
    │       ├── controller_node.py   # Node pengendali utama 50 Hz & Strict FPGA Guard
    │       ├── heading_estimator.py # Autokalibrasi Gyro Z, Integrasi Yaw & Course-Lock Tracker
    │       ├── mcu_driver.py        # Driver serial STM32 /dev/ttyACM0 @ 1 Mbps (IMU RX & Motor TX)
    │       └── fpga_bridge.py       # Driver serial UART DE10-Nano FPGA (Q8.8 framing)
    │
    └── igor_bringup/                # [Orkestrasi Peluncuran & Driver Sensor]
        ├── package.xml
        ├── setup.py
        ├── igor_bringup/
        │   └── rplidar_driver_node.py # Driver serial RPLiDAR A1/A2 (/dev/lidar -> /scan)
        ├── launch/
        │   └── bringup.launch.py    # Master launch file single-command
        └── config/
            ├── igor_params.yaml     # Parameter konfigurasi sistem
            └── 99-jetauto-devices.rules # Udev rules untuk port serial robot
```

---

## 2. Alur Data Sistem (Dataflow Pipeline)

Pipeline data berjalan secara deterministik pada frekuensi **50 Hz** ($dt = 0.02\text{ s}$):

```mermaid
flowchart TD
    subgraph SENSORS["Perangkat Keras Sensor Fisik"]
        LIDAR_HW["Slamtec RPLiDAR A1 - /dev/lidar @ 115.200 bps"]
        STM32_HW["STM32 & MPU-6050 IMU - /dev/ttyACM0 @ 1.000.000 bps"]
    end

    subgraph DRIVERS["Driver Serial Dedicated"]
        LIDAR_HW -->|Paket 5-Byte RPLiDAR| RPLIDAR_NODE["rplidar_driver_node di igor_bringup"]
        RPLIDAR_NODE -->|Publish 10 Hz| SCAN_TOPIC["Topik /scan: LaserScan 360 deg"]

        STM32_HW -->|Paket Func 0x07 24-Byte| MCU_RX["Background Thread Reader di mcu_driver.py"]
        MCU_RX -->|Float32 LE Unpack| IMU_DATA["IMU: ax, ay, az dalam g, gx, gy, gz dalam deg/s"]
    end

    subgraph INPUT_CMD["Perintah Kecepatan Operator"]
        OPERATOR["Teleop Gamepad / Keyboard / Nav2"] -->|geometry_msgs/Twist| CMD_TOPIC["Topik /cmd_vel"]
    end

    subgraph HEADING_ENGINE["Heading & Course-Lock Engine di heading_estimator.py"]
        IMU_DATA --> CALIB["Autokalibrasi Statis Zero-Bias Gyro Z - 100 Sampel Pertama"]
        CALIB --> YAW_INT["Integrasi Real-Time 50 Hz: yaw_robot = yaw + gyro_z - bias * dt"]
        CMD_TOPIC --> CLOCK["Course-Lock Tracker: Kunci yaw_target jika abs omega_cmd < 0.02"]
        YAW_INT --> DELTA_THETA["Selisih Sudut Hadap: delta_yaw = wrap_to_pi target - robot"]
        CLOCK --> DELTA_THETA
        DELTA_THETA --> OBS_73["Normalisasi: obs_73 = clip delta_yaw / pi, -1, 1"]
        DELTA_THETA --> PUB_HEAD["Publish Topik: /igor/heading"]
    end

    subgraph CONTROLLER["IgorControllerNode di igor_controller"]
        SCAN_TOPIC --> SUBSAMP["LidarSubsampler: Resample 360 deg ke 64 Frontal Beams"]
        SUBSAMP --> OBS_VEC["Vektor Observasi 74-Dimensi: 64 LiDAR, 3 Accel, 3 Gyro, 3 Twist, 1 Heading"]
        IMU_DATA --> OBS_VEC
        CMD_TOPIC --> OBS_VEC
        OBS_73 --> OBS_VEC

        OBS_VEC --> BRANCH{"Parameter: use_fpga"}
        BRANCH -->|False| CPU_PATH["Inferensi CPU NumPy / ONNX: CL-DRL / CBF / mini-DWA / DWA / APF"]
        BRANCH -->|True| FPGA_GUARD{"Validasi Algoritma CL-DRL?"}
        FPGA_GUARD -->|Bukan CL-DRL| FATAL["FATAL ERROR & SHUTDOWN: Tolak DWA/APF pada FPGA"]
        FPGA_GUARD -->|CL-DRL / CBF / mini-DWA| FPGA_SERIAL["Kirim 74 int16 Q8.8 ke /dev/fpga - Baca 3 Aksi Residual"]

        CPU_PATH --> SAFETY_GATE["Lapisan Keselamatan & Gating Blending: Adaptive Blending & Hard Stop"]
        FPGA_SERIAL --> SAFETY_GATE

        SAFETY_GATE --> SAFE_TWIST["Kecepatan Aman: v_safe vx, vy, omega_z"]
        SAFE_TWIST --> PUB_TWIST["Publish Topik: /igor/cmd_vel_safe"]
        SAFE_TWIST --> IK["Invers Kinematika Mecanum JetAuto: FL=+v1, RL=+v2, FR=-v3, RR=-v4 Mirrored"]
        IK --> SEND_MCU["Kirim Paket Serial Func 0x03 4x RPS ke STM32 /dev/ttyACM0 @ 1 Mbps"]
    end
```

---

## 3. Integrasi Hardware & Port Serial

### Pemetaan Port Default pada Jetson Orin Nano
* **STM32 Sub-Controller**: `/dev/ttyACM0` @ **1.000.000 bps** (bidirectional: IMU 6-DOF & perintah motor 4-roda).
* **Slamtec RPLiDAR A1**: `/dev/lidar` atau `/dev/ttyUSB0` @ **115.200 bps** (protokol biner scan kontinu).
* **Terasic DE10-Nano FPGA**: `/dev/fpga` atau `/dev/ttyUSB1` @ **115.200 bps** / **921.600 bps** (UART Q8.8 framing).

### Konfigurasi Akses Serial (Dilakukan Sekali pada Jetson)
Pastikan user Linux Anda memiliki izin akses ke port dialout/serial:
```bash
sudo usermod -a -G dialout $USER
# Terapkan rules udev JetAuto jika belum terpasang:
sudo cp src/igor_bringup/config/99-jetauto-devices.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

---

## 4. Cara Menjalankan (Single-Command Bringup)

### A. Kompilasi Workspace
Sebelum menjalankan sistem untuk pertama kali (atau setelah retraining), kompilasi workspace:
```bash
cd ~/peruri-ai-final/igor_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

---

### B. Perintah Eksekusi Berdasarkan Skenario

#### Skenario 1: Menjalankan CL-DRL + CBF Safety Filter pada CPU (Rekomendasi Utama)
Sistem menjalankan model CL-DRL yang diperkuat sertifikat Lyapunov Nagumo *Control Barrier Function* (QP filter) langsung pada prosesor Jetson:
```bash
ros2 launch igor_bringup bringup.launch.py algorithm:=cl_drl_cbf use_fpga:=false
```

#### Skenario 2: Menjalankan dengan Akselerasi Hardware DE10-Nano FPGA
Inferensi neural network dieksekusi oleh IP Core pada FPGA DE10-Nano dalam format fixed-point signed 16-bit Q8.8:
```bash
ros2 launch igor_bringup bringup.launch.py algorithm:=cl_drl_cbf use_fpga:=true fpga_port:=/dev/fpga
```

#### Skenario 3: Menjalankan Algoritma DWA atau APF Standalone pada CPU
Untuk benchmarking perbandingan dengan algoritma navigasi reaktif klasik:
```bash
# Dynamic Window Approach (Anti-Freeze Rollout):
ros2 launch igor_bringup bringup.launch.py algorithm:=dwa use_fpga:=false

# Artificial Potential Field (64 Beams Repulsion):
ros2 launch igor_bringup bringup.launch.py algorithm:=apf use_fpga:=false
```

#### Skenario 4: Mode Simulasi / Headless (Uji Coba Tanpa Robot Fisik)
Menjalankan bringup lengkap tanpa perlu mencolokkan perangkat keras serial:
```bash
ros2 launch igor_bringup bringup.launch.py algorithm:=cl_drl_cbf use_mock_serial:=true
```

---

### C. Daftar Parameter Launch yang Tersedia

| Parameter | Tipe | Nilai Default | Deskripsi |
| :--- | :---: | :---: | :--- |
| `algorithm` | string | `cl_drl_cbf` | Pilihan: `cl_drl`, `cl_drl_cbf`, `cl_drl_dwa`, `dwa`, `apf`. |
| `use_fpga` | bool | `false` | Mengaktifkan akselerator DE10-Nano FPGA (khusus varian CL-DRL). |
| `mcu_port` | string | `/dev/ttyACM0` | Port serial mikrokontroler sasis STM32 (@ 1 Mbps). |
| `fpga_port` | string | `/dev/fpga` | Port serial UART akselerator DE10-Nano FPGA. |
| `lidar_port` | string | `/dev/lidar` | Port serial sensor Slamtec RPLiDAR A1 (@ 115.200 bps). |
| `launch_lidar` | bool | `true` | Menentukan apakah driver LiDAR diluncurkan otomatis. |
| `use_mock_serial` | bool | `false` | Mode emulasi sensor jika port fisik belum terpasang. |
| `control_rate_hz` | double | `50.0` | Frekuensi loop kontrol utama (Hz). |

> [!IMPORTANT]
> **Strict FPGA Guard**:
> Jika Anda menyetel `use_fpga:=true` tetapi memilih algoritma non-neural seperti `dwa` atau `apf`, sistem **seketika menolak eksekusi dan melakukan shutdown terarah (FATAL ERROR)** untuk mencegah perilaku perangkat keras yang tidak terdefinisi.

---

## 5. Cara Mengendalikan Robot

Controller Project IGOR menerima perintah gerak melalui topik standar **`/cmd_vel`** (`geometry_msgs/msg/Twist`). Anda dapat mengendalikan robot menggunakan beberapa metode berikut:

### Metode A: Teleoperasi Keyboard (Komputer atau Terminal Jetson)
Jalankan node keyboard standar ROS 2 di terminal terpisah:
```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```
* `i` : Maju linier ($+v_x$)
* `,` : Mundur linier ($-v_x$)
* `j` : Belok kiri di tempat ($+\omega_z$)
* `l` : Belok kanan di tempat ($-\omega_z$)
* `J` (Shift+j) : Geser samping holonomik ke kiri (*strafe left*, $+v_y$)
* `L` (Shift+l) : Geser samping holonomik ke kanan (*strafe right*, $-v_y$)
* `k` : Berhenti darurat

### Metode B: Joystick Gamepad (Bluetooth / USB Wireless Dongle)
Jika menggunakan controller nirkabel bawaan JetAuto:
```bash
ros2 run joy joy_node
ros2 run teleop_twist_joy teleop_twist_joy --ros-args -p enable_button:=4
```

### Metode C: Navigasi Otonom Nav2 (Autonomous Global Planning)
Saat paket Nav2 dijalankan, controller server Nav2 mempublikasikan perintah ke `/cmd_vel`. Controller IGOR menyaring perintah dengan pengereman asimetris adaptif; keselamatan lintasan fisik tetap perlu divalidasi terhadap sensor, peta, pengereman, dan fixture robot sebenarnya.

### Metode D: Uji Perintah Langsung via CLI ROS 2
```bash
# Perintah maju lurus 0.35 m/s:
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.35, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"

# Perintah geser diagonal (Maju 0.25 m/s + Geser Kanan 0.20 m/s):
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.25, y: -0.20, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

> [!TIP]
> **Fitur Keselamatan Watchdog 0.5 Detik**:
> Jika tidak ada perintah baru yang masuk di `/cmd_vel` selama lebih dari **0.5 detik**, sasis secara otomatis berhenti seketika (*zero-velocity brake*) untuk mencegah robot bergerak liar jika sinyal komunikasi terputus.

---

## 6. Monitoring & Telemetri Real-Time

Buka terminal baru untuk memantau status operasional robot secara langsung:

### 1. Memantau Sudut Haluan & Heading Error
```bash
ros2 topic echo /igor/heading
```
* Menampilkan nilai selisih sudut haluan $\Delta \theta$ dalam radian ($[-\pi, \pi]$). Ketika robot melaju translasi murni, *Course-Lock* aktif mempertahankan haluan lurus stabil.

### 2. Memantau Perintah Kecepatan Aman Hasil Filter
```bash
ros2 topic echo /igor/cmd_vel_safe
```
* Menampilkan kecepatan $[v_x, v_y, \omega]$ aktual yang telah disesuaikan dengan amplop keselamatan (*asymmetric braking* dan *Nagumo barrier filter*).

### 3. Memantau Telemetri Lengkap Sistem (JSON)
```bash
ros2 topic echo /igor/diagnostics
```
Output menyediakan telemetri diagnostik komprehensif:
```json
{
  "algo": "cl_drl_cbf",
  "fpga": false,
  "d_min": 1.45,
  "cmd": [0.35, 0.0, 0.0],
  "safe": [0.35, 0.0, 0.0],
  "rps": [1.15, 1.15, -1.15, -1.15],
  "heading": {
    "calibrated": true,
    "gyro_bias_z_rad_s": 0.0014,
    "theta_robot_deg": 1.2,
    "theta_target_deg": 1.2,
    "delta_theta_deg": 0.0,
    "course_locked": true
  }
}
```
*(Catatan: Nilai RPS motor ke-3 dan ke-4 bernilai negatif mencerminkan pembalikan tanda mekanikal roda kanan sasis JetAuto).*

---

## 7. Pelatihan Ulang Model (Retraining AI)

Jika Anda ingin melatih ulang kebijakan DRL dengan variasi kurikulum atau dataset baru:

```bash
# Opsi 1: Menjalankan via perintah ROS 2 (setelah source install/setup.bash):
ros2 run igor_navigation retrain_ai --timesteps 300000 --eval

# Opsi 2: Menjalankan langsung via Python:
python3 src/igor_navigation/retrain_ai.py --timesteps 300000 --eval

# Atau uji cepat (smoke test) 10.000 timesteps:
ros2 run igor_navigation retrain_ai --timesteps 10000
```

### Hasil yang Dihasilkan Otomatis oleh Skrip:
1. **Memperbarui berkas bobot** di `src/igor_navigation/igor_navigation/weights/` (`.zip`, `.onnx`, `.json`, `.h`, `.mem`).
2. **Menyimpan 5 animasi GIF durasi penuh** dan grafik komparatif di `src/igor_navigation/igor_navigation/evaluations/`.
3. **Memicu `colcon build` otomatis** sehingga perubahan bobot langsung aktif pada bringup robot tanpa langkah manual tambahan.


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `eth_direction.md`

SHA256: `343f3f377626daee66bd67304a361442dc866eff07ff877cfe6ca8dfbf752f7b`

<!-- BEGIN ORIGINAL DOCUMENT -->

# Ethernet direction: Jetson Orin Nano ? DE10-Nano

## Result and implemented architecture

The original Ethernet implementation was **not synchronized and was not a
working hardware path**. The fixes below provide a deployable HPS UDP gateway
that uses the existing verified Parallel8 fabric UART. The connection **between
the two boards is Ethernet**; a **USB-to-3.3 V UART adapter local to the DE10**
connects its HPS Linux USB host to its FPGA JP1 header.

```text
Jetson Orin Nano (Linux, UDP client)
  RJ45 192.168.50.1/24
           ? Ethernet cable or common switch; UDP 8080
  RJ45 192.168.50.2/24
DE10-Nano HPS (ARM Linux, de10_udp_gateway.py)
           ? HPS USB host ? local USB-UART adapter (9600 or 921600)
DE10-Nano FPGA JP1 UART ? Parallel8 74?128?64?3 core
```

This is **not** an implementation of the initially proposed native
HPS-to-FPGA DDR/DMA bridge. That native design does not exist in the supplied
Quartus projects. The adapter is an explicit additional hardware requirement;
without it, the implemented hardware gateway cannot reach the UART-only image.
A network-only test is available without an adapter, but never reports FPGA
success. Physical Ethernet and inference acceptance must be performed on the
boards using the steps below; they were not available from this workstation.

## One-command connection from Jetson

For a standalone download, copy `tools/de10_connect.py` onto Jetson and run
`python3 de10_connect.py`. It includes its required gateway/client assets.
With the updated repository and prepared HPS Linux/SSH, you can also run:

```bash
python3 tools/connect_de10.py
```

The script configures temporary IPs, uses the DE10 USB console if HPS is not
reachable, authenticates normally, deploys the gateway over SSH and runs a
network-only UDP test. Keep its terminal open; Ctrl+C ends its gateway session.
It verifies HPS ARMv7/SoCFPGA identity before remote configuration. Use
`--user ACTUAL_HPS_ACCOUNT --console /dev/ttyUSBx` when defaults do not match.
`--hardware --baud 9600 --fpga-serial HPS_LOCAL_ADAPTER` enables real inference.
The script cannot replace a missing Linux SD image or repair NO-CARRIER wiring.
See [full automation instructions](docs/connect_de10.md).

## 1. Initial audit and fixes

| Problem found | Consequence | Implemented fix |
|---|---|---|
| C packed response is 50 bytes; original Python checked/sliced 48 bytes, earlier UART test assumed 52 | Unpack/CRC failures | Shared little-endian codec, exact 492/50-byte lengths and C compile-time size/offset assertions |
| Python ignored status, sequence/timestamp, sender, dimensions or response CRC in some paths | Stale/error datagrams could look like actions | Connected UDP socket filters peer; CRC, dimension, status, frame ID, timestamp, total deadline and float/Q consistency checks |
| UDP/serial failures silently returned zero actions or enabled mock | Transport failure could look like valid inference | Explicit exceptions and fault latching; controller commands full motor stop on transport failure |
| Packaged host bridge supported UART only while original source advertised UDP | Deployment selected incompatible code | Same UART+UDP bridge and Ethernet codec in source and packaged integration trees |
| Daemon assumed `ai_accel_wrapper` at LW bridge offset 0 and DDR at 0x20000000 | Current FPGA has neither register interface nor DDR master; Linux memory is not reserved/coherent | Production path replaced by UART gateway; old HAL now heap-only mock and refuses hardware access |
| C daemon validated packet contents without requiring exact received datagram length | Truncated/oversized packets could be mishandled | Gateway receives whole UDP datagram and rejects any size other than 492 |
| Old mock produced a reactive heuristic and fabricated execution cycles | Network test could be mistaken for real model inference | Network-only backend returns status 6, rejected by production clients; cycle count is 0/unknown because fabric UART does not transmit it |
| Benchmark counted any received datagram and truncated 0.8 to raw 204 | Invalid replies counted as success; mismatched golden input | Validated benchmark/test uses raw Q8.8=205 and compares against model fixtures |
| No Linux/IP/service/wiring deployment directions | A SOF alone could not start Ethernet communication | Explicit two-board setup, staged diagnostics, service template and test steps below |
| Prebuilt daemon/object files were checked in | Wrong architecture/stale code could be deployed | Removed generated binaries; optional compatibility launcher must be built on target Linux |

The UDP bridge does not automatically retry. Gateway recent duplicate/out-of-order
requests from the same endpoint (up to 128 tracked peers) do not rerun the unsequenced UART accelerator.
UART errors latch the backend; client errors latch that client instance. Reset
FPGA and restart both gateway and client after a transport fault. A valid zero
residual is distinct from an error and does not by itself mean motor STOP.

## 2. Does Quartus programming alone enable Ethernet?

**No.** The DE10-Nano RJ45 PHY is connected to the **HPS Ethernet MAC**.
Quartus loads FPGA configuration SRAM; it does not install/boot HPS Linux,
configure IP addresses, launch a UDP server or create an absent Avalon/DMA IP.
Terasic documents the HPS Ethernet wiring in the DE10-Nano user manual,
section 3.7.2. Board-revision resources and BSPs are available from the
[official Terasic downloads](https://download.terasic.com/downloads/cd-rom/de10-nano/).
Intel describes the separate HPS/FPGA interfaces in its
[HPS memory-mapped interface documentation](https://www.intel.com/content/www/us/en/docs/programmable/683126/21-2/hps-fpga-memory-mapped-interfaces.html).

For the implemented gateway:

1. Boot compatible ARM Linux on DE10 HPS from a board-revision-appropriate SD
   image/BSP. Its bootloader must initialize HPS clocks, DDR, Ethernet and USB.
   No SD image or bootloader was changed by this patch. Old Python-2-only images
   need a Python 3-capable userspace before this gateway can run.
2. Wait until HPS boot completes. A boot script may load its own FPGA RBF.
3. Load the desired UART SOF using Quartus, then verify HPS Ethernet/USB still
   operate and that Linux did not subsequently overwrite the FPGA image.
4. Connect the local adapter, configure both IPs, and start the gateway.

The most recently programmed image in the preceding UART work was the **9600**
variant. This Ethernet change does not reprogram FPGA or change its clock/model.

| Fabric image | Serial baud on DE10 adapter | Host timeout example |
|---|---|---|
| `fpga/experiments/parallel8_9600/output_files/igor_src_policy_9600.sof` | 9600 | UDP test 1.0 s; gateway 0.5 s |
| `fpga/bitstreams/igor_src_policy_parallel8.sof` | 921600 | Start with same conservative timeouts; tune only after measurement |

For 9600 reprogramming, run `python tools/program_uart9600.py --program` on the
Windows programming machine, or use the variant QPF/SOF in Quartus Programmer.
For original Parallel8 open `fpga/bitstreams/igor_src_policy_parallel8.cdf`
in Quartus Programmer and select the accepted SOF after Auto Detect. Its SHA256
is `cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49`.
The old all-release launcher can refuse after software changes because its
frozen manifest includes software; do not silently regenerate acceptance evidence
to bypass that refusal. Always inspect the detected chain and select the FPGA,
keeping HPS in bypass; do not assume the HPS is device 2.

### If a local UART adapter is unacceptable

A separate **native HPS/fabric hardware project** is required. Start from the
Terasic HPS reference system matching the actual board revision, add the
Parallel8 core behind a documented Avalon-MM register/on-chip RAM interface
(or implement a real DMA master), connect/clock/reset the HPS bridges in
Platform Designer, generate handoff files, and build matching bootloader/device
tree/FPGA image. Reserve DMA memory or use a coherent kernel DMA driver; do not
map arbitrary Linux RAM through `/dev/mem`. Add completion acknowledgement,
sequence/error registers, a fresh-result lease, and reset/timeout tests. Then
implement and test that register ABI as another gateway backend. None of those
components can be inferred from the old `REG_IN_PTR` constants. That native
backend is **not supplied or claimed as working by this patch**.

## 3. Wire and prepare the DE10 HPS Linux

Requirements: booted HPS Linux, Python 3.8+ and pyserial, an HPS USB host port
with suitable host/OTG cable, and a USB-UART adapter with **3.3 V TTL signals**.
USB-Blaster and the board's HPS console connector are not this local fabric link.

| Local adapter signal | FPGA connection |
|---|---|
| TX | JP1 pin 1, FPGA UART_RX / V12 |
| RX | JP1 pin 2, FPGA UART_TX / E8 |
| GND | JP1 pin 12 or 30 |

Do not connect adapter VCC. Disconnect the earlier Jetson UART TX/RX wires:
the Jetson now sends through RJ45, and the DE10-local adapter drives fabric RX.

On DE10, verify the OS and identify actual device/interface names:

```bash
uname -m
python3 --version
ip -br link
ls -l /dev/serial/by-id/
python3 -c 'import serial; print(serial.__version__)'
```

DE10 HPS is ARMv7, not Jetson AArch64. Do not copy a Jetson/PC executable as an
HPS daemon. On Debian/Ubuntu-based images, install dependencies if missing:

```bash
sudo apt-get update
sudo apt-get install python3 python3-serial iproute2 iputils-ping
```

For other HPS distributions use their package manager; `apt` is not universal.
If needed on a Python-3-capable system with pip, use
`python3 -m pip install --user pyserial`. Give the HPS account access to the
adapter's actual device group; on Debian this is commonly `dialout`:

```bash
ls -l /dev/ttyUSB0
# Only if the device group is dialout:
sudo usermod -aG dialout "$USER"
# Log out and back in before starting the gateway.
```

Use `/dev/serial/by-id/...` when available, not an assumed `/dev/ttyUSB0`.
Only one process may own this adapter. The gateway requests exclusive access.

## 4. Install matching software on both machines

Use this updated full repository at `~/igor_ws` on both boards. Alternatively,
build `tools/igor_ethernet_update.zip` with `python tools/package_ethernet.py`,
copy the ZIP onto **both** boards, then apply it to existing matching workspaces:

```bash
python3 -m zipfile -e ~/igor_ethernet_update.zip ~/igor_ws
cd ~/igor_ws
```

The ZIP contains relative `src/` paths, the packaged bridge counterpart, fixtures,
service example and this document. It is an update, not a bootable SD image or a
complete ROS distribution. It contains no host-architecture binaries. Always
run the Python gateway directly, or rebuild the compatibility C launcher:

```bash
# Optional; Linux target compiler/build tools required.
make -B -C src/igor_pipeline/hps_de10
src/igor_pipeline/hps_de10/de10_server_daemon --help
```

The old `--hw` and `--mock` flags are replaced by explicit `--backend uart` or
`--backend mock`. The launcher executes the adjacent Python gateway; keep both
files in the project directory. No production path accesses `/dev/mem`.

## 5. Configure the Ethernet link

Connect Jetson RJ45 and DE10 RJ45 directly, or to the same isolated switch.
The examples use a private subnet that must not conflict with an existing LAN.
Find interface names with `ip -br link`; replace the example `eth0` if needed.
These commands add a link address without flushing other addresses/default routes.

Jetson:

```bash
JETSON_IF=eth0   # replace with the actual wired interface
sudo ip link set dev "$JETSON_IF" up
sudo ip address replace 192.168.50.1/24 dev "$JETSON_IF"
ip route get 192.168.50.2
ping -c 3 192.168.50.2
```

DE10 HPS:

```bash
DE10_IF=eth0     # replace with the actual wired interface
sudo ip link set dev "$DE10_IF" up
sudo ip address replace 192.168.50.2/24 dev "$DE10_IF"
ip route get 192.168.50.1
ping -c 3 192.168.50.1
```

The first ping only works after the other side is configured. No gateway,
DNS server or DHCP server is needed for this direct link. These `ip` settings
are temporary. If NetworkManager manages the interface, a persistent profile
can instead be created **once** on each board (do not add duplicate profiles):

```bash
# Jetson
sudo nmcli connection add type ethernet ifname "$JETSON_IF" con-name igor-eth ipv4.method manual ipv4.addresses 192.168.50.1/24 ipv4.never-default yes
sudo nmcli connection up igor-eth
# DE10, only if NetworkManager is installed/managing this interface
sudo nmcli connection add type ethernet ifname "$DE10_IF" con-name igor-eth ipv4.method manual ipv4.addresses 192.168.50.2/24 ipv4.never-default yes
sudo nmcli connection up igor-eth
```

For existing `igor-eth` profiles use `nmcli connection modify` instead of add.
For a different network manager persist the same address/netmask in its native
configuration. Do not run multiple network managers on the interface. Keep
Internet/default-route configuration on the existing uplink.

If a firewall is active, allow UDP 8080 from the Jetson link address to DE10.
For UFW on DE10, an example scoped rule is:

```bash
sudo ufw allow in on "$DE10_IF" from 192.168.50.1 to 192.168.50.2 port 8080 proto udp
```

## 6. Test in stages

### A. Network only ? no FPGA success claim

DE10 terminal:

```bash
cd ~/igor_ws
python3 src/igor_pipeline/hps_de10/de10_udp_gateway.py --bind 192.168.50.2 --backend mock --allow-client 192.168.50.1
```

Jetson terminal:

```bash
cd ~/igor_ws
python3 src/igor_pipeline/scripts/ethernet_test.py --host 192.168.50.2 --network-only --iter 10
```

Expected: `NETWORK_ONLY PASS`, `Passed=10`, and `mode=NETWORK TEST ONLY`.
This proves UDP request/response framing, CRC and echoed identity across the
link. It does **not** execute the FPGA. The production bridge must reject this
server's status 6; the same client command without `--network-only` must fail.
Stop the mock gateway with Ctrl-C before starting hardware mode on port 8080.

### B. Verify local fabric UART on DE10

Program the correct image, release KEY1, press/release KEY0, then run on DE10
before starting the gateway (replace adapter path):

```bash
python3 src/igor_pipeline/scripts/uart_test.py --port /dev/serial/by-id/REPLACE_WITH_ADAPTER --baud 9600 --iter 3
```

Expected raw Q8.8 `[-46, 60, 34]`, 3/3 validated, CRC8 response
`5a a5 02 06 d2 ff 3c 00 22 00 61`. A UART failure here must be resolved before
Ethernet can deliver real FPGA inference; see the existing UART diagnostics.

### C. Full Jetson Ethernet ? HPS ? actual FPGA

DE10 terminal:

```bash
python3 src/igor_pipeline/hps_de10/de10_udp_gateway.py --bind 192.168.50.2 --port 8080 --backend uart --serial /dev/serial/by-id/REPLACE_WITH_ADAPTER --baud 9600 --timeout 0.5 --allow-client 192.168.50.1 --log hps_eth_run1.jsonl
```

Jetson terminal:

```bash
python3 src/igor_pipeline/scripts/ethernet_test.py --host 192.168.50.2 --iter 50 --timeout 1 --output jetson_eth_fixed1.jsonl
python3 src/igor_pipeline/scripts/ethernet_test.py --host 192.168.50.2 --all-cases --iter 48 --timeout 1 --output jetson_eth_matrix1.jsonl
python3 src/igor_pipeline/scripts/ethernet_test.py --check-log jetson_eth_matrix1.jsonl
```

Expected: first test 50/50 `FPGA PASS`, raw Q8.8 `[-46,60,34]` for its fixed
input; matrix test 48/48 across 16 fixtures; log check 48 verified responses.
Only a status-0, CRC-valid, correctly identified packet with exact expected
integer outputs counts as success. Capture files are never overwritten; use
new filenames on subsequent runs. An incomplete capture fails offline checking.
`benchmark_latency.py 192.168.50.2 8080 --iter 50` is also a validated fixed-input
benchmark, not an unchecked datagram counter.

At 9600 baud, 153+11 UART bytes cost ~170.83 ms plus inference/network/software;
50 transactions take at least ~8.55 seconds. Ethernet being Gigabit does not
remove this local UART bottleneck. At 921600, wire time is ~1.78 ms. Cycle count
in Protocol V2 is 0/unknown on this backend, not an inference-cycle measurement.

### D. Fault recovery checks

While a diagnostic run is active, hold KEY1 or disconnect the local UART RX/TX.
Expected: nonzero backend status/timeout, nonzero client exit, and no claimed
valid action. The next request after a UART fault remains rejected by the
latched gateway. Stop both processes, restore wiring, release KEY1, reset with
KEY0, restart the hardware gateway, and start a **new** client.
A production controller converts a transport exception into four zero motor
setpoints; this is covered by software tests, not a physical motor test here.

## 7. ROS integration and optional service

Both bridge copies now accept `udp://192.168.50.2:8080`. Build/source the intended
ROS workspace after applying the update, then supply explicit transport settings:

```bash
colcon build --packages-select igor_controller
source install/setup.bash
ros2 run igor_controller controller_node --ros-args -p use_fpga:=true -p use_mock_serial:=false -p fpga_port:=udp://192.168.50.2:8080 -p fpga_timeout:=0.3
```

`fpga_baudrate` only affects a directly connected Jetson serial port; with UDP,
set baud on the **HPS gateway**. The 9600 profile is a communication diagnostic,
not a 50-Hz control path: its ~171 ms minimum exceeds a 20 ms control period and
the source controller's sensor freshness budget. Do not relax freshness guards
to disguise this. Use the verified 921600 image/backend for performance testing,
measure complete latency/jitter and recheck robot watchdogs before motion tests.
Ethernet transport correctness is not a completed robot safety acceptance test.

After manual hardware tests pass, optionally install
`src/igor_pipeline/hps_de10/igor-ethernet.service.example` as
`/etc/systemd/system/igor-ethernet.service`. Edit the actual Linux account,
project root, adapter path, bind IP and baud first; the account needs serial
permissions. Then on DE10:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now igor-ethernet.service
systemctl status igor-ethernet.service
journalctl -u igor-ethernet.service -n 50 --no-pager
ss -lunp | grep ':8080'
```

The template does not automatically restart after a fault. FPGA reset and manual
service restart (`sudo systemctl restart igor-ethernet.service`) are recovery
steps. UART backend faults keep the process alive but latched; check the journal
rather than treating `active` as proof of successful inference.

## 8. Wire contract and implemented files

| Packet | Layout | Size / CRC |
|---|---|---|
| Request | LE magic u32, frame u32, timestamp u64, linear 3f32, angular 3f32, dimension u32, observations 74f32, Q8.8 74i16, CRC u32 | 492 bytes; CRC over bytes 0..487 |
| Response | LE magic u32, frame u32, timestamp u64, status u32, outputs u32, actions 3f32, Q8.8 3i16, cycles u32, CRC u32 | 50 bytes; cycles offset 42, CRC offset 46, no padding |

CRC32 is IEEE/zlib. Frame/timestamp echo identifies a response without requiring
clock synchronization between boards. Raw integer inputs are authoritative;
redundant floats must be finite, in-domain and quantize to the same integers.
Responses must satisfy float = integer/256 exactly. Status 0 is verified
hardware inference; status 4 is UART failure/deadline, 6 is network-only mock,
7 is a latched/unexpected backend fault. All nonzero statuses are errors for
production clients. These mechanisms provide integrity/correlation, not network
authentication; configuration above scopes traffic to the dedicated link.

Implemented files:

- `src/igor_controller/igor_controller/ethernet_protocol.py`: shared 492/50 codec and correlated, fail-closed UDP client; mirrored in packaged integration.
- `src/igor_controller/igor_controller/fpga_bridge.py`: UART+UDP integration; identical packaged counterpart.
- Both `controller_node.py` files: configurable FPGA timeout; source controller also stops all motors on transport failure.
- `src/igor_pipeline/hps_de10/de10_udp_gateway.py`: explicit real UART or network-test backend, strict validation, duplicate suppression and backend fault latch.
- `src/igor_pipeline/protocol/protocol_v2.h`: exact C wire-size/offset checks and status definitions.
- HPS `de10_server_daemon.c`/`Makefile`: Linux compatibility launcher; old unsafe production HAL removed, mock-only API retained.
- `src/igor_pipeline/scripts/ethernet_test.py`: model fixtures, multi-pattern validation, logs and offline revalidation.
- `benchmark_latency.py`: delegates to validated transport test.
- HPS service example and `tools/package_ethernet.py`: deployment support.
- `test/test_ethernet.py`: C/Python interoperability, localhost UDP?gateway?fixture UART, errors, deadlines, stale/duplicate packets, mock rejection and controller stop tests.

## 9. Verification evidence and remaining physical acceptance

Workstation verification uses **real localhost UDP sockets with a simulated
serial fixture**, plus compiled native C interoperability/HAL tests. It does not
emulate the USB electrical path or prove the physical Ethernet link.
Reproduce:

```bash
python -m unittest discover -s test -p test_ethernet.py
python -m unittest discover -s test -p 'test_uart*.py'
python fpga/verification/run_host_regression.py
```

Latest verification: **16 Ethernet tests + 14 UART tests + 29 host/controller
tests + 18 connection automation tests = 77 passing tests**. A separate real-process localhost CLI smoke test
also passes network-only mode and confirms production rejection of mock.
Results and source hashes are recorded in `docs/ethernet_validation/results.json`;
the same directory contains logs. Run `python tools/verify_ethernet.py` to
regenerate this evidence.
No FPGA RTL or SOF was changed by this patch. The hardware checklist remains:
HPS Linux boots; RJ45 ping passes; network-only test passes; local DE10 fabric
UART passes; 50 fixed and 48 matrix Ethernet inference transactions pass; fault
injection fails closed. Native HPS DDR/DMA and a physical robot motion test are
not implemented/verified claims. The Linux C launcher must still be compiled on
ARM Linux; this workstation tests the portable C wire ABI and mock-only HAL,
not an ARM executable or a complete SD-card boot flow.


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `final_docs.md`

SHA256: `46aeab96c86d1a6082dbb9570945d91d7f6585df3d253b3ac9cb18e6fa4127e8`

<!-- BEGIN ORIGINAL DOCUMENT -->

# Project IGOR — final operating and test guide

**Recorded hardware session: 18 October 2026**  
Workspace: `/home/toyotateamaitb/igor_ws`  
Devices: NVIDIA Jetson Orin Nano, Terasic DE10-Nano, Hiwonder JetAuto STM32 chassis, RPLiDAR.

This guide describes the code and hardware tested in this session. Use it for the current setup; older instructions in `pipeline_docs.md`, `test.md`, and older README sections contain superseded protocols, addresses, or daemon flags.

## 1. What works, and what remains unverified

| Item | Result |
|---|---|
| Jetson ↔ DE10 HPS Ethernet | Working: 1 Gbit/s full duplex; ping and SSH verified |
| Physical Ethernet UDP request/reply | 10/10 network-only transactions passed; mean RTT 1.639 ms |
| Jetson header UART | Exact 512-byte loopback passed at 115200 and 921600 baud |
| Actual FPGA inference over direct Jetson UART | **98/98 passed**, including 16 different model fixtures; mean RTT 4.594 ms, maximum 5.920 ms |
| STM32 communication and IMU | 550 CRC-valid IMU frames in five seconds; zero CRC errors |
| Physical LiDAR | Health OK; real 1080-sample scans received; approximately 74 ms between scans in the captured sample |
| Individual wheels | User observed each wheel move in the expected order and stop |
| Expanded wheel combinations | **All 11 groups moved and stopped correctly**, confirmed by the user |
| Live sensors → FPGA → controller with zero velocity requested | Healthy diagnostics received; all output velocity commands remained zero |
| ROS packages | `waypoint_action`, `igor_navigation`, `igor_controller`, and `igor_bringup` built successfully |
| 5 m × 4 m route implementation | Measured-pose and command-estimated versions implemented and software-tested |
| Completed rectangle on the floor | **Not demonstrated.** The motion-requested preflight detected a nearby return at 0.284 m and prevented the route from starting |
| AI inference specifically through Ethernet | **Not demonstrated.** The verified inference connection is direct Jetson GPIO UART |

The session established physical FPGA inference and physical motor operation, and exercised the live pipeline while requesting zero movement. It did not establish a completed moving sensor→FPGA→motor navigation mission. Serial write success is not motor feedback; physical wheel results came from user observation.

## 2. Actual architecture

```text
RPLiDAR ── USB /dev/lidar ───────────────────────┐
                                               v
STM32 ── USB /dev/ttyACM0 ── IMU ──> Jetson controller
                                               |
                           form 74-feature observation
                                               |
                         /dev/ttyTHS1, 921600 baud
                                               v
                                   DE10 FPGA Parallel8
                                               |
                                  3 Q8.8 AI residuals
                                               v
                               Jetson blending / CBF / STOP gates
                                               |
                                   Mecanum inverse kinematics
                                               |
                            STM32 USB, 1,000,000 baud
                                               v
                                      Four wheel motors

Separate working network connection:
Jetson enP8p1s0 192.168.50.1 <── Ethernet ──> DE10 HPS end0 192.168.50.2
```

The FPGA receives **74 processed features**, not complete raw sensor streams:

- 64 normalized frontal LiDAR features.
- Six IMU features.
- Three nominal velocity-command features.
- One normalized heading-error feature.

Jetson retains sensor processing, filtering, safety checks, kinematics, and STM32 motor commands. The FPGA returns three residual actions. A zero residual alone does not mean the motors should stop; the controller must zero the complete motor command on a fault or zero nominal input.

### Wire protocols

| Link | Protocol |
|---|---|
| Jetson GPIO ↔ FPGA | 921600 baud, 8N1, 3.3 V TTL; 153-byte request, 11-byte response; CRC8 Maxim; signed Q8.8 |
| Jetson ↔ STM32 | USB serial, 1,000,000 baud; `AA 55`, motor function `0x03`; four zero-based motor indices and float32 RPS; CRC8 |
| Jetson ↔ HPS UDP | Port 8080; Protocol V2, exactly 492-byte requests and 50-byte replies; CRC32 and correlated frame/timestamp |

UDP status 6 means **network-only mock**, not FPGA inference success. Production clients reject it.

## 3. Wiring and device identification

### Direct FPGA UART — the verified AI path

| Jetson 40-pin header | DE10 FPGA JP1 |
|---|---|
| Pin 8, TX | Pin 1, UART RX |
| Pin 10, RX | Pin 2, UART TX |
| Pin 9, GND | Pin 12, GND |

Use 3.3 V signal levels and a common ground. The FPGA project maps RX to FPGA pin V12 and TX to E8. Verify physical JP1 pin orientation. Remove any pin 8–10 loopback jumper before reconnecting FPGA signals.

### USB devices on this Jetson

| Device | Path/identity observed |
|---|---|
| Jetson header UART | `/dev/ttyTHS1`, controller `serial@3100000` |
| STM32 | `/dev/ttyACM0`, USB `1a86:55d4`, serial `5917012181` |
| Stable STM32 path | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5917012181-if00` |
| LiDAR | `/dev/lidar` → `/dev/ttyCH341USB0`, USB `1a86:7523` |
| DE10 HPS USB console, when connected | FT232R `0403:6001`; observed `/dev/ttyUSB0` with stable ID `usb-FTDI_FT232R_USB_UART_B402QWPK-if00-port0` |
| DE10 programming/JTAG | `09fb:6010 Altera DE-SoC`; does not provide an HPS Linux serial login |

The HPS console was later unplugged; it need not appear during normal direct-UART inference. Device paths can change after reconnecting hardware.

```bash
cd /home/toyotateamaitb/igor_ws
lsusb
ls -l /dev/ttyTHS1 /dev/ttyACM0 /dev/lidar
ls -l /dev/serial/by-id/
python3 -c "from serial.tools import list_ports; print([(p.device,p.description,p.hwid) for p in list_ports.comports()])"
```

The LiDAR's custom `ttyCH341USB0` node may not appear in pyserial's standard port enumeration. Inspect its actual device node and symlink too. Only one process should own each serial connection.

## 4. Fixes that made communication and wheel movement succeed

| Problem found | Correction and resulting behavior |
|---|---|
| Wrong Ethernet interface assumed in old examples | Identified Jetson `enP8p1s0` and HPS `end0`; used their actual names |
| HPS configured for DHCP on a direct cable without a DHCP server | Added HPS `192.168.50.2/24`; Jetson uses `192.168.50.1/24`. Ping, SSH and UDP then worked |
| Wired addressing was not prepared for restart | Saved static addressing on HPS and enabled Jetson wired-profile autoconnect/never-default. Configuration was validated, but a reboot test was not performed |
| JTAG cable mistaken for the Linux console | Connected the separate DE10 USB-UART console; logged into HPS and inspected/configured it |
| UART wiring was initially wrong | Corrected crossed TX/RX and common ground; isolated Jetson loopback established that its UART/header worked |
| Board had previously used the 9600 image | User loaded the Parallel8 921600 image and host tests used matching baud |
| FPGA received no successful requests while LED1, LED3 and LED4 were on | Decoded this as reset released plus E-stop active/latched, fault code 1. Releasing KEY1 and resetting only KEY0 cleared it; valid replies then appeared |
| Active controller default baud still 9600 | Changed it to 921600 and exposed `fpga_baudrate`/`fpga_timeout` in launch |
| Launch endpoint used the old subnet | Updated Ethernet default to `udp://192.168.50.2:8080`; direct UART operation still requires explicit `fpga_port:=/dev/ttyTHS1` |
| Physical LiDAR path could fall back to synthetic scans | Hardware bringup now uses the installed SLAMTEC `rplidar_ros` driver; synthetic publishing is selected only by explicit mock mode |
| Actual driver reports approximately 359° coverage | Corrected overly strict full-scan validation while retaining range/timestamp checks; regression-tested against captured metadata |
| Scan resampling assumed a fixed angle origin | Controller now retains actual scan angle metadata |
| Missing/stale sensors could become a clear-space observation | Active controller now sends complete STOP instead |
| Missing physical STM32 could silently become mock | Physical initialization now fails instead; short serial writes are failures |
| Clock changes could affect freshness timing | Controller and MCU receive leases now use monotonic time |
| Residual output could retain movement despite zero nominal input | Zero nominal input forces zero output; post-compute freshness/output checks precede motor transmission |
| Recovery automatically reversed without a verified rear path | Recovery now holds zero wheel speeds |
| Shutdown did not reliably call driver cleanup | Controller destroys the node and closes hardware with STOP; route supervisor also sends independent final STOP packets |
| ROS planner interface not declared as a dependency | Added `waypoint_action` to `igor_controller` |
| Standalone connection bundle differed from source assets | Regenerated `tools/de10_connect.py`; connection regressions pass |
| Network helper assumed `eth0`/old subnet and hid errors | Updated interface selection/address defaults and error reporting |

### The decisive FPGA reset procedure

1. Program the correct Parallel8 image.
2. Leave **KEY1 fully released**.
3. Press and release **only KEY0**.
4. Before sending requests, expect **LED1 on; LED3–LED7 off**.

For this RTL:

| LEDs | Meaning |
|---|---|
| LED7–LED4 | Four-bit error code |
| LED3 | E-stop active or latched |
| LED2 | Response-valid indication |
| LED1 | Reset released |
| LED0 | Valid/fresh residual permit; not a direct chassis motor-power permit |

LED1+LED3+LED4 means E-stop fault 1. KEY1 latches the stop; simply releasing it does not clear the latch. Reset with KEY0 while KEY1 remains released. During FPGA-controller operation, an inference fault causes the host to stop; KEY1 is not a physical chassis power disconnect.

### Bitstream warning specific to this checkout

The checked-out `fpga/bitstreams/igor_src_policy_parallel8.sof` is a **132-byte Git LFS pointer**, not the programmable object. Obtain the real LFS object on the Quartus machine before programming:

- Real object size: **6,690,394 bytes**.
- Expected SHA256: `cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49`.

Quartus and git-lfs were not installed on this Jetson. Programming was performed by the user. Inspect the detected JTAG chain in Quartus; do not assume fixed HPS/FPGA chain indices. A KEY0 reset does not load a different image. After a power cycle or HPS boot flow that reloads fabric, confirm the intended image again.

## 5. Build and prepare each terminal

Known working environment: Jetson AArch64, Ubuntu/ROS 2 Humble, Python 3.10, NumPy, pyserial, colcon, and installed `rplidar_ros`.

For a normal workspace build:

```bash
cd /home/toyotateamaitb/igor_ws
source /opt/ros/humble/setup.bash
colcon build --base-paths src waypoint_list --packages-up-to igor_bringup igor_controller
source install/setup.bash
ros2 launch igor_bringup bringup.launch.py --show-args
```

In each subsequent ROS terminal:

```bash
cd /home/toyotateamaitb/igor_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
```

This session instead built under `/tmp/igor-uart-build`, `/tmp/igor-uart-install`, and `/tmp/igor-uart-build-logs`. To use that existing session build, substitute:

```bash
source /opt/ros/humble/setup.bash
source /tmp/igor-uart-install/setup.bash
```

The `/tmp` build may disappear after reboot. Source one intended overlay so stale installed code does not shadow the current source. The session user already had `dialout` access; another account may need device-group permissions.

## 6. Test FPGA inference without moving the wheels

Stop other FPGA serial clients first. With correct wiring, Parallel8 loaded, and the E-stop latch cleared:

```bash
python3 src/igor_pipeline/scripts/uart_test.py --self-check --baud 921600
python3 src/igor_pipeline/scripts/uart_test.py \
  --port /dev/ttyTHS1 --baud 921600 --iter 50 --timeout 1
```

Expected fixed-input result:

```text
Q8.8 = [-46, 60, 34]
Float residuals = [-0.1796875, 0.234375, 0.1328125]
Reply = 5a a5 02 06 d2 ff 3c 00 22 00 61
Validation passed: 50/50
```

For a preserved capture, use a new filename:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
python3 src/igor_pipeline/scripts/uart_test.py \
  --port /dev/ttyTHS1 --baud 921600 --iter 50 --timeout 1 \
  --jsonl "docs/ethernet_validation/fpga_uart_${RUN_TAG}.jsonl"
```

### Isolate Jetson UART if no bytes return

Disconnect **both FPGA signal wires** first, then jumper **Jetson pin 8 to pin 10**:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
python3 tools/uart_diagnose.py --port /dev/ttyTHS1 --mode loopback \
  --seconds 1 --output "docs/ethernet_validation/loopback_${RUN_TAG}.json"
```

Expected: exact 512-byte PASS at both 115200 and 921600. Remove the jumper and restore the crossed FPGA wiring before running inference again. Never join the lines while both boards' TX outputs remain connected.

## 7. Test individual wheels, pairs, and all four

The wheel-test tool sends motor packets directly to STM32; it does not call the FPGA. These commands send nonzero motor speeds. Secure the robot with all four wheels lifted and clear. Close other STM32 owners, including the main controller. The script validates the observed STM32 USB identity before sending commands.

First inspect the plan without opening serial:

```bash
python3 tools/test_jetauto_wheels.py --groups singles pairs four \
  --output /tmp/igor_wheel_dry_run.json
```

Run all groups:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
python3 tools/test_jetauto_wheels.py --groups singles pairs four \
  --run --wheels-raised --rps 0.5 --seconds 0.75 \
  --output "docs/ethernet_validation/wheel_groups_${RUN_TAG}.json"
```

For only individual wheels, use `--groups singles`; for only all pairs, use `--groups pairs`; for all four together, use `--groups four`.

| Order | Wheels selected |
|---|---|
| 1–4 | M1 front-left; M2 rear-left; M3 front-right; M4 rear-right |
| 5 | M1 + M2 |
| 6 | M1 + M3 |
| 7 | M1 + M4 |
| 8 | M2 + M3 |
| 9 | M2 + M4 |
| 10 | M3 + M4 |
| 11 | M1 + M2 + M3 + M4 |

At the tested 0.5 RPS, active left motors receive +0.5 and active right motors −0.5 because of the mirrored mounting. Each group is followed by repeated STOP packets and a pause. Ctrl+C triggers cleanup and STOP. The completed 11-group session was physically confirmed by the user; future runs still need observation of actual movement and stopping.

## 8. Test LiDAR and the complete pipeline while stationary

Place the robot in its normal driving orientation with a horizontal scan plane. In this session, an incorrect upright/vertical placement made LiDAR see the floor as a nearby wall. Also clear people, supports, cables, and nearby objects from the scan plane.

Inspect close returns without opening the chassis controller:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
ROS_LOG_DIR=/tmp/igor-lidar-check python3 tools/inspect_lidar_clearance.py \
  --output "docs/ethernet_validation/lidar_clearance_${RUN_TAG}.json"
```

This starts and stops the installed LiDAR driver. It reports distances and angles; it does not send wheel commands. Angles are relative to the configured LiDAR axis, which must be aligned/verified against the chassis before interpreting them as robot directions.

Run the complete **zero-command preflight**, without `--run`:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
ROS_LOG_DIR=/tmp/igor-preflight python3 tools/run_timed_rectangle.py \
  --output-dir "docs/ethernet_validation/preflight_${RUN_TAG}"
```

The supervisor starts real LiDAR, the FPGA-enabled controller, and STM32. It publishes zero velocity for about ten seconds, checks diagnostics and clearance, shuts down the children, and independently sends final STOP packets. No other hardware controller/serial client should be running.

A passing preflight requires real scans, multiple healthy calibrated hardware diagnostics, zero safe velocities, live hardware processes, and minimum recent clearance **greater than 0.45 m**. Startup sensor faults can occur before the first scan; persistent faults need investigation.

Read the new output directory:

- `result.json`: preflight result, fault counts, zero-command check, final STOP result.
- `lidar.log` and `controller.log`: hardware/node logs.

### Sensor-age configuration

The bringup default receive-freshness lease remains **25 ms**. Captured scan intervals were about **74 ms**, so the supervised low-speed rectangle/preflight tool explicitly uses a **150 ms** receive-freshness lease. Scan message timestamps are validated separately; this is not a hard 150 ms acquisition-to-actuation guarantee. IMU updates were much faster. The 150 ms value is a test configuration based on observed scan timing, not a general robot stopping-distance certification. It retains stale-data STOP checks. The helper does not bypass collision boundaries or fabricate scans.

## 9. Operate the FPGA-enabled controller manually

Use this instead of the supervisor when an interactive hardware bringup is needed:

```bash
ros2 launch igor_bringup bringup.launch.py \
  algorithm:=cl_drl_cbf use_fpga:=true \
  fpga_port:=/dev/ttyTHS1 fpga_baudrate:=921600 fpga_timeout:=0.02 \
  sensor_freshness_timeout_ms:=150.0 \
  mcu_port:=/dev/ttyACM0 lidar_port:=/dev/lidar \
  use_mock_serial:=false launch_planner:=false
```

The command opens the chassis driver. Keep the robot restrained/clear for initial checks, and use a clear supervised area for any movement. Without a fresh nonzero command, output must remain zero.

In another prepared ROS terminal:

```bash
ros2 topic echo /igor/diagnostics
ros2 topic echo /igor/cmd_vel_safe
ros2 topic echo /igor/safety_gate_alert
ros2 topic hz /scan
```

Successful diagnostics include `fpga: true`, `mock: false`, and `safety_permit: true`. Fault diagnostics include a reason and zero wheel setpoints. These fields are software state, not independent motor acknowledgments.

The controller accepts both `/cmd_vel_in` and `/cmd_vel`. Use only one active movement-command source. Do not start a route and teleop simultaneously.

## 10. Run the requested 5 m × 4 m route

This is a rectangle, with the **first side 5 m** and each corner turning left:

```text
Start (0,0), heading 0°
    → 5 m → (5,0)
    left 90°
    → 4 m → (5,4)
    left 90°
    → 5 m → (0,4)
    left 90°
    → 4 m → (0,0)
    left 90° → initial heading
```

### A. Implemented no-localization version

The user explicitly requested operation without localization. `timed_rectangle` estimates travel by integrating the controller's **executed velocity commands**; it does not measure wheel travel or position. It does not accumulate distance while the controller reports zero. Slip, motor calibration, steering corrections, and latency can change real distance and final heading.

Defaults: 0.20 m/s straight, +0.30 rad/s at corners, zero intervals of 0.5 seconds between stages. Ideal nominal motion is about 111 seconds plus pauses. Actual dimensions are estimates, not guaranteed 5 m × 4 m measurements.

After a successful stationary preflight, put all wheels on the floor, point the robot along the first 5 m side, clear the whole route and stopping space, and supervise with an immediate physical stop available. Stop all existing hardware nodes before using the supervisor, since it starts its own:

```bash
RUN_TAG=$(date +%Y%m%d_%H%M%S)
ROS_LOG_DIR=/tmp/igor-rectangle python3 tools/run_timed_rectangle.py \
  --run --floor-ready \
  --output-dir "docs/ethernet_validation/rectangle_${RUN_TAG}"
```

The tool first repeats the stationary preflight. Only a passing result starts movement. It stops on stale sensors/controller output, close obstacles, unexpected reverse/lateral/right-turn commands, scheduling gaps, segment deadlines, total deadline, hardware-node exit, or interruption.

Logs also contain `route.log` and `route.jsonl` once the route starts. `done: true` means the command-estimated stages completed; it is not a measured-position acceptance result.

**Latest physical attempt:** preflight rejected 0.284 m clearance. All safe commands stayed zero; final STOP was sent. Follow-up returns were about 0.294 m at +80° and 0.408 m at −121°. No completed floor rectangle was recorded. The subsequent request to bypass the boundary around people was not implemented; obstacle stopping remains enabled.

### B. Measured-pose version for later localization

`rectangle_route` requires a fresh measured `geometry_msgs/PoseStamped` topic. Its path is relative to the starting pose, with four left quarter-turns and return to the starting heading. It checks pose freshness/frame changes, path deviation, scan clearance, controller diagnostics, and timeouts.

The existing `waypoint_server/motion_node.py` integrates commands for visualization; it is not a measured localization source. No suitable physical localization source was available in this session.

With a real measured `/pose` source and the hardware controller running separately:

```bash
# Starts disarmed; does not command motion.
ros2 launch igor_bringup rectangle_route.launch.py

# Future measured-localization run, only after validating that source:
ros2 launch igor_bringup rectangle_route.launch.py \
  armed:=true measured_pose_confirmed:=true pose_topic:=/pose
```

Do not run the measured and timed route publishers together. Configuration is in `src/igor_bringup/config/rectangle_5x4_left.yaml`.

## 11. Stop and recover

- Use **Ctrl+C in the route supervisor terminal**. Cleanup stops its command publisher, publishes zeros, closes the controller, and sends independent final STOP packets.
- Stop other teleop/route publishers too. A one-off zero message can be overwritten by another active movement publisher.
- With all movement publishers stopped and the controller still running, an explicit zero is:

```bash
ros2 topic pub --once /cmd_vel_in geometry_msgs/msg/Twist '{}'
```

- For an FPGA E-stop/fault: stop the host process, release KEY1, reset only KEY0, and create a new client/controller instance. Transport errors can latch the client; do not reuse a failed instance and assume it recovered.
- Check the report for `final_stop_sent: true` or `final_stop_error`. Serial STOP cannot protect against every Jetson crash, USB/power loss, stuck controller, or hardware fault. Provide an accessible physical chassis stop for floor tests.

## 12. Ethernet setup and its separate AI limitation

Current addresses:

| Board | Interface | Address |
|---|---|---|
| Jetson | `enP8p1s0` | `192.168.50.1/24` |
| DE10 HPS Linux | `end0` | `192.168.50.2/24` |

```bash
ip -br addr show enP8p1s0
ip route get 192.168.50.2
ping -I enP8p1s0 -c 3 192.168.50.2
ssh fpga@192.168.50.2
```

Authenticate interactively. Passwords are intentionally not recorded here.

If temporary Jetson addressing is needed, the helper configures an address without flushing unrelated addresses/routes:

```bash
bash src/igor_pipeline/scripts/setup_network_hardware.sh enP8p1s0 192.168.50.1/24
```

On HPS, temporary configuration is:

```bash
sudo ip link set dev end0 up
sudo ip address replace 192.168.50.2/24 dev end0
```

Persisted during the session:

- Jetson NetworkManager profile `enP8p1s0`: manual address, autoconnect=yes, never-default=yes; Wi-Fi retains the default route.
- HPS `/etc/network/interfaces.d/end0`: static address without a gateway.
- Original HPS configuration backed up at `/etc/network/end0.before-igor`.

### Network-only UDP test

On HPS, using the deployed workspace:

```bash
cd /home/fpga/igor_ws
python3 src/igor_pipeline/hps_de10/de10_udp_gateway.py \
  --bind 192.168.50.2 --backend mock --allow-client 192.168.50.1
```

On Jetson:

```bash
python3 src/igor_pipeline/scripts/ethernet_test.py \
  --host 192.168.50.2 --network-only --iter 10
```

Expected: `NETWORK_ONLY PASS`, status 6. The same request without `--network-only` must fail against this backend. Stop this mock gateway when finished; it is not a production AI service.

### What true Ethernet AI still requires

The supplied fabric image exposes UART, not a native HPS memory-mapped accelerator bridge. The existing HPS gateway expects a **separate HPS-local USB-to-3.3 V TTL UART adapter** wired to FPGA JP1. Direct Jetson-to-JP1 wires do not create that HPS connection. Never connect two TX drivers to FPGA RX simultaneously.

The running HPS kernel was `6.12.100-armv7-fpga`; `CONFIG_USB_SERIAL` and `CONFIG_USB_ACM` were disabled, with no matching kernel build resources installed. That gateway approach therefore needs both its adapter connection and a compatible kernel/driver. Pyserial 3.5 was installed in `/home/fpga/igor_ws/.venv`; the generic connection script invokes system Python, so hardware deployment must also select an interpreter with pyserial.

A native HPS/fabric bridge would instead require a matching FPGA/Platform Designer project, ABI, boot handoff, and driver. Neither approach was completed in this session. See [eth_direction.md](eth_direction.md) for details. Do not use old daemon `--hw`/`--mock` or `/dev/mem` DDR instructions as a working native accelerator path.

## 13. Software regression commands

These tests do not move hardware. Localhost UDP tests require socket permissions:

```bash
python3 -m unittest discover -s test -p test_rectangle_route.py
python3 -m unittest discover -s test -p test_ethernet.py
python3 -m unittest discover -s test -p test_connect_de10.py
python3 -m unittest discover -s test -p 'test_uart*.py'
python3 fpga/verification/run_host_regression.py
```

Latest observed suite results:

| Suite | Passing tests |
|---|---:|
| New route/active-source sensor/MCU checks | 13 |
| Ethernet protocol/gateway | 16 |
| Connection automation/standalone bundle | 18 |
| UART fixtures | 14 |
| Packaged host/controller regression | 29 |

The host regression targets `fpga/software_integration/src`; it is distinct from the active workspace controller. New source-guard tests explicitly cover the active controller/MCU changes. Pure path simulation is software evidence, not physical route completion. Packet CRCs are integrity checks, not authentication or proof of safe navigation.

## 14. Files and evidence

| File | Purpose |
|---|---|
| `src/igor_controller/igor_controller/fpga_bridge.py` | Real UART/UDP accelerator client |
| `src/igor_controller/igor_controller/mcu_driver.py` | STM32 motor TX and IMU RX |
| `src/igor_controller/igor_controller/controller_node.py` | Observation, inference, filtering, STOP gates, motor kinematics |
| `src/igor_bringup/launch/bringup.launch.py` | Hardware/mock launch selection and exposed transport settings |
| `tools/test_jetauto_wheels.py` | Singles, six pairs, all-four tests; dry-run default |
| `tools/inspect_lidar_clearance.py` | Physical clearance diagnostics without chassis commands |
| `tools/run_timed_rectangle.py` | Zero-command preflight, optional timed mission, cleanup and final STOP |
| `timed_rectangle_path.py`, `timed_rectangle_node.py` in the controller package | No-localization command-estimated rectangle |
| `rectangle_path.py`, `rectangle_route_node.py` in the controller package | Measured-pose rectangle for a future localization source |
| `test/test_rectangle_route.py` | Route and active-source safety/transport regression |

Physical evidence:

- [98-request FPGA inference capture](docs/ethernet_validation/jetson_fpga_bridge_20261018_acceptance.jsonl)
- [FPGA latency summary](docs/ethernet_validation/jetson_fpga_bridge_20261018_summary.json)
- [Ethernet network-only capture](docs/ethernet_validation/jetson_hps_network_20261018.jsonl)
- [Jetson UART loopback](docs/ethernet_validation/jetson_loopback_20261018_run1.json)
- [STM32/IMU capture summary](docs/ethernet_validation/jetauto_stm32_telemetry_20261018.json)
- [LiDAR capture](docs/ethernet_validation/jetauto_lidar_20261018_run1.json)
- [All 11 wheel groups, user-confirmed](docs/ethernet_validation/jetauto_wheel_groups_20261018_run1.json)
- [Latest motion-requested preflight result](docs/ethernet_validation/jetauto_rectangle_20261018_run1/result.json)
- [Close-return diagnostic](docs/ethernet_validation/jetauto_clearance_20261018_run1.json)

Further detail: [diagnosis history](docs/jetson_de10_diagnosis.md), [rectangle test report](docs/jetauto_rectangle_test.md), and [direct UART runbook](docs/direct_uart_runbook.md). This final guide records later results that supersede intermediate statements in those historical reports.

Documentation validation: all local evidence links resolved, all 22 Bash code blocks passed shell syntax parsing, and the no-hardware protocol self-check and documented tool help options were checked. No motors or hardware route were started while writing this guide.


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `global_planner_architecture.md`

SHA256: `c0645d1447c2e6636b7077546c74cb985e4b78f65f06264b7cbf830b5d57e83d`

<!-- BEGIN ORIGINAL DOCUMENT -->

Suppose that i have weights and bias trained for an ai model and I want to offload the inference to inside fpga de 10 nano while there is a jetson orin nano that functions as a power distribution and signal sending to the microncontroller to the motor where the signal is calculated from the de 10 nano. Jetson orin nano also sends raw data from lidar (64 values), imu, and etc to the fpga as the input for the inference and then send it back to the jetson orin for safety gate.

There is a chance that the AI model will change its dimension, like how many its inputs and outputs, so just make sending packet first (later I will tell on which is which after training), which comes from the jetson orin, and the incoming packet which comes from the fpga. Also, I've given a sample on the packet structure to be sent to the motor in the teleop_mecanum.py. This packet structure will be sent and there is a likely chance that the output of the inference is vx, vy, and omega which will need to be converted into velocity for each wheel. 

Another note, for now, the packed binary struct to the fpga will comply to the structure defined in the `./teleop_mecanum.py` as it is primary goal to just make it work. The safety feature will be handled in the jetson orin. Also, the model has been quantized into Q8.8 so adjust it for the code later. On top of that, the safety gate, which will be implemented in jetson orin, will act like below
1. Safety gate only guards the output from de-10 nano and will calculate the position (got from the imu) for the next 0.1 s with the given inference from fpga, will it go into a boundary zone (like 15 cm radius of it) of the obstacle aligned with the direction it was trying to move based on the inference)? If yes, then the gate will be activated, which results in all input into the fpga will be blocked (to stall the inference), then stop and then go backward for 0.1s with velocity 0.15 m/s and then do inference again toward the former target
2. Safety guard also have the behavior to drop the message from the input from the raw data if the raw data seemed old with timeout like 20-30 ms (it is because the processing of data of fpga took around 16 ms from my current testing)

Other than that, I will also implement ethernet communication protocol between the jetson orin and de-10 nano so the communcation will also need to be programmed (like described in the `./pipeline_architecture.md`). As for the MCU and motor controller integration, it is basically has been implemented in the `teleop_mecanum.py` given, so learn it and make it such that the changing max speed value when runtime will also change the value itself without waiting for any input key for its direction. For its hardware watchdog, implement it but don't activate it for now as I want to prove the system fully running without handling the safety of the jetson for now.


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `global_planner_docs.md`

SHA256: `e7f17044e0af79c8ef9b8da2ef3a79815c4fcb561c83a8eb8ce0b4a7d16e50df`

<!-- BEGIN ORIGINAL DOCUMENT -->

# Project IGOR: Global Planner & Safety Gate Architecture Documentation (`global_planner_docs.md`)

This document provides a comprehensive technical overview of the implementation completed for **Phase 1 through Phase 3** of [`global_planner_plan.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/global_planner_plan.md), satisfying all requirements from [`global_planner_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/global_planner_architecture.md), [`pipeline_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/pipeline_architecture.md), and [`teleop_mecanum.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/teleop_mecanum.py).

---

## 1. System Architecture & Features Implemented

```
+---------------------------------------------------------------------------------------------+
|                                    ROS 2 MISSION LAYER                                      |
|  +-----------------------------+               +-----------------------------------------+  |
|  | Waypoint Client             |  Action Goal  | WaypointGlobalPlannerNode               |  |
|  | (YAML List / Aruco / Manual)| ------------> | (Action Server: WaypointSet.action)     |  |
|  +-----------------------------+               +-----------------------------------------+  |
+-------------------------------------------------------------|-------------------------------+
                                                              | Lookahead Carrot & Path
                                                              v
+---------------------------------------------------------------------------------------------+
|                                JETSON ORIN NANO SAFETY GATE                                 |
|  +---------------------------------------------------------------------------------------+  |
|  | 1. Sensor Freshness Filter: Discards IMU/LiDAR older than 25 ms (20-30 ms threshold)   |  |
|  | 2. Lookahead Carrot Tracker: Generates nominal (cmd_vx, cmd_vy, cmd_omega, delta_theta)|  |
|  | 3. Safety Gate Forward Predictor: 0.1s kinematic projection vs 15cm obstacle boundary  |  |
|  | 4. Emergency Backoff Recovery FSM: Reverse 0.15 m/s for 0.1s -> resume inference       |  |
|  | 5. Dynamic Speed Parameters: Runtime speed scaling without waiting for keypresses     |  |
|  +---------------------------------------------------------------------------------------+  |
+------------------------------------|------------------------^-------------------------------+
                        Nominal Obs  |                        | AI Actions
                        (74-D Q8.8)  v                        | (3-D Q8.8)
+-------------------------------------------------------------|-------------------------------+
|                       ACCELERATION ENGINE (DUAL-MODE)                                       |
|  +---------------------------------------------------------------------------------------+  |
|  | Ethernet UDP (Port 8080) to DE10-Nano FPGA / UART / Local CPU fallback                 |  |
|  | 74-D Vector: 64 LiDAR + 6 IMU + 3 Twist + 1 Heading                                    |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
                                                              | Safe Blended Twist
                                                              v
+---------------------------------------------------------------------------------------------+
|                                    ACTUATION & LOW-LEVEL                                    |
|  +---------------------------------------------------------------------------------------+  |
|  | Mecanum Inverse Kinematics (Right-side sign mirror: FL: M1, RL: M2, FR: -M3, RR: -M4)   |  |
|  | STM32 Motor Driver: 4-wheel RPS packet (Func 0x03, 1 Mbps)                             |  |
|  | Hardware Watchdog: Implemented (HeartbeatWatchdog, dormant by default)                |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
```

### Key Features Implemented:
1. **Closed-Loop Waypoint Global Planner**:
   - Replaced open-loop duration sleeping with closed-loop pose feedback (`/pose` subscription from SLAM, odometry, or `motion_node`).
   - Compliant with `WaypointSet.action` (`absis`, `ordinat`, `yaw`, `duration`).
   - Supports both translational tracking and in-place pure rotational movements.
   - Publishes continuous real-time feedback (`absis_feedback`, `ordinat_feedback`, `yaw_feedback`, and `progress` string).
2. **Sensor Freshness Drop Gate (20–30 ms)**:
   - Tracks arrival timestamps for incoming RPLiDAR (`/scan`) and STM32 MPU-6050 IMU telemetry.
   - Evaluates sensor age against a 25 ms threshold (designed for the ~16 ms FPGA processing latency). Stale messages are dropped and logged to prevent lagging inferences.
3. **Jetson Orin Nano Predictive Safety Gate (0.1s Horizon / 15 cm Barrier)**:
   - Predicts 0.1s forward displacement based on candidate inference velocities.
   - If displacement enters the 15 cm obstacle zone in the directional motion cone:
     - Blocks FPGA inference inputs (stalls inference).
     - Commands an immediate stop followed by a 0.1s emergency reverse backoff at 0.15 m/s.
     - Automatically resets and resumes normal tracking once backoff is complete.
4. **Dual-Mode DE10-Nano FPGA Bridge (Ethernet UDP & UART)**:
   - Supports Gigabit Ethernet UDP streaming to DE10-Nano HPS (`192.168.1.50:8080` or `127.0.0.1:8080` for mock mode) and serial UART fallback.
   - Packets serialized in signed Q8.8 fixed-point format with CRC-32 checksum.
5. **Dynamic Runtime Speed Scaling**:
   - ROS 2 dynamic parameter callback (`_on_parameter_change`) enables updating `max_linear_x`, `max_linear_y`, `max_angular_z`, and `speed_scale` at runtime without keypress delays.
6. **Hardware Watchdog**:
   - `HardwareWatchdog` class is fully implemented and hooked into the command stream, configured dormant by default (`enable_watchdog:=false`).

---

## 2. File Directory & Function Call Workflow

| File | Primary Functions & Classes | Description |
|---|---|---|
| [`waypoint_global_planner_node.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_controller/igor_controller/waypoint_global_planner_node.py) | `WaypointGlobalPlannerNode`<br>`compute_closed_loop_twist()`<br>`execute_callback()`<br>`_pose_callback()` | ROS 2 Action Server for `WaypointSet`. Tracks robot pose, computes lookahead commands, and publishes to `/cmd_vel_in` and `/cmd_vel`. |
| [`controller_node.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_controller/igor_controller/controller_node.py) | `IgorControllerNode`<br>`_control_loop()`<br>`check_forward_collision_risk()`<br>`_on_parameter_change()`<br>`HardwareWatchdog` | Main 50 Hz controller. Enforces sensor freshness drop gate, predictive safety gate, 0.1s backoff recovery FSM, 74-D observation assembly, and Mecanum IK. |
| [`fpga_bridge.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_controller/igor_controller/fpga_bridge.py) | `FPGABridge`<br>`infer()`<br>`checksum_crc8()`<br>`compute_crc32()` | Communicates with Cyclone V DE10-Nano over Ethernet UDP port 8080 or UART serial, packing 74 Q8.8 inputs and receiving 3 Q8.8 actions. |
| [`bringup.launch.py`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_bringup/launch/bringup.launch.py) | `generate_launch_description()` | Master bringup launch file supporting single-command launch of RPLiDAR driver, Igor controller, and waypoint global planner. |
| [`demo_rectangle.yaml`](file:///home/hadynata/vs-code-data/Python/igor_ws/waypoint_list/waypoint_client/point/demo_rectangle.yaml) | Waypoint List | Mission route configuration for the 3m x 5m rectangular navigation demo. |

---

## 3. Dedicated Demo Case: 3m x 5m Rectangle Traversal

For the demo, the global planner executes a complete **3m x 5m rectangle trajectory**:
$$\text{Forward } (5\text{m}) \longrightarrow \text{Left } (90^\circ) \longrightarrow \text{Forward } (3\text{m}) \longrightarrow \text{Left } (90^\circ) \longrightarrow \text{Forward } (5\text{m}) \longrightarrow \text{Left } (90^\circ) \longrightarrow \text{Forward } (3\text{m})$$

### Rectangle Geometry & Coordinates:
- **Start Pose**: $(0.0, 0.0), \text{yaw} = 0^\circ$
- **Segment 1 (Side 1 = 5m)**: Move forward to $(5.0, 0.0)$, heading $0^\circ$.
- **Segment 2 (Turn 1)**: Rotate in-place to heading $90^\circ$ (pointing left / $+Y$).
- **Segment 3 (Side 2 = 3m)**: Move forward to $(5.0, 3.0)$, heading $90^\circ$.
- **Segment 4 (Turn 2)**: Rotate in-place to heading $180^\circ$ (pointing rear / $-X$).
- **Segment 5 (Side 3 = 5m)**: Move forward to $(0.0, 3.0)$, heading $180^\circ$.
- **Segment 6 (Turn 3)**: Rotate in-place to heading $-90^\circ / 270^\circ$ (pointing $-Y$).
- **Segment 7 (Side 4 = 3m)**: Move forward to $(0.0, 0.0)$, returning to origin with heading $0^\circ$.

The waypoints are defined in [`waypoint_list/waypoint_client/point/demo_rectangle.yaml`](file:///home/hadynata/vs-code-data/Python/igor_ws/waypoint_list/waypoint_client/point/demo_rectangle.yaml):
```yaml
waypoints:
  - x: 5.0
    y: 0.0
    yaw: 0.0
    duration: 12.0
  - x: 0.0
    y: 0.0
    yaw: 90.0
    duration: 3.0
  - x: 5.0
    y: 3.0
    yaw: 90.0
    duration: 8.0
  - x: 0.0
    y: 0.0
    yaw: 180.0
    duration: 3.0
  - x: 0.0
    y: 3.0
    yaw: 180.0
    duration: 12.0
  - x: 0.0
    y: 0.0
    yaw: -90.0
    duration: 3.0
  - x: 0.0
    y: 0.0
    yaw: 0.0
    duration: 8.0
```

---

## 4. How to Run the 3m x 5m Rectangle Demo

### Step 1: Start the Accelerator Daemon
- **On Physical DE10-Nano FPGA**:
  ```bash
  cd ~/igor_pipeline/hps_de10
  sudo ./de10_server_daemon --hw --port 8080
  ```
- **Or on Local Host (Simulation / Mock Mode)**:
  ```bash
  ./src/igor_pipeline/hps_de10/de10_server_daemon --mock --port 8080
  ```

### Step 2: Start Master Robot Bringup
In a separate terminal on the Jetson Orin Nano, launch the full navigation stack:
```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch igor_bringup bringup.launch.py \
    algorithm:=cl_drl_cbf \
    use_fpga:=true \
    fpga_port:="udp://192.168.1.50:8080" \
    mcu_port:=/dev/ttyACM0 \
    lidar_port:=/dev/lidar \
    use_mock_serial:=false \
    launch_planner:=true
```
*(If running purely on a PC/laptop without physical hardware, set `use_mock_serial:=true`, `launch_lidar:=false`, and `fpga_port:="udp://127.0.0.1:8080"`)*.

### Step 3: Run the Waypoint Action Client
In a third terminal, start the waypoint client listener:
```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 run waypoint_client waypoint_client_node
```

### Step 4: Dispatch the 3m x 5m Rectangle Route
In a fourth terminal, publish the filename to trigger the route execution:
```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 topic pub --once /waypoint_filename std_msgs/msg/String "{data: 'demo_rectangle.yaml'}"
```

### Step 5: Visualizing and Monitoring in Rviz
To monitor the robot's pose trajectory, lookahead carrot tracking, and LiDAR obstacle field:
```bash
rviz2 -d waypoint_list/waypoint_server/rviz/waypoint_config.rviz
```

The robot will execute each segment sequentially:
1. Progressively drive forward 5 meters.
2. Rotate 90 degrees to face left.
3. Drive forward 3 meters.
4. Rotate 90 degrees to face rear.
5. Drive forward 5 meters.
6. Rotate 90 degrees to face start.
7. Drive forward 3 meters back to origin $(0.0, 0.0)$.
All motor commands are continuously validated by the 0.1s predictive safety gate and accelerated via DE10-Nano FPGA inference.


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `global_planner_plan.md`

SHA256: `568bad80748bf551e01ff6d0af0e07f03bc90ab4ed6871df0f6622bc1950a335`

<!-- BEGIN ORIGINAL DOCUMENT -->

# Global Planner Architecture & Implementation Plan: `global_planner_plan.md`

## 1. Executive Summary & Objective

The objective of this architecture and implementation plan is to design and integrate a **Robust Global Planner** for Project IGOR (Hiwonder JetAuto Mecanum AMR). The system incorporates:
1. **Global Goal/Waypoint Mission Management**: Based on ROS 2 Action Server/Client paradigm modeled after the reference in `waypoint_list/` (`waypoint_Action_Server`, `waypoint_Action_Client`, `WaypointSet.action`, and YAML sequence dispatcher).
2. **AI & FPGA Hardware Acceleration Integration**: Seamlessly feeding lookahead navigation commands to the 74-dimensional observation vector of the AI model (`64 LiDAR + 6 IMU + 3 Twist + 1 Heading`) running either on the Cyclone V DE10-Nano FPGA accelerator (via UDP over Gigabit Ethernet as specified in `pipeline_architecture.md` / `global_planner_architecture.md`, with fallback to serial/mock) or local CPU inference.
3. **Jetson Orin Nano Safety Gate & Active Recovery**: Implementing an obstacle-predictive safety gate that:
   - Evaluates a 0.1s forward collision envelope ($r_{\text{safe}} = 15\text{ cm}$ radius boundary) against raw LiDAR and IMU telemetry.
   - Triggers hard stall on FPGA inference input, performs an active emergency backoff recovery maneuver (reversing at $0.15\text{ m/s}$ for $0.1\text{ s}$), and resumes target tracking.
   - Enforces a 20–30 ms freshness timeout / drop policy on raw sensor inputs to prevent stale inferences from lagging FPGA execution ($~16\text{ ms}$ PL execution time).
4. **Mecanum Dynamic Velocity Dispatch**: Adapting runtime speed bounds dynamically (like `teleop_mecanum.py` runtime speed scaling) and converting twist outputs to 4-wheel Mecanum RPS (with physical right-side sign inversion).
5. **Substantial Robustness Enhancements**: Transitioning from open-loop, time-stepped coordinate dead-reckoning (used in the naive `waypoint_list`) to closed-loop closed-space tracking with carrot lookahead, adaptive waypoint switching, stuck detection, dynamic re-planning, and graceful degradation.

---

## 2. Analysis of Existing Codebase & Identified Limitations

### 2.1 The Reference `waypoint_list/` Mechanism
In `waypoint_list/waypoint_server/waypoint_server/waypoint_Action_Server.py`:
- **Open-Loop Execution**: It calculates linear and angular velocities simply as $(x_2 - x_1)/t$ and $(\psi_2 - \psi_1)/t$ and loops with `time.sleep(0.1)` until elapsed time reaches duration.
- **Blind Assumption**: The robot assumes it reaches the exact target coordinate at the end of the time duration, completely ignoring wheel slip, obstacle detours, delays, or external disturbances.
- **Disconnected from AI & Sensors**: It publishes directly to `/cmd_vel` without sensing LiDAR or feeding the 74-D input observation pipeline.

### 2.2 The AI Inference Pipeline (`src/igor_controller` & `src/igor_navigation`)
- **Neural Network Architecture**: MLP taking 74 inputs:
  - `obs[0..63]`: 64 normalized frontal LiDAR rays ($[-\pi/2, +\pi/2]$, clipped to 3.5m).
  - `obs[64..66]`: IMU linear accelerations $(a_x, a_y, a_z) / 3.0$.
  - `obs[67..69]`: IMU angular velocities $(\omega_x, \omega_y, \omega_z) / 2.0$ in rad/s.
  - `obs[70..72]`: Nominal commanded velocities $(v_x / 0.60, v_y / 0.50, \omega_z / 2.0)$.
  - `obs[73]`: Course-Lock normalized heading error $\Delta \theta / \pi \in [-1, 1]$.
- **Residual Output**: 3 actions $(\Delta v_x, \Delta v_y, \Delta \omega_z)$ in $[-1, 1]$ quantized in Q8.8 fixed point for DE10-Nano FPGA accelerator.
- **Nominal Guidance Needed**: The AI model is trained as a **gated residual collision avoidance controller**. It *requires* a valid nominal velocity $(v_x, v_y, \omega_z)$ and heading error $\Delta \theta$ directed toward the target lookahead carrot. Without a goal-directed nominal command, the robot cannot progress to global waypoints.

---

## 3. Robustness Architecture & Critical Improvements

To achieve production-grade robustness and satisfy all requirements from `global_planner_architecture.md`, the new global planner architecture replaces the naive open-loop system with the following improvements:

```
+---------------------------------------------------------------------------------------------+
|                                    ROS 2 MISSION LAYER                                      |
|  +-----------------------------+               +-----------------------------------------+  |
|  | Waypoint Client             |  Action Goal  | Igor Global Planner Node                |  |
|  | (YAML List / Aruco / Manual)| ------------> | (Action Server: WaypointSet.action)     |  |
|  +-----------------------------+               +-----------------------------------------+  |
+-------------------------------------------------------------|-------------------------------+
                                                              | Lookahead Carrot & Path
                                                              v
+---------------------------------------------------------------------------------------------+
|                                JETSON ORIN NANO SAFETY GATE                                 |
|  +---------------------------------------------------------------------------------------+  |
|  | 1. Sensor Freshness Filter: Discards IMU/LiDAR older than 20-30 ms                     |  |
|  | 2. Lookahead Carrot Tracker: Generates nominal (cmd_vx, cmd_vy, cmd_omega, delta_theta)|  |
|  | 3. Safety Gate Forward Predictor: 0.1s kinematic projection vs 15cm obstacle zone      |  |
|  | 4. Emergency Backoff Recovery FSM: Reverse 0.15 m/s for 0.1s -> resume inference       |  |
|  +---------------------------------------------------------------------------------------+  |
+------------------------------------|------------------------^-------------------------------+
                        Nominal Obs  |                        | AI Actions
                        (74-D Q8.8)  v                        | (3-D Q8.8)
+-------------------------------------------------------------|-------------------------------+
|                       ACCELERATION ENGINE (DUAL-MODE)                                       |
|  +---------------------------------------------------------------------------------------+  |
|  | Gigabit Ethernet (UDP port 8080) to DE10-Nano HPS/FPGA (or UART / Local CPU fallback) |  |
|  | Inference: 74 inputs -> MLP (128 -> 64 -> 3) -> raw delta twist actions (~16 ms)      |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
                                                              | Safe Blended Twist
                                                              v
+---------------------------------------------------------------------------------------------+
|                                    ACTUATION & LOW-LEVEL                                    |
|  +---------------------------------------------------------------------------------------+  |
|  | Mecanum Inverse Kinematics (Right-side sign mirror) + Dynamic Max Speed Scaling       |  |
|  | STM32 Motor Driver: 4-wheel RPS packet (Func 0x03, 1 Mbps)                             |  |
|  | Hardware Watchdog: Implemented & configurable (passive/dormant by default)             |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
```

### 3.1 Closed-Loop Lookahead Tracking vs. Open-Loop Timing
* **Improvement**: Replace the timer-based duration loop with closed-loop pose feedback (fused from wheel odometry, IMU yaw, or SLAM `/pose`).
* **Mechanism**: Use `GlobalPath` and `LookaheadCarrotTracker` (from `igor_navigation.utils.path_tracker`) to dynamically compute nominal body velocities $(v_x, v_y, \omega_z)$ directed toward a carrot point at lookahead distance $L_d$ (default $0.60\text{ m}$).
* **Goal Tolerance & Timeout**: Waypoint transition triggers when Euclidean distance to target $< \epsilon_{\text{dist}}$ (e.g., $0.15\text{ m}$) and angular error $< \epsilon_{\text{yaw}}$ (e.g., $0.1\text{ rad}$), with a maximum timeout guard to prevent infinite hanging.

### 3.2 Sensor Freshness Timeout Gate (20–30 ms)
* **Requirement**: "Safety guard also have the behavior to drop the message from the input from the raw data if the raw data seemed old with timeout like 20-30 ms (it is because the processing of data of fpga took around 16 ms from my current testing)"
* **Mechanism**: Every incoming LiDAR and IMU message is timestamped with system monotonic nanoseconds. Before packing the 74-D observation vector:
  $$\Delta t_{\text{sensor}} = t_{\text{current}} - t_{\text{sensor\_stamp}}$$
  If $\Delta t_{\text{sensor}} > 25\text{ ms}$ (configurable 20–30 ms), the stale frame is dropped. If staleness persists for $> 3$ consecutive ticks, the node drops nominal velocity to 0 and holds position until fresh sensor data arrives.

### 3.3 Active Safety Gate & 0.1s Forward Collision Prediction
* **Requirement**: Calculate position for the next $0.1\text{ s}$ with the given inference from FPGA. If it enters a $15\text{ cm}$ boundary zone of an obstacle aligned with movement direction:
  1. Block all input to FPGA (stalling inference).
  2. Stop and reverse backward for $0.1\text{ s}$ with velocity $0.15\text{ m/s}$.
  3. Resume inference toward the former target.
* **Kinematic Forward Projection**:
  Given current robot pose $(x_0, y_0, \theta_0)$ and candidate twist $(v_x, v_y, \omega)$:
  $$\theta_{0.1} = \theta_0 + \omega \cdot \Delta t \quad (\Delta t = 0.1\text{ s})$$
  $$\begin{bmatrix} \Delta x_{\text{world}} \\ \Delta y_{\text{world}} \end{bmatrix} = \begin{bmatrix} \cos\theta_0 & -\sin\theta_0 \\ \sin\theta_0 & \cos\theta_0 \end{bmatrix} \begin{bmatrix} v_x \Delta t \\ v_y \Delta t \end{bmatrix}$$
  $$p_{0.1} = [x_0 + \Delta x_{\text{world}},\; y_0 + \Delta y_{\text{world}}]$$
* **Obstacle Boundary Test**:
  Check distance from $p_{0.1}$ to all LiDAR detected obstacle points within the directional motion cone:
  $$d_{\text{obs}} = \min_i \| p_{0.1} - p_{\text{obs}, i} \|$$
  If $d_{\text{obs}} < R_{\text{boundary}} = 0.15\text{ m}$ (safety bubble):
  - Transition state machine to `SAFETY_GATE_ACTIVE`.
  - Suppress FPGA TX packets (freeze FPGA inference).
  - Inject reverse recovery maneuver: $v_x = -0.15\text{ m/s},\; v_y = 0.0,\; \omega = 0.0$ for $t_{\text{reverse}} = 0.1\text{ s}$.
  - Transition to `RESUME_TRACKING` once backoff completes.

### 3.4 Runtime Speed Scaling Without Keypress Stalls
* **Requirement**: "changing max speed value when runtime will also change the value itself without waiting for any input key for its direction."
* **Mechanism**: Implement a dynamic ROS 2 Parameter callback (`add_on_set_parameters_callback`) for `max_linear_speed`, `max_angular_speed`, and `speed_scale_factor` (0.1 to 2.0). When updated via ROS 2 CLI (`ros2 param set ...`) or teleop publisher, the controller recalculates kinematic bounds immediately without re-initialization or waiting for directional inputs.

### 3.5 Watchdog Architecture
* **Requirement**: "For its hardware watchdog, implement it but don't activate it for now as I want to prove the system fully running without handling the safety of the jetson for now."
* **Mechanism**: Provide a dedicated `HeartbeatWatchdog` class on the Jetson that formats ping/keepalive packets and checks serial/socket activity. Add a boolean flag `enable_watchdog = False` (default) so that the watchdog structure is present, fully tested in mock, but dormant during initial hardware validation.

---

## 4. Architectural Data Flow & Component Mapping

```
                                      +---------------------------------------------+
                                      |            waypoint_client_node             |
                                      | Reads waypoints.yaml & Aruco Docking goals  |
                                      +---------------------------------------------+
                                                             |
                                                             | WaypointSet.action
                                                             v
                                      +---------------------------------------------+
                                      |          igor_global_planner_node           |
                                      | - Action Server (WaypointSet)               |
                                      | - Multi-goal queue management               |
                                      | - Lookahead Carrot Generator                |
                                      | - Progress & State Publisher                |
                                      +---------------------------------------------+
                                                             |
                                                             | /cmd_vel_in + Waypoint carrot
                                                             v
+------------------+  /scan (360)     +---------------------------------------------+
| RPLiDAR A1/A2    | ---------------> |             igor_controller_node            |
+------------------+  (Subsampled 64) | - Freshness Gate (< 25ms timeout)           |
                                      | - 74-D Vector Packing (Q8.8)                |
+------------------+  Func 0x07 (1M)  | - Ethernet UDP Bridge to DE10-Nano (8080)   |
| STM32 IMU Driver | ---------------> | - 0.1s Predictive Safety Gate               |
+------------------+  (ax..az, gx..gz)| - 0.15 m/s Reverse Recovery FSM             |
                                      | - Dynamic Speed Parameter Callback          |
                                      +---------------------------------------------+
                                                             |
                                                             | Func 0x03 (4x Mecanum RPS)
                                                             v
                                      +---------------------------------------------+
                                      |           STM32 Motor Controller            |
                                      | (FL: M1, RL: M2, FR: -M3, RR: -M4)          |
                                      +---------------------------------------------+
```

---

## 5. Step-by-Step Implementation Plan

### Phase 1: Global Planner Action Server Upgrade (`igor_planner`)
1. Create `igor_planner` package (or extend `igor_navigation` and `waypoint_server`) with:
   - Action server implementing `WaypointSet.action` compatible with `waypoint_client`.
   - Closed-loop waypoint navigation using robot odometry/pose instead of open-loop `time.sleep`.
   - Continuous real-time feedback computation: `absis_feedback`, `ordinat_feedback`, `yaw_feedback`, and `progress` percentage.
   - Smooth lookahead carrot calculation feeding the local controller via `/cmd_vel_in` and `/igor/target_pose`.

### Phase 2: Sensor Freshness Filter & 74-D Vector Pipeline
1. In `igor_controller/controller_node.py`:
   - Enhance LiDAR subsampler and IMU callback to track nanosecond timestamps.
   - Introduce `MAX_SENSOR_LATENCY_SEC = 0.025` (25 ms).
   - If sensor data age $> 25\text{ ms}$, reject packet and log warning; fall back to safe zero-command if timeout exceeds 3 cycles ($60\text{ ms}$).
   - Package validated 74-D vector with normalized sensors, nominal velocities, and heading error.

### Phase 3: Jetson Orin Nano Predictive Safety Gate & Recovery FSM
1. In `igor_controller/controller_node.py`:
   - Implement `check_forward_collision_risk(candidate_twist, lidar_beams, dt=0.1, radius=0.15)`.
   - Implement 3-State Recovery FSM:
     - `STATE_NORMAL`: Feed 74-D observation to DE10 FPGA; execute gated residual actions.
     - `STATE_SAFETY_TRIPPED`: When 0.1s forward trajectory enters 15 cm obstacle zone:
       * Inhibit outgoing UDP packets to DE10 (stall inference).
       * Command immediate stop, then $v_x = -0.15\text{ m/s}$ for $0.1\text{ s}$.
     - `STATE_RECOVERY_COMPLETE`: Reset obstacle trajectory buffer and resume inference toward original global waypoint.

### Phase 4: DE10-Nano Ethernet UDP Bridge Integration
1. Extend `fpga_bridge.py`:
   - Implement `UDPFPGABridge` adhering to `pipeline_architecture.md`:
     * Target IP: `192.168.1.50` (or `127.0.0.1` in mock mode), Port `8080`.
     * Binary packed structs with Q8.8 fixed-point serialization.
     * Socket timeout of $30\text{ ms}$ (with fallback to CPU controller if bridge packet is lost).

### Phase 5: Dynamic Speed Adjustment & Watchdog Skeleton
1. In `controller_node.py` and `teleop_mecanum.py`:
   - Bind dynamic parameter reconfiguration to adjust `max_linear_x`, `max_linear_y`, `max_angular_z`, and `speed_multiplier` without needing directional keypresses.
   - Implement dormant `STM32Watchdog` with heartbeat frame generation, enabled via parameter `enable_watchdog` (default: `False`).

### Phase 6: Dual-Mode Testing & Verification
1. Stage 1: Software Loopback / Mock Mode:
   - Run simulated `mock_de10_host_server` and `waypoint_client` with sample `waypoints.yaml`.
   - Verify closed-loop waypoint transition, feedback reporting, and mock safety gate intervention.
2. Stage 2: Hardware Deployment:
   - Deploy on Jetson Orin Nano connected to STM32 over USB (`/dev/ttyACM0`) and DE10-Nano over Gigabit Ethernet.

---

## 6. Verification Criteria & Acceptance Metrics

| Verification Item | Acceptance Criteria |
|---|---|
| **Waypoint Action Server** | Successfully accepts `WaypointSet` goals, publishes real-time feedback, and reaches target with tolerance $< 0.15\text{ m}$ closed-loop. |
| **Observation Dimension** | Bit-for-bit compliance with 74-D vector (`64 LiDAR + 6 IMU + 3 Twist + 1 Heading`) in Q8.8 fixed point. |
| **Sensor Freshness Gate** | Stale sensor data older than $25\text{ ms}$ is dropped and flagged before reaching FPGA inference. |
| **0.1s Predictive Safety Gate** | When obstacle is within 15 cm of predicted 0.1s forward path, inference stalls and robot backs up at $0.15\text{ m/s}$ for $0.1\text{ s}$. |
| **Dynamic Speed Scaling** | Updating speed parameter modifies robot speed in real-time without requiring directional trigger. |
| **Watchdog Dormancy** | Watchdog code exists and builds cleanly, remaining inactive by default (`enable_watchdog:=false`). |


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `pipeline_architecture.md`

SHA256: `9537bb940979e4661708c6e48716344c35a89aef53e404a50fdca381dbedf3bd`

<!-- BEGIN ORIGINAL DOCUMENT -->

# Jetson Orin Nano <-> DE10-Nano FPGA AI Acceleration Bridge

This repository contains the software architecture, network protocols, Linux drivers, FPGA wrappers, and dual-mode testing frameworks for offloading AI inference from an **NVIDIA Jetson Orin Nano** to an **Intel DE10-Nano (Cyclone V SoC) FPGA Accelerator** over Gigabit Ethernet.

---

## 1. System Architecture & Dual-Mode Execution Topology

To allow risk-free development, the system supports a **Two-Stage Testing Protocol**:

1. **Software Loopback / Mock Mode (Offline Test):** Test the Jetson streamer and DE10 server logic on a local PC or Jetson without requiring physical Ethernet wiring or live FPGA hardware.
2. **Hardware Gigabit Ethernet Mode (Live Deployment):** Route high-speed UDP streams over Gigabit Ethernet directly into the DE10-Nano HPS memory for FPGA Programmable Logic (PL) acceleration.

```
[ STAGE 1: SOFTWARE MOCK MODE (Local Loopback / No Hardware) ]
+-------------------------------------------------------------------------+
| Jetson Orin Nano / Host PC                                              |
|  +------------------+     UDP (127.0.0.1)      +--------------------+  |
|  | Jetson Streamer  | <-----------------------> | Mock DE10 Server   |  |
|  | (Client Mode)    |                           | (CPU AI Simulator) |  |
|  +------------------+                           +--------------------+  |
+-------------------------------------------------------------------------+

[ STAGE 2: PHYSICAL HARDWARE MODE (Gigabit Ethernet + FPGA) ]
+--------------------+        Gigabit Ethernet        +-------------------+
| Jetson Orin Nano   | <----------------------------> | DE10-Nano (SoC)   |
| (Client Streamer)  |     UDP Payload (Port 8080)    |  +--------------+ |
+--------------------+                                |  | HPS (Linux)  | |
                                                      |  +------|-------+ |
                                                      |  lwHPS  | F2S DMA |
                                                      |  +------v-------+ |
                                                      |  | FPGA PL Core | |
                                                      |  +--------------+ |
                                                      +-------------------+

```

---

## 2. Antigravity Execution Rules & Code Policies

When executing this project via **Antigravity** (or any autonomous AI coding agent), strictly follow these rules:

1. **Non-Destructive Code Augmentation (READ-ONLY Existing Files)**
* Never modify, delete, or overwrite existing files (`*.c`, `*.cpp`, `*.h`, `*.v`).
* Create new files (e.g., `*_ext.c`, `*_mock.cpp`, `*_adapter.v`) that wrap, include, or subclass existing files.


2. **Atomic Single-Chat Scope**
* Each module must be complete and buildable within a **single chat generation**.


3. **Dual-Interface Abstraction**
* Every component must provide an abstraction layer enabling seamless toggling between `--mode=mock` (software host simulation) and `--mode=hardware` (Cyclone V physical hardware).



---

## 3. Directory Structure Blueprint

```text
src/igor_bridge
├── README.md                           # Master Architecture & Plan
├── protocol/                           # Shared Network Definitions
│   ├── protocol_legacy.h               # Base struct definitions (Read-Only)
│   └── protocol_v2.h                   # Extended packed structs & serialization
├── hps_de10/                           # DE10-Nano Server & Memory Drivers
│   ├── de10_shared_mem_ext.c           # Physical memory / mmap interface
│   ├── de10_fpga_bridge.c              # Control register bridge driver
│   ├── de10_server_daemon.c            # Production server daemon (Hardware Mode)
│   └── mock_fpga_engine.c              # Software emulation backend
├── jetson_orin/                        # Jetson Orin Nano Streamer
│   ├── legacy_sensor_stream.cpp        # Sensor input interface (Read-Only)
│   ├── jetson_client_adapter.cpp       # Network socket layer
│   └── jetson_main.cpp                 # Main execution loop with mode flags
├── simulators/                         # Offline Host Testing Tools
│   └── mock_de10_host_server.cpp       # Standalone DE10 simulator for Jetson testing
└── scripts/                            # Operational & Benchmark Tools
    ├── test_local_loopback.sh          # Stage 1 offline test launcher
    ├── setup_network_hardware.sh       # Stage 2 network setup script
    └── benchmark_latency.py            # Performance visualizer

```

---

## 4. Modular Implementation Roadmap

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MODULE IMPLEMENTATION ROADMAP                         │
├───────────┬──────────────────────────────────┬──────────────────────────────┤
│ Module ID │ Target Scope                     │ Key Deliverable              │
├───────────┼──────────────────────────────────┼──────────────────────────────┤
│ Module 01 │ Protocol Layer (Shared)          │ Packed Binary Structs        │
│ Module 02 │ DE10-Nano Drivers & HAL          │ Memory Mapping & Hardware HAL│
│ Module 03 │ Offline Mock DE10 Server         │ Standalone Software Simulator│
│ Module 04 │ DE10-Nano Dual-Mode Server Daemon│ Server with --mock/--hw flags│
│ Module 05 │ Jetson Orin Client Streamer      │ Streamer with Loopback Support│
│ Module 06 │ Cyclone V FPGA PL Wrapper        │ Verilog Acceleration Wrapper │
│ Module 07 │ Testing Scripts & Benchmarking   │ Automated Test Pipelines     │
└───────────┴──────────────────────────────────┴──────────────────────────────┘

```

---

### Module 01: Extended Binary Protocol & Serialization Test

* **Objective:** Define binary structures (`SensorPacket` and `InferenceResponsePacket`) with memory-alignment guarantees and local verification utilities.
* **Non-Destructive Constraint:** Wrap `protocol_legacy.h` inside `protocol/protocol_v2.h`.
* **Deliverable:** `protocol/protocol_v2.h`.

### Module 02: DE10 Memory Driver & Hardware Abstraction Layer (HAL)

* **Objective:** Abstract hardware register access to allow software emulation fallback if `/dev/mem` is unavailable or running on a generic Linux machine.
* **Non-Destructive Constraint:** Create `hps_de10/de10_shared_mem_ext.c` without altering legacy drivers.
* **Deliverable:** `hps_de10/de10_shared_mem_ext.c` & `hps_de10/de10_shared_mem_ext.h`.

### Module 03: Standalone Software DE10 Server Simulator

* **Objective:** Build a lightweight C++ simulator (`simulators/mock_de10_host_server.cpp`) that runs locally on the Jetson or a PC. It mimics the DE10-Nano network behavior and returns synthesized AI results over UDP.
* **Deliverable:** `simulators/mock_de10_host_server.cpp` & `simulators/CMakeLists.txt`.

### Module 04: DE10-Nano Dual-Mode HPS Daemon

* **Objective:** Create the main DE10 HPS server daemon capable of running in two modes:
* `--mock`: Computes AI response in CPU memory without touching physical FPGA bridges (used to test Ethernet link stability).
* `--hw`: Uses physical memory addresses (`0x20000000`) and FPGA registers (`0xFF200000`).


* **Deliverable:** `hps_de10/de10_server_daemon.c` & `hps_de10/Makefile`.

### Module 05: Jetson Orin Client Streamer with Mode Switcher

* **Objective:** Implement the Jetson client node supporting `--target=localhost` (for Module 03/04 mock testing) and `--target=192.168.1.50` (for real DE10 hardware).
* **Deliverable:** `jetson_orin/jetson_client_adapter.cpp` & `jetson_orin/jetson_main.cpp`.

### Module 06: FPGA Hardware Acceleration Top Wrapper

* **Objective:** Build the Avalon-MM/AXI integration wrapper in Verilog (`fpga_pl/rtl/ai_accel_wrapper.v`) for live hardware deployment.
* **Deliverable:** `fpga_pl/rtl/ai_accel_wrapper.v`.

### Module 07: Dual-Stage Verification Scripts & Benchmarking

* **Objective:** Provide automated execution scripts for both Stage 1 (Software Loopback) and Stage 2 (Physical Hardware).
* **Deliverable:** `scripts/test_local_loopback.sh`, `scripts/setup_network_hardware.sh`, and `scripts/benchmark_latency.py`.

---

## 5. Antigravity Prompt Sequences

Feed these prompts sequentially into **Antigravity**.

---

### Prompt 01 — Module 01 Generation

> **Antigravity Instructions — Module 01**
> Inspect `protocol/` for existing files. Do **NOT** modify existing code.
> Create `protocol/protocol_v2.h` containing packed structs (`#pragma pack(push, 1)`):
> 1. `SensorPacket`: `frame_id` (uint32), `timestamp_ns` (uint64), `linear_velocity[3]` (float), `angular_velocity[3]` (float), `sensor_data_len` (uint32), `sensor_data[512]` (float).
> 2. `InferenceResponsePacket`: `frame_id` (uint32), `timestamp_ns` (uint64), `status_code` (uint32), `num_outputs` (uint32), `ai_results[128]` (float).
> 3. Provide validation functions to verify packet sizes and binary integrity.
> 
> 
> Output the entire code block in one response.

---

### Prompt 02 — Module 02 Generation

> **Antigravity Instructions — Module 02**
> Inspect `hps_de10/`. Create `hps_de10/de10_shared_mem_ext.h` and `hps_de10/de10_shared_mem_ext.c`.
> Implement a Hardware Abstraction Layer (HAL):
> 1. Function `hal_init(int is_mock)`: Maps `/dev/mem` for addresses `0xFF200000` (lwHPS2FPGA) and `0x20000000` (RAM) if `is_mock == 0`. Allocate heap buffers if `is_mock == 1`.
> 2. Register accessor wrappers: `hal_write_reg()`, `hal_read_reg()`, `hal_get_shared_buffer()`.
> 3. Clean unmap/free functions.
> 
> 
> Output complete C files in one response.

---

### Prompt 03 — Module 03 Generation

> **Antigravity Instructions — Module 03**
> Create `simulators/mock_de10_host_server.cpp` to act as an offline software emulator for the DE10-Nano.
> Features:
> 1. Listen on UDP port `8080` (or configurable port).
> 2. Receive `SensorPacket` from `protocol/protocol_v2.h`.
> 3. Simulate FPGA processing delay (`std::this_thread::sleep_for(std::chrono::microseconds(500))`).
> 4. Generate deterministic mock output values in `InferenceResponsePacket` and reply to sender.
> 5. Create CMakeLists.txt to build the simulator locally on any Linux host.
> 
> 
> Output full source code in one response.

---

### Prompt 04 — Module 04 Generation

> **Antigravity Instructions — Module 04**
> Create `hps_de10/de10_server_daemon.c` using `hps_de10/de10_shared_mem_ext.h` and `protocol/protocol_v2.h`.
> Implementation details:
> 1. Support CLI flags: `--mock` (emulate FPGA logic in C) and `--hw` (trigger real PL via mapped registers).
> 2. Listen on UDP port `8080`.
> 3. Process stream packets, manage input/output shared buffers, poll status flag (or emulate done signal), and send back response frames.
> 4. Include a production `Makefile` for ARM32 cross-compilation.
> 
> 
> Output all source code in one response.

---

### Prompt 05 — Module 05 Generation

> **Antigravity Instructions — Module 05**
> Create `jetson_orin/jetson_client_adapter.cpp` and `jetson_orin/jetson_main.cpp`.
> Features:
> 1. CLI option `--target <ip_address>` (default: `127.0.0.1` for mock, `192.168.1.50` for live DE10).
> 2. Socket timeout mechanism (`50ms`).
> 3. High-resolution timer measuring round-trip time (RTT) from packet send to response receive.
> 4. Summary display of throughput and packet loss.
> 5. CMakeLists.txt for ARM64 / x86 compilation.
> 
> 
> Output complete C++ implementation in one response.

---

### Prompt 06 — Module 06 Generation

> **Antigravity Instructions — Module 06**
> Create top-level Verilog hardware wrapper `fpga_pl/rtl/ai_accel_wrapper.v`.
> Features:
> 1. Avalon-MM Slave control interface (`Control`, `InPtr`, `OutPtr`, `Length`, `Status`).
> 2. FSM controlling data read, computation pulse, and completion interrupt.
> 3. Instantiation interface for custom AI acceleration execution units.
> 
> 
> Output pure Verilog code in one response.

---

### Prompt 07 — Module 07 Generation

> **Antigravity Instructions — Module 07**
> Create test automation scripts in `scripts/`:
> 1. `scripts/test_local_loopback.sh`: Compiles Jetson client and Mock Server, runs them locally on `127.0.0.1`, and validates data integrity.
> 2. `scripts/setup_network_hardware.sh`: Configures physical network interface (`192.168.1.10`, Jumbo Frames MTU 9000).
> 3. `scripts/benchmark_latency.py`: Parses execution logs, generates CSV summaries, and prints latency profiles.
> 
> 
> Output complete script implementations in one response.

---

## 6. Execution & Testing Workflow

### Stage 1: Local Offline Testing (No DE10 Hardware Required)

Verify protocol formatting, network socket code, and latency calculation locally on a single machine:

```bash
# Terminal 1: Launch Local DE10 Mock Server
cd simulators
mkdir build && cd build
cmake .. && make
./mock_de10_host_server --port 8080

# Terminal 2: Run Jetson Client targeting Local Loopback
cd jetson_orin/build
./jetson_ai_streamer --target 127.0.0.1 --port 8080

```

### Stage 2: DE10 Software Network Test (Ethernet Connected, No PL Access)

Verify physical Ethernet bandwidth between Jetson and DE10-Nano without risking FPGA memory conflicts:

```bash
# On DE10-Nano HPS: Run daemon in --mock mode
cd hps_de10
make
sudo ./de10_server_daemon --mock

# On Jetson Orin Nano: Target DE10 IP
./jetson_ai_streamer --target 192.168.1.50 --port 8080

```

### Stage 3: Full Physical Hardware Acceleration Mode

Execute end-to-end hardware acceleration over physical Ethernet:

```bash
# On DE10-Nano HPS: Run daemon in --hw mode
sudo ./de10_server_daemon --hw

# On Jetson Orin Nano: Run production streamer
./jetson_ai_streamer --target 192.168.1.50 --port 8080

```

---

## 7. Performance Benchmarking & Diagnostic Indicators

| Test Stage | Expected Round-Trip Latency | Target Throughput | Primary Verification Focus |
| --- | --- | --- | --- |
| **Stage 1 (Local Loopback)** | $< 100\ \mu\text{s}$ | $> 1000\text{ Hz}$ | Struct serialization & packet packing correctness |
| **Stage 2 (Network Mock)** | $300 - 600\ \mu\text{s}$ | $> 500\text{ Hz}$ | Ethernet cable stability & MTU configuration |
| **Stage 3 (FPGA Hardware)** | Latency dependent on PL Core | Dependent on PL execution | Complete system verification |

<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `pipeline_docs.md`

SHA256: `dd27986c1981694c665fc83e4b15cce14a818984e6f291be763efed163143e4f`

<!-- BEGIN ORIGINAL DOCUMENT -->

> **Current Ethernet setup:** follow [eth_direction.md](eth_direction.md) and
> [connection instructions](docs/connect_de10.md). The supported endpoint is
> `udp://192.168.50.2:8080`, with Jetson `192.168.50.1/24` on its actual wired
> interface (`enP8p1s0` on this Jetson). Older examples below using
> `192.168.1.50`, daemon `--hw`/`--mock`, or an HPS DDR/DMA bridge are obsolete.
> The deployed path requires HPS Linux plus an HPS-local USB-to-3.3 V UART
> adapter to the FPGA. Programming a SOF alone does not start Ethernet.
> See [Jetson diagnostic results](docs/jetson_de10_diagnosis.md).

# Project IGOR: Jetson Orin Nano <-> DE10-Nano FPGA Acceleration Pipeline Documentation (`pipeline_docs.md`)

This document provides complete technical documentation for the implementation of the **Gigabit Ethernet & Serial AI Acceleration Pipeline** described in [`pipeline_plan.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/pipeline_plan.md), [`pipeline_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/pipeline_architecture.md), and [`global_planner_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/global_planner_architecture.md).

---

## 1. System Overview & Technical Ground Truth

The acceleration pipeline offloads the **74-128-64-3 PPO Gated Residual policy** from the **NVIDIA Jetson Orin Nano** host controller to the **Intel Cyclone V SoC DE10-Nano FPGA** over high-speed Gigabit Ethernet UDP (port 8080) with automatic UART serial fallback.

### Ground Truth Parameters:
- **Observation Input**: 74 elements ($64\text{ frontal LiDAR} + 6\text{ IMU }(a_x, a_y, a_z, \omega_x, \omega_y, \omega_z) + 3\text{ nominal twist }(v_x, v_y, \omega) + 1\text{ Course-Lock heading error } \Delta\theta$).
- **Quantization**: Signed fixed-point **Q8.8** ($x_{\text{int}} = \text{round}(x \times 256.0)$).
- **Inference Output**: 3 delta actions ($[\Delta v_x, \Delta v_y, \Delta \omega_z]$ clamped in $[-1.0, 1.0]$).
- **PL Acceleration Core**: `igor_src_policy_core.v` (74 $\to$ 128 (ReLU) $\to$ 64 (ReLU) $\to$ 3 MLP) using 18,051 int16 quantized parameters from `policy_weights.mem`.
- **Global Planner Integration**: Lookahead carrot tracking from `WaypointGlobalPlannerNode` feeds nominal body velocity commands and heading difference into the 74-D observation vector, which is safety-checked and streamed to the DE10-Nano.

---

## 2. Hardware Wiring & Physical Interconnection Guide

To deploy the full hardware pipeline on the physical JetAuto robot, follow the wiring scheme below connecting the **Jetson Orin Nano**, the **DE10-Nano Cyclone V FPGA**, the **STM32 Sub-Controller**, and the **Slamtec RPLiDAR A1/A2**:

```
+---------------------------------------------------------------------------------------+
|                                    PHYSICAL WIRING                                    |
|                                                                                       |
|   +-----------------------+     Gigabit Ethernet (RJ45 Cat6)   +--------------------+ |
|   |                       | <================================> |                    | |
|   |   Jetson Orin Nano    |      Static IP: 192.168.1.10/24    | DE10-Nano SoC FPGA | |
|   |   (Master Controller) |      Target IP: 192.168.1.50:8080  | (AI Accelerator)   | |
|   |                       |                                    |                    | |
|   |                       | --- UART Fallback (Header JP1) --- | (GPIO 0 / JP1)     | |
|   |   Pin 8  (UART TXD)   | ---------------------------------> | GPIO_0[0] (RX)     | |
|   |   Pin 10 (UART RXD)   | <--------------------------------- | GPIO_0[1] (TX)     | |
|   |   Pin 9  (GND)        | ---------------------------------- | GND (Pin 12)       | |
|   +-----------------------+                                    +--------------------+ |
|         |          |                                                                  |
|         | USB      | USB                                                              |
|         v          v                                                                  |
|   +-----------+  +-------------------+                                                |
|   | RPLiDAR   |  | STM32 JetAuto MCU |                                                |
|   | /dev/lidar|  | /dev/ttyACM0      |                                                |
|   | (115.2k)  |  | (1,000,000 bps)   |                                                |
|   +-----------+  +-------------------+                                                |
|                            | 4x Motor Signals                                         |
|                            v                                                          |
|                  [M1:FL, M2:RL, M3:FR, M4:RR]                                         |
+---------------------------------------------------------------------------------------+
```

### Detailed Pin & Connector Connections:
1. **Gigabit Ethernet Connection (Primary Fast Link)**:
   - Connect a standard Cat5e/Cat6 RJ45 patch cable directly between the Jetson Orin Nano Gigabit Ethernet port and the DE10-Nano RJ45 port.
   - Jetson Ethernet IP: `192.168.1.10/24` (Subnet `255.255.255.0`).
   - DE10-Nano HPS Linux IP: `192.168.1.50/24` (Port: `8080`).
2. **UART Serial Connection (Fallback Link & Monitoring)**:
   - If utilizing UART instead of Ethernet:
     - **Jetson Pin 8 (UART2 TXD)** $\to$ **DE10-Nano GPIO_0[0] (Pin 1 on JP1 header)**.
     - **Jetson Pin 10 (UART2 RXD)** $\to$ **DE10-Nano GPIO_0[1] (Pin 2 on JP1 header)**.
     - **Jetson Pin 9 / 14 (GND)** $\to$ **DE10-Nano Ground (Pin 12 on JP1 header)**.
     - Baud rate: `115200` or `921600` bps.
3. **STM32 Motor & IMU Link**:
   - Micro-USB cable from Jetson USB 3.0 port to the JetAuto STM32 chassis controller USB port (`/dev/ttyACM0` @ 1,000,000 bps).
   - Transmits 4-wheel Mecanum RPS speed commands (Func `0x03`) and receives 6-DOF MPU-6050 IMU telemetry (Func `0x07`).
4. **LiDAR Link**:
   - USB cable from RPLiDAR A1/A2 adapter to Jetson USB port (`/dev/lidar` or `/dev/ttyUSB0` @ 115200 bps).

---

## 3. Implemented Components & File Mapping

```
src/igor_pipeline/
├── protocol/
│   ├── protocol_legacy.h             # Legacy baseline struct (Read-Only)
│   └── protocol_v2.h                 # Compact 74-D/3-D struct with Q8.8 & CRC-32
├── hps_de10/
│   ├── de10_driver_legacy.h          # Legacy driver header (Read-Only)
│   ├── de10_server_legacy.c          # Legacy server implementation (Read-Only)
│   ├── de10_shared_mem_ext.h         # Dual-mode HAL header (Mock & Physical Hardware)
│   ├── de10_shared_mem_ext.c         # HAL implementation (mmap /dev/mem or heap buffers)
│   ├── de10_server_daemon.c          # Production HPS server daemon (--mock / --hw)
│   └── Makefile                      # Build script for de10_server_daemon
├── simulators/
│   ├── mock_de10_host_server.cpp     # Standalone C++ offline simulator
│   └── CMakeLists.txt                # Build configuration for simulator
├── jetson_orin/
│   ├── jetson_client_legacy.cpp      # Legacy streamer client (Read-Only)
│   ├── jetson_client_adapter.hpp     # Production C++ streamer API
│   ├── jetson_client_adapter.cpp     # Low-latency UDP socket streamer implementation
│   ├── jetson_main.cpp               # Client benchmark & verification CLI tool
│   └── CMakeLists.txt                # Build configuration for client streamer
├── fpga_pl/
│   └── ai_accel_wrapper.v            # Avalon-MM Slave / DMA Master Verilog PL wrapper
└── scripts/
    ├── test_local_loopback.sh        # Stage 1 offline loopback automation test
    ├── setup_network_hardware.sh     # Stage 2 network configuration utility
    └── benchmark_latency.py          # Latency & jitter statistical profiler
```

---

## 4. Detailed Component Architecture & Function Calls

### 4.1 Extended Protocol (`protocol_v2.h`)
- **`SensorPacketV2`**: Packed struct transmitting:
  - `uint32_t magic` (`0x49474F52` = `"IGOR"`)
  - `uint32_t frame_id`
  - `uint64_t timestamp_ns` (monotonic high-resolution timestamp)
  - `float linear_velocity[3]`, `float angular_velocity[3]`
  - `uint32_t sensor_data_len` (`74`)
  - `float sensor_data[74]`
  - `int16_t q8_8_data[74]` (pre-quantized fixed-point array)
  - `uint32_t crc32`
- **`InferenceResponsePacketV2`**: Packed struct returning:
  - `uint32_t magic` (`0x49474F52`)
  - `uint32_t frame_id`, `uint64_t timestamp_ns` (echoed for RTT)
  - `uint32_t status_code`, `uint32_t num_outputs` (`3`)
  - `float ai_results[3]`, `int16_t q8_8_results[3]`
  - `uint32_t execution_cycles`, `uint32_t crc32`

### 4.2 Dual-Mode Memory HAL (`de10_shared_mem_ext.c`)
- **`hal_init(SoC_HAL_Context *ctx, int is_mock)`**:
  - `is_mock == 0`: Maps `/dev/mem` for lightweight bridge (`0xFF200000`, span 2MB) and shared SDRAM (`0x20000000`, span 16MB).
  - `is_mock == 1`: Allocates virtual aligned heap buffers, preventing segmentation faults when testing on non-FPGA hosts.
- **Double-Buffering Ping-Pong**:
  - Configures `in_buf_ping` (0x000000), `out_buf_ping` (0x400000), `in_buf_pong` (0x800000), `out_buf_pong` (0xC00000) in shared DDR.
- **`hal_trigger_inference(SoC_HAL_Context *ctx, int bank, uint32_t len, uint32_t timeout_us)`**:
  - Pulses start bit (`*accel_ctrl = 0x01`).
  - Monitors `*accel_status` done bit with a 20 ms timeout watchdog.

---

## 5. How to Test Connection & Run Full Pipeline (End-to-End)

Follow this complete step-by-step procedure to test connectivity, run the bringup stack, send global planner waypoint routes, stream AI observations to the FPGA, receive delta actions, and drive the Mecanum chassis.

### Step 1: Verify Hardware Network Connection
On the Jetson Orin Nano, configure the Ethernet interface and verify connectivity with the DE10-Nano:
```bash
# 1. Configure Jetson IP address
sudo ip addr add 192.168.1.10/24 dev eth0 || true
sudo ip link set eth0 up

# 2. Ping DE10-Nano to verify physical cable link
ping -c 3 192.168.1.50
```

### Step 2: Test Low-Level FPGA Streaming Connection
Test UDP packet transmission and verify Round-Trip Time (RTT) before launching ROS 2:
```bash
# Target live DE10-Nano hardware (or use 127.0.0.1 for mock testing)
python3 src/igor_pipeline/scripts/benchmark_latency.py 192.168.1.50 8080
```
Expected output:
```text
Total Sent: 200, Total Received: 200, Packet Loss Rate: 0.00%
Mean RTT: ~2.0 ms
```

### Step 3: Launch DE10 Server Daemon
- **On Physical DE10-Nano (via SSH / Serial Console)**:
  ```bash
  cd ~/igor_pipeline/hps_de10
  sudo ./de10_server_daemon --hw --port 8080
  ```
- **On Local Jetson (Mock Verification Mode)**:
  ```bash
  ./src/igor_pipeline/hps_de10/de10_server_daemon --mock --port 8080
  ```

### Step 4: Launch Master Robot Bringup
Launch the entire system in a new terminal on the Jetson Orin Nano. This activates:
- RPLiDAR Driver (`/scan`)
- STM32 MCU Driver (`/dev/ttyACM0` for motor execution & IMU feedback)
- `IgorControllerNode` (Freshness gate, 0.1s predictive safety gate, FPGA UDP streamer)
- `WaypointGlobalPlannerNode` (Action Server `/waypoint`)

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

# For live hardware deployment:
ros2 launch igor_bringup bringup.launch.py \
    algorithm:=cl_drl_cbf \
    use_fpga:=true \
    fpga_port:="udp://192.168.1.50:8080" \
    mcu_port:=/dev/ttyACM0 \
    lidar_port:=/dev/lidar \
    use_mock_serial:=false \
    launch_planner:=true

# (Or for local software simulation without hardware):
ros2 launch igor_bringup bringup.launch.py \
    algorithm:=cl_drl_cbf \
    use_fpga:=true \
    fpga_port:="udp://127.0.0.1:8080" \
    use_mock_serial:=true \
    launch_lidar:=false \
    launch_planner:=true
```

### Step 5: Send Route Command to Global Planner
In another terminal, send the route goal to the global planner:
- **Option A: Send Single Goal via ROS 2 Action CLI**:
  ```bash
  source /opt/ros/humble/setup.bash
  source install/setup.bash
  ros2 action send_goal /waypoint waypoint_action/action/WaypointSet \
      "{absis: 5.0, ordinat: 0.0, yaw: 0.0, duration: 12.0}" --feedback
  ```
- **Option B: Run Autonomous Multi-Waypoint Sequence**:
  ```bash
  ros2 run waypoint_client waypoint_client_node
  ```
  And trigger the rectangle route by publishing the filename:
  ```bash
  ros2 topic pub --once /waypoint_filename std_msgs/msg/String "{data: 'demo_rectangle.yaml'}"
  ```

### Step 6: Monitor Execution & Diagnostics
Observe real-time telemetry, FPGA acceleration status, and motor RPS:
```bash
# Monitor controller diagnostics (5 Hz)
ros2 topic echo /igor/diagnostics

# Monitor safety gate alert status
ros2 topic echo /igor/safety_gate_alert

# Monitor real-time action feedback
ros2 topic echo /waypoint/_action/feedback
```
The execution will stream 74-D observation packets to the DE10-Nano over UDP, receive delta actions, evaluate the 0.1s safety gate, convert velocity to 4-wheel Mecanum RPS, and command the STM32 to drive the robot along the specified route.

---

## 6. Compilation & Execution Reference by Target Platform

Here is the exact checklist of source files, compile commands, and run commands required on each device:

### 6.1 Intel Cyclone V SoC DE10-Nano (FPGA + HPS Linux)

#### Files Required on DE10-Nano:
- `src/igor_pipeline/protocol/protocol_v2.h`
- `src/igor_pipeline/hps_de10/de10_shared_mem_ext.h`
- `src/igor_pipeline/hps_de10/de10_shared_mem_ext.c`
- `src/igor_pipeline/hps_de10/de10_server_daemon.c`
- `src/igor_pipeline/hps_de10/Makefile`
- `fpga/bitstreams/igor_src_policy.sof` (or compiled from `ai_accel_wrapper.v` + `igor_src_policy_core.v`)

#### Compilation on DE10-Nano (ARMv7 Linux / Native GCC):
```bash
cd ~/igor_pipeline/hps_de10
make clean && make
```
*(Produces executable binary: `de10_server_daemon`)*.

#### Running on DE10-Nano:
1. **Program FPGA Bitstream** (via Quartus Programmer / JTAG or U-Boot / devcfg):
   ```bash
   # If using Linux devcfg:
   dd if=igor_src_policy.rbf of=/dev/fpga0 bs=1M
   ```
2. **Run Server Daemon in Hardware Mode**:
   ```bash
   cd ~/igor_pipeline/hps_de10
   sudo ./de10_server_daemon --hw --port 8080
   ```
   *(Or with `--mock` if running without physical FPGA bitstream programmed)*.

---

### 6.2 NVIDIA Jetson Orin Nano (Master Robot Controller / Ubuntu 22.04 + ROS 2 Humble)

#### Files Required on Jetson Orin Nano:
- **ROS 2 Workspace Packages**:
  - `src/igor_bringup/` (`launch/bringup.launch.py`)
  - `src/igor_controller/` (`controller_node.py`, `waypoint_global_planner_node.py`, `fpga_bridge.py`, `mcu_driver.py`, `heading_estimator.py`)
  - `src/igor_navigation/` (Kinematics, Subsampler, CBF safety filters, weights)
  - `waypoint_list/waypoint_action/` (`WaypointSet.action`)
  - `waypoint_list/waypoint_client/` (`waypoint_Action_Client.py`, `point/demo_rectangle.yaml`)
- **Pipeline C++ Client & Test Tools**:
  - `src/igor_pipeline/protocol/protocol_v2.h`
  - `src/igor_pipeline/jetson_orin/jetson_client_adapter.hpp` & `.cpp`
  - `src/igor_pipeline/jetson_orin/jetson_main.cpp`
  - `src/igor_pipeline/scripts/benchmark_latency.py`
  - `test_global_planner_pipeline.py`

#### Compilation on Jetson Orin Nano:
1. **Build ROS 2 Navigation & Global Planner Packages**:
   ```bash
   cd ~/vs-code-data/Python/igor_ws
   source /opt/ros/humble/setup.bash
   
   # Build action interfaces and controller packages
   colcon build --packages-select waypoint_action
   source install/setup.bash
   colcon build --base-paths src waypoint_list --packages-select igor_navigation igor_controller igor_bringup waypoint_client
   ```
2. **Build C++ Jetson Streamer Client (Standalone verification)**:
   ```bash
   cd ~/vs-code-data/Python/igor_ws/src/igor_pipeline/jetson_orin
   mkdir -p build && cd build
   cmake .. && make
   ```
   *(Produces executable binary: `jetson_ai_streamer`)*.

#### Running on Jetson Orin Nano:
1. **Configure Ethernet Network Link**:
   ```bash
   sudo ip addr add 192.168.1.10/24 dev eth0 || true
   sudo ip link set eth0 up
   ```
2. **Run Standalone Connection Benchmark (Pre-Flight Check)**:
   ```bash
   python3 src/igor_pipeline/scripts/benchmark_latency.py 192.168.1.50 8080
   ```
3. **Launch Autonomous Robot Bringup**:
   ```bash
   source /opt/ros/humble/setup.bash
   source install/setup.bash
   ros2 launch igor_bringup bringup.launch.py \
       algorithm:=cl_drl_cbf \
       use_fpga:=true \
       fpga_port:="udp://192.168.1.50:8080" \
       mcu_port:=/dev/ttyACM0 \
       lidar_port:=/dev/lidar \
       use_mock_serial:=false \
       launch_planner:=true
   ```
4. **Trigger 3m x 5m Rectangle Demo Route**:
   ```bash
   # Terminal A: Start action client
   ros2 run waypoint_client waypoint_client_node
   
   # Terminal B: Dispatch rectangle YAML
   ros2 topic pub --once /waypoint_filename std_msgs/msg/String "{data: 'demo_rectangle.yaml'}"
   ```



<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `pipeline_plan.md`

SHA256: `895387907965e566cdd33ca1745a90344bf88107a0592eed60dc071e7e4be621`

<!-- BEGIN ORIGINAL DOCUMENT -->

# DE10-Nano & Jetson Orin Nano AI Acceleration Pipeline: Architecture, Robustness Enhancements, and Implementation Plan (`pipeline_plan.md`)

## 1. Executive Summary & Context

This document outlines the detailed architecture, robustness enhancements, and phased implementation plan for deploying the high-speed AI acceleration bridge between the **NVIDIA Jetson Orin Nano** (host/robot controller) and the **Intel Cyclone V SoC DE10-Nano FPGA** over Gigabit Ethernet (UDP port 8080) and UART fallback.

### Ground Truth vs. Legacy Discrepancies Resolved:
1. **Model Weights & Dimension Ground Truth**:
   - The reference file [`pipeline_architecture.md`](file:///home/hadynata/vs-code-data/Python/igor_ws/pipeline_architecture.md) and [`protocol_legacy.h`](file:///home/hadynata/vs-code-data/Python/igor_ws/src/igor_pipeline/protocol/protocol_legacy.h) describe generic placeholder dimensions (`512` sensor floats and `128` AI outputs).
   - **The exact technical ground truth of this project resides in `src/igor_navigation/igor_navigation/weights/` and `fpga/rtl/igor_src_policy/`**:
     * **Input Dimension**: **74 elements** ($64\text{ frontal LiDAR} + 6\text{ IMU }(a_x,a_y,a_z, \omega_x,\omega_y,\omega_z) + 3\text{ nominal twist }(v_x, v_y, \omega) + 1\text{ Course-Lock heading error } \Delta\theta$).
     * **Quantization**: Signed fixed-point **Q8.8** ($x_{\text{int}} = \text{round}(x \times 256.0)$).
     * **Output Dimension**: **3 delta actions** ($[\Delta v_x, \Delta v_y, \Delta \omega_z]$ bounded in $[-1.0, 1.0]$).
     * **FPGA Accelerator Core**: `igor_src_policy_core.v` implementing 74 $\to$ 128 (ReLU) $\to$ 64 (ReLU) $\to$ 3 (Linear clamped) MLP, with weights loaded from `policy_weights.mem` / `weights_q8_8.h`.
2. **Integration with Global Planner**:
   - The newly implemented closed-loop **`WaypointGlobalPlannerNode`** (`WaypointSet.action`) computes nominal twist $(v_x, v_y, \omega)$ and heading error $\Delta \theta$ towards the lookahead carrot.
   - The **`IgorControllerNode`** assembles the 74-D vector, applies the 25 ms freshness filter and 0.1s forward collision safety gate, and dispatches the vector to the FPGA acceleration pipeline over Gigabit Ethernet UDP port 8080.
   - This plan ensures full end-to-end synergy from global waypoint mission down to FPGA PL acceleration and STM32 4-wheel Mecanum execution.

---

## 2. Non-Destructive Code Augmentation Rules

Per Section 2 of `pipeline_architecture.md`, existing files are strictly **READ-ONLY**:
* Never overwrite or modify `src/igor_pipeline/protocol/protocol_legacy.h`, `src/igor_pipeline/hps_de10/de10_server_legacy.c`, `src/igor_pipeline/hps_de10/de10_driver_legacy.h`, or `src/igor_pipeline/jetson_orin/jetson_client_legacy.cpp`.
* Augment functionality exclusively by creating new files:
  - `src/igor_pipeline/protocol/protocol_v2.h`
  - `src/igor_pipeline/hps_de10/de10_shared_mem_ext.h` & `de10_shared_mem_ext.c`
  - `src/igor_pipeline/hps_de10/de10_server_daemon.c` & `Makefile`
  - `src/igor_pipeline/simulators/mock_de10_host_server.cpp` & `CMakeLists.txt`
  - `src/igor_pipeline/jetson_orin/jetson_client_adapter.cpp`, `jetson_main.cpp`, & `CMakeLists.txt`
  - `src/igor_pipeline/fpga_pl/ai_accel_wrapper.v`
  - `src/igor_pipeline/scripts/test_local_loopback.sh`, `setup_network_hardware.sh`, `benchmark_latency.py`

---

## 3. High-Level Architecture & End-to-End Pipeline

```
+---------------------------------------------------------------------------------------------------------+
|                                        JETSON ORIN NANO (HOST)                                          |
|                                                                                                         |
|  +------------------------------+     /cmd_vel_in     +-----------------------------------------------+ |
|  | WaypointGlobalPlannerNode    | ------------------> | IgorControllerNode                            | |
|  | (WaypointSet Action Server)  |   (Carrot Twist)    | - Sensor Freshness Gate (< 25 ms)             | |
|  +------------------------------+                     | - 74-D Vector Assembler (LiDAR+IMU+Twist+Err) | |
|                                                       | - Jetson Predictive Safety Gate (0.1s horizon)| |
|  +------------------------------+                     | - Emergency Backoff Recovery FSM              | |
|  | jetson_client_adapter.cpp    | <------------------ | - Dynamic Speed Limits & Watchdog             | |
|  | (UDP Streamer Client)        |  (Raw 74-D Vector)  +-----------------------------------------------+ |
|  +------------------------------+                                                                       |
+---------------------------------|-----------------------------------------------------------------------+
                                  |
                                  | Gigabit Ethernet UDP (Port 8080)
                                  | Payload: SensorPacketV2 (74 float / Q8.8, Magic, CRC32, Frame ID)
                                  v
+---------------------------------------------------------------------------------------------------------+
|                                    INTEL DE10-NANO CYCLONE V SOC (FPGA)                                 |
|                                                                                                         |
|  [HPS - Hard Processor System (ARM Cortex-A9)]                                                         |
|  +---------------------------------------------------------------------------------------------------+  |
|  | de10_server_daemon.c                                                                              |  |
|  | Dual-Mode:                                                                                        |  |
|  |   --mock : Software emulation (evaluates Q8.8 MLP or reactive obstacle braking)                   |  |
|  |   --hw   : Hardware mode (maps /dev/mem lwHPS2FPGA 0xFF200000 & Shared SDRAM 0x20000000)          |  |
|  +---------------------------------------------------------------------------------------------------+  |
|                                     |                        ^                                          |
|                         Shared SDRAM|0x20000000   Status/Done|lwHPS2FPGA 0xFF200000                     |
|                                     v                        |                                          |
|  [FPGA PL - Programmable Logic (Cyclone V)]                  |                                          |
|  +-----------------------------------------------------------|---------------------------------------+  |
|  | ai_accel_wrapper.v (Avalon-MM Slave / DMA Master)         |                                       |  |
|  |        |                                                  |                                       |  |
|  |        v                                                  |                                       |  |
|  | igor_src_policy_core.v                                    |                                       |  |
|  | (74 -> 128 -> 64 -> 3 MLP Neural Accelerator Core)        |                                       |  |
|  | ROM: policy_weights.mem (18,051 int16 parameters)         |                                       |  |
|  +---------------------------------------------------------------------------------------------------+  |
+---------------------------------|-----------------------------------------------------------------------+
                                  |
                                  | Response: InferenceResponsePacketV2 (3 delta actions, Latency, CRC32)
                                  v
+---------------------------------------------------------------------------------------------------------+
|                                       JETSON LOW-LEVEL ACTUATION                                        |
|  +---------------------------------------------------------------------------------------------------+  |
|  | - Jetson Safety Gate Verification (0.1s collision check)                                          |  |
|  | - Blended Gated Residual Twist: v_exec = v_cmd + alpha * delta_v                                  |  |
|  | - 4-Wheel Mecanum Inverse Kinematics (Right-side sign mirror: M1, M2, -M3, -M4)                   |  |
|  | - Serial UART transmission to STM32 @ 1 Mbps (Func 0x03)                                          |  |
+---------------------------------------------------------------------------------------------------------+
```

---

## 4. Robustness Enhancements for the Pipeline

The legacy mockup in `pipeline_architecture.md` was a minimal proof-of-concept. To make this pipeline production-ready and highly reliable on physical hardware, we propose five key robustness improvements:

### 1. Dual-Format Protocol Compatibility (`protocol_v2.h`)
- **Problem in Legacy**: `protocol_legacy.h` allocates a rigid `float sensor_data[512]` (2KB packet) and `float ai_results[128]`, whereas our real model uses exactly **74 inputs** and **3 outputs**. Transmitting 512 floats wastes 85% of network bandwidth and causes unnecessary packet fragmentation.
- **Robustness Enhancement**:
  - `protocol_v2.h` defines a compact, bit-aligned packet struct:
    * `MAGIC_NUMBER`: `0x49474F52` ("IGOR") header identifier.
    * `frame_id`: Sequential 32-bit counter.
    * `timestamp_ns`: 64-bit nanosecond timestamp for precise Round-Trip Time (RTT) profiling.
    * `status_code`: Bitfield for status/errors (e.g. `STATUS_OK`, `STATUS_STALE_DROPPED`, `STATUS_SAFETY_ACTIVE`).
    * `obs_dimension`: `74` (explicit verification).
    * `sensor_data[74]`: Exact 74 floats (or packed int16 Q8.8 option).
    * `nominal_twist[3]`: Commanded $v_x, v_y, \omega$.
    * `crc32`: Hardware-friendly polynomial checksum guaranteeing 100% bit integrity over Gigabit Ethernet.
  - Retain backwards-compatibility macros so legacy tools can still inspect frames if needed.

### 2. Dual-Engine Acceleration HAL (`de10_shared_mem_ext.c`)
- **Problem in Legacy**: Direct `/dev/mem` access crashes with `SIGSEGV` or segmentation faults when executed on PCs or Jetson without Cyclone V hardware.
- **Robustness Enhancement**:
  - Implement a clean Hardware Abstraction Layer (HAL):
    * `hal_init(int mode)`: Detects if running on Cyclone V HPS (`/dev/mem` with physical address mapping `0xFF200000` and `0x20000000`). If hardware mapping fails or `--mock` is specified, it gracefully allocates aligned virtual heap memory and enables the software neural simulator.
    * `hal_write_reg()`, `hal_read_reg()`, `hal_get_shared_buffer()`: Abstracted macros preventing unaligned bus faults.
    * `hal_cleanup()`: Ensures clean unmapping and memory release on `SIGINT` / `SIGTERM`.

### 3. Asynchronous Non-Blocking HPS Server Daemon (`de10_server_daemon.c`)
- **Problem in Legacy**: `de10_server_legacy.c` has a blocking `while((*soc.accel_status & 0x01) == 0)` loop without a watchdog or timeout. If the FPGA PL hangs or an interrupt is missed, the entire HPS server deadlocks forever.
- **Robustness Enhancement**:
  - Introduce an execution watchdog timeout (e.g. 10,000 cycles / ~1 ms).
  - If the done bit fails to assert within the deadline, log an error flag (`STATUS_PL_TIMEOUT`), issue an accelerator soft-reset pulse (`*accel_ctrl = 0x02`), and return a safe zero-action packet to the Jetson rather than hanging.

### 4. Zero-Copy Shared Ring Buffer Architecture
- **Problem in Legacy**: Single input and output buffer in DDR SDRAM can cause race conditions if the Jetson transmits faster than the PL execution cycle.
- **Robustness Enhancement**:
  - Implement a ping-pong (double buffer) scheme in the 16 MB shared SDRAM space:
    * Bank 0: `0x20000000` (Input Ping) / `0x20400000` (Output Ping)
    * Bank 1: `0x20800000` (Input Pong) / `0x20C00000` (Output Pong)
  - Alternating buffers allows DMA burst transfers to occur concurrently with UDP network packet reception.

### 5. Automated Latency Benchmark & Network Profiler (`benchmark_latency.py`)
- High-resolution RTT monitoring with rolling metrics:
  - Median RTT, 99th percentile (p99) tail latency, packet jitter, and packet loss rate.
  - Automatically flags if RTT exceeds the 25 ms sensor freshness deadline.

---

## 5. Detailed Modular Implementation Plan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE IMPLEMENTATION ROADMAP                   │
├───────────┬──────────────────────────────────┬──────────────────────────────┤
│ Module ID │ Target Scope                     │ Key Deliverables             │
├───────────┼──────────────────────────────────┼──────────────────────────────┤
│ Module 01 │ Protocol Layer (Shared)          │ protocol/protocol_v2.h       │
│ Module 02 │ DE10 HAL & Shared Memory Driver  │ hps_de10/de10_shared_mem_ext │
│ Module 03 │ Standalone Host DE10 Simulator   │ simulators/mock_de10_server  │
│ Module 04 │ DE10-Nano Dual-Mode HPS Daemon   │ hps_de10/de10_server_daemon  │
│ Module 05 │ Jetson Orin Client Streamer Node │ jetson_orin/jetson_client_*  │
│ Module 06 │ Cyclone V Avalon-MM PL Wrapper   │ fpga_pl/ai_accel_wrapper.v   │
│ Module 07 │ Integration Test & Benchmarking  │ scripts/test_local_loopback  │
└───────────┴──────────────────────────────────┴──────────────────────────────┘
```

### Module 01: Extended Binary Protocol (`src/igor_pipeline/protocol/protocol_v2.h`)
- **Header**: `#pragma pack(push, 1)` binary packing.
- **`SensorPacketV2`**:
  - `uint32_t magic` (0x49474F52)
  - `uint32_t frame_id`
  - `uint64_t timestamp_ns`
  - `float linear_velocity[3]` (nominal $v_x, v_y, v_z$)
  - `float angular_velocity[3]` (nominal $\omega_x, \omega_y, \omega_z$)
  - `uint32_t sensor_data_len` (fixed to 74 for Igor model)
  - `float sensor_data[74]` (64 LiDAR, 6 IMU, 3 Twist, 1 Heading Error)
  - `int16_t q8_8_data[74]` (Pre-quantized fixed-point array for direct FPGA DMA ingestion)
  - `uint32_t crc32`
- **`InferenceResponsePacketV2`**:
  - `uint32_t magic` (0x49474F52)
  - `uint32_t frame_id`
  - `uint64_t timestamp_ns`
  - `uint32_t status_code` (OK, TIMEOUT, CRC_ERR, SAFETY_OVERRIDE)
  - `uint32_t num_outputs` (3 for Igor model: $[\Delta v_x, \Delta v_y, \Delta \omega_z]$)
  - `float ai_results[3]` (FP32 delta actions)
  - `int16_t q8_8_results[3]` (Raw Q8.8 outputs directly from PL)
  - `uint32_t execution_cycles` (PL latency counter)
  - `uint32_t crc32`
- **Helper functions**:
  - `uint32_t calculate_crc32(const uint8_t *data, size_t len)`
  - `int validate_sensor_packet(const SensorPacketV2 *p)`
  - `int validate_response_packet(const InferenceResponsePacketV2 *p)`

### Module 02: DE10 Memory Driver & Hardware Abstraction Layer
- **Files**: `src/igor_pipeline/hps_de10/de10_shared_mem_ext.h` & `de10_shared_mem_ext.c`
- **Functions**:
  - `int hal_init(SoC_HAL_Context *ctx, int is_mock)`:
    - If `is_mock == 0`: maps `/dev/mem` for `0xFF200000` (LWHPS2FPGA, span 2MB) and `0x20000000` (SDRAM, span 16MB).
    - If `is_mock == 1`: allocates virtual memory buffers using `posix_memalign` (cache-line aligned).
  - `void hal_write_reg(SoC_HAL_Context *ctx, uint32_t reg_offset, uint32_t value)`
  - `uint32_t hal_read_reg(SoC_HAL_Context *ctx, uint32_t reg_offset)`
  - `void* hal_get_in_buffer(SoC_HAL_Context *ctx, int bank)`
  - `void* hal_get_out_buffer(SoC_HAL_Context *ctx, int bank)`
  - `void hal_cleanup(SoC_HAL_Context *ctx)`

### Module 03: Standalone Host DE10 Simulator
- **File**: `src/igor_pipeline/simulators/mock_de10_host_server.cpp`
- **Features**:
  - Runs on any standard Linux x86_64 / ARM64 machine without FPGA hardware or root privileges.
  - Binds to UDP port 8080.
  - Ingests `SensorPacketV2`, validates CRC32.
  - Implements bit-exact software execution of the 74-128-64-3 Q8.8 neural network (using weights matching `src/igor_navigation/igor_navigation/weights/model_weights.json`).
  - Simulates FPGA PL latency (~16 ms or configurable 500 $\mu$s delay).
  - Returns `InferenceResponsePacketV2`.
  - Includes a standalone `CMakeLists.txt`.

### Module 04: DE10-Nano Dual-Mode HPS Server Daemon
- **Files**: `src/igor_pipeline/hps_de10/de10_server_daemon.c` & `Makefile`
- **Features**:
  - CLI flags: `--mock` (software emulation on HPS CPU) and `--hw` (production PL access).
  - High-performance UDP socket with `SO_REUSEADDR`, `SO_RCVBUF` / `SO_SNDBUF` tuning.
  - Double-buffering memory ping-pong.
  - PL completion polling with 2 ms timeout guard.
  - Production Makefile targeting ARM Cortex-A9 (`arm-linux-gnueabihf-gcc` / native gcc).

### Module 05: Jetson Orin Client Streamer & ROS 2 Adapter
- **Files**:
  - `src/igor_pipeline/jetson_orin/jetson_client_adapter.hpp` & `.cpp`
  - `src/igor_pipeline/jetson_orin/jetson_main.cpp`
  - `src/igor_pipeline/jetson_orin/CMakeLists.txt`
- **Features**:
  - CLI options: `--target <ip>` (default: `127.0.0.1` for mock, `192.168.1.50` for hardware), `--port <port>` (8080).
  - 30 ms socket timeout matching our sensor freshness threshold.
  - Calculates rolling RTT, jitter, packet loss rate.
  - Seamless C++ API exposed for ROS 2 nodes (`infer_async(const float obs[74], float actions[3])`).

### Module 06: Cyclone V Avalon-MM FPGA PL Wrapper
- **File**: `src/igor_pipeline/fpga_pl/ai_accel_wrapper.v`
- **Features**:
  - Avalon-MM Slave control interface (`Control`, `InPtr`, `OutPtr`, `Length`, `Status`).
  - Connects to existing `igor_src_policy_core.v` (the 74-128-64-3 quantized MLP core).
  - Reads 74 Q8.8 inputs sequentially or via parallel bus from DDR, pulses `start`, monitors `done`, and writes 3 Q8.8 action outputs back to DDR.
  - Generates done interrupt for HPS.

### Module 07: Testing Scripts & Benchmarking Pipeline
- **Files**:
  - `src/igor_pipeline/scripts/test_local_loopback.sh`: Builds and runs Stage 1 (Jetson Client + Mock Server on `127.0.0.1`), verifying bit-level serialization and RTT latency.
  - `src/igor_pipeline/scripts/setup_network_hardware.sh`: Configures network interface (`eth0`, IP `192.168.1.10/24`, MTU 1500/9000).
  - `src/igor_pipeline/scripts/benchmark_latency.py`: Executes automated statistical latency profiling, generating CSV logs and validation reports.

---

## 6. Verification Criteria & Acceptance Metrics

| Verification Stage | Metric Target | Acceptance Condition |
|---|---|---|
| **Protocol Serialization** | Zero CRC mismatches | 100,000 packets transmitted with 0 corrupted bytes. |
| **Observation Integrity** | 74 inputs bit-exact | Sensor indices 0..63 (LiDAR), 64..69 (IMU), 70..72 (Twist), 73 (Heading) conform to Q8.8. |
| **Output Integrity** | 3 actions in $[-1, 1]$ | Delta actions $[\Delta v_x, \Delta v_y, \Delta \omega_z]$ correctly scaled and verified. |
| **Stage 1 (Local Loopback)** | RTT Latency $< 250\ \mu\text{s}$ | Throughput $> 1,000\text{ Hz}$ on `127.0.0.1` with 0 dropped frames. |
| **Stage 2 (Network Mock)** | RTT Latency $< 1\text{ ms}$ | Stable communication between Jetson and DE10-Nano over Gigabit Ethernet. |
| **Stage 3 (FPGA Hardware)** | Latency $\approx 16\text{ ms}$ | Full inference loop cleanly completes within the 25 ms sensor freshness deadline. |
| **Global Planner Synergy** | End-to-End Success | `WaypointGlobalPlannerNode` goals progress smoothly with FPGA acceleration enabled. |


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `test.md`

SHA256: `d15e6fe05267d7e44cd9a5b23847bce7f0fce3fb561e9f44bb084b80a8f3692f`

<!-- BEGIN ORIGINAL DOCUMENT -->

# Physical UART and Ethernet tests

Use [eth_direction.md](eth_direction.md) for the current architecture and
[docs/connect_de10.md](docs/connect_de10.md) for connection automation.
The former version of this guide described a UART-aware HPS daemon that was
never implemented, used incorrect packet sizes, and supplied obsolete flags.

The production route is Jetson UDP → DE10 HPS Linux gateway → HPS-local
USB-UART adapter → FPGA Parallel8 core → reply along the same route.
The observation is 74 prepared sensor/command features, not raw LiDAR packets.
Jetson retains sensor processing, action filtering, and motor commands.

1. Check Jetson: `python3 tools/connect_de10.py --check-only`.
2. Check HPS boots through its USB-UART console. Configure HPS Ethernet
   `192.168.50.2/24`; Jetson uses `192.168.50.1/24`.
3. Run `python3 tools/connect_de10.py --user ACTUAL_HPS_USER` for network-only
   verification. This does not prove FPGA inference.
4. Program the intended image; release KEY1 and press/release KEY0. Connect
   the HPS-local adapter TX → JP1 pin 1, RX → JP1 pin 2, GND → JP1 pin 12.
   Use 3.3 V TTL signals; leave adapter VCC disconnected.
5. On HPS, test the fabric link before starting the gateway:

```bash
python3 src/igor_pipeline/scripts/uart_test.py --port /dev/serial/by-id/ACTUAL_ADAPTER --baud 9600 --iter 3
```

For the 9600 image, expect raw Q8.8 `[-46, 60, 34]` and three validated replies.
For the Parallel8 921600 image, use `--baud 921600` instead. The UART request
is 153 bytes; its reply is 11 bytes. UART does not use UDP Protocol V2 structs.

6. Stop the network-only gateway, then from Jetson run:

```bash
python3 tools/connect_de10.py --user ACTUAL_HPS_USER --hardware --baud 921600 --fpga-serial /dev/serial/by-id/ACTUAL_HPS_ADAPTER
```

The adapter path is on HPS, not Jetson. Only select 921600 after loading its
matching image. The 9600 profile takes at least 171 ms per transaction and
cannot support the intended 50 Hz control loop.

For fixed/matrix inference acceptance, fault injection, logs, and ROS launch,
follow sections 6–7 of [eth_direction.md](eth_direction.md). UDP Protocol V2
uses exactly 492-byte requests and 50-byte replies. A mock status is rejected
by production clients; a timeout must stop all four motor setpoints.

Software regression:

```bash
python3 -m unittest discover -s test -p test_ethernet.py
python3 -m unittest discover -s test -p test_connect_de10.py
python3 -m unittest discover -s test -p 'test_uart*.py'
python3 fpga/verification/run_host_regression.py
```

Localhost Ethernet tests need socket permissions. These tests use fixtures;
they do not establish physical FPGA or motor acceptance.


<!-- END ORIGINAL DOCUMENT -->


---

## SOURCE: `to-do.md`

SHA256: `7907bfbd40c1b3ff1136f207ba08d7300dc798bb254b866b6da95f5c7bcce198`

<!-- BEGIN ORIGINAL DOCUMENT -->

# To-Do List for FPGA-Jetson Integration and Demo

## High-Priority Tasks (Critical for Demo)
1. **Correct UART Baud Rate Mismatch**
   - Ensure `fpga_baudrate` parameter is declared and set to `921600` in `bringup.launch.py`.
   - Update `controller_node.py` to use this parameter when instantiating `FPGABridge`.
2. **Wire FPGA UART to Jetson**
   - Verify physical connections: TX/RX pins from DE10‑Nano to Jetson UART header.
   - Confirm voltage level shifting (3.3 V) and ground continuity.
3. **Validate FPGA Bitstream**
   - Build and load the latest `igor_src_policy.sof` bitstream.
   - Run `fpga/scripts/freeze_release.py` to update manifest hashes.
4. **Synchronize Codebases**
   - Mirror changes from `ros2_ws/src/` to `fpga/software_integration/src/`.
   - Run CI verification (`run_host_regression.py`) to ensure no drift.
5. **Implement Demo Waypoint Sequence**
   - Add a simple rectangle waypoint planner (5 m × 3 m) in `global_planner`.
   - Ensure the planner publishes a `Path` that the controller consumes.

## Medium-Priority Tasks (Stability & Clean‑up)
- Register controller alias `cl_drl_dwa_shield`.
- Enable LiDAR obstacle extraction for CBF safety filter.
- Standardize IMU normalization (use 9.81 m/s² for accel Z, rad/s for gyro).
- Replace independent wheel clipping with proportional desaturation.
- Automate weight export to `policy_weights.mem` after retraining.

## Low-Priority Tasks (Documentation & Misc)
- Update `global_planner_docs.md` with demo instructions.
- Add compile/run instructions for Jetson Orin Nano and DE10‑Nano.
- Clean broken links and metadata in repository.
- Provide wiring diagrams and pin mappings in `fpga/docs/CONNECTOR.md`.

*All tasks should be completed before the live demonstration. Prioritize items marked **High-Priority**.*

<!-- END ORIGINAL DOCUMENT -->
