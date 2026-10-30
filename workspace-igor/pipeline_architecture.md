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