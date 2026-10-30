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
