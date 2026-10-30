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
