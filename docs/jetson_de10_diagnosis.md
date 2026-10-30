# Jetson → DE10 diagnosis, 2026-10-18

## Updated result after HPS console access

**Ethernet is fixed and physically tested. Direct Jetson UART inference now
passes 98/98 production-bridge checks after clearing the FPGA E-stop latch.
The Ethernet-to-fabric gateway still requires an HPS-to-fabric connection
absent from the confirmed direct wiring.**

### Final direct-UART acceptance

With Parallel8 loaded and KEY1 released, resetting only KEY0 restored the
idle pattern (LED1 on, LED3–LED7 off). The next three UART tests returned the
exact expected Q8.8 [-46,60,34], CRC-valid response
`5a a5 02 06 d2 ff 3c 00 22 00 61`.

Then the actual production FPGABridge, mock=false, ttyTHS1/921600,
passed **50 fixed + 48 varied transactions across 16 fixtures: 98/98**.
Mean RTT **4.594 ms**, max **5.920 ms**, zero over 20 ms in this sample.
These are measured end-to-end UART times, not inferred FPGA cycle counts or
a real-time scheduling guarantee. The earlier CLI byte-at-a-time reader
measured 13.329 ms mean over three transactions; the production bridge reads
the response differently.

- [Hardware acceptance capture](ethernet_validation/jetson_fpga_bridge_20261018_acceptance.jsonl)
- [Latency summary](ethernet_validation/jetson_fpga_bridge_20261018_summary.json)
- [Direct UART run instructions](direct_uart_runbook.md)

Root causes addressed: HPS DHCP-only configuration on the isolated cable;
previously incorrect UART wiring; FPGA image/baud mismatch history; and an
active/latched E-stop, which intentionally suppressed UART replies. Jetson
UART loopback verified 512 exact bytes at both 115200 and 921600.

No physical LiDAR/STM32 was visible at the last check. No motor commands
were sent. Sensor freshness, actual control-loop timing under load, physical
fault STOP and motion acceptance remain outstanding.

- Console enumerated as FT232R `0403:6001`, stable Jetson path
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_B402QWPK-if00-port0`.
- Logged into HPS as `fpga`, verified ARMv7 Cyclone V SoCFPGA identity.
  Kernel: `6.12.100-armv7-fpga`; userspace Python 3.13.5. Device-tree
  compatibility reports `terasic,de0-atlas` and `altr,socfpga-cyclone5`;
  image/BSP provenance should be checked before replacing the kernel.
- Root cause: HPS interface **end0** used DHCP on a direct link with no DHCP
  server, leaving it at `169.254.243.36/16`. Added `192.168.50.2/24`.
- Jetson → HPS ping: **3/3**, mean **0.723 ms**. HPS → Jetson: **2/2**.
- SSH works; host public key verified through the USB console and pinned in
  `/tmp/igor_hps_known_hosts` for this session.
- Deployed gateway/codec under `/home/fpga/igor_ws` on HPS.
- Physical UDP network-only test: **10/10**, mean **1.639 ms**, max **2.465 ms**.
  Capture: [jetson_hps_network_20261018.jsonl](ethernet_validation/jetson_hps_network_20261018.jsonl).
  Production client rejected status 6 as required. Temporary mock gateway
  stopped after the test; no mock production service was installed.
- Saved Jetson NetworkManager profile `enP8p1s0`: static 192.168.50.1/24,
  autoconnect=yes, ipv4.never-default=yes. Saved HPS ifupdown config
  `/etc/network/interfaces.d/end0`: static 192.168.50.2/24, no gateway;
  original backed up as `/etc/network/end0.before-igor`. `ifquery end0` passes.
  Live link remains up; reboot persistence is configured but not reboot-tested.
- Installed pyserial 3.5 offline into `/home/fpga/igor_ws/.venv`, without
  changing system Python. Use `.venv/bin/python` for HPS UART/gateway commands.
  The generic connection script currently invokes system Python; its hardware
  mode needs system pyserial or an equivalent interpreter adjustment.
- User confirms Parallel8 **921600** image. Later clarification establishes
  that UART is wired directly from Jetson GPIO to FPGA JP1; there is no
  confirmed separate HPS-local USB-UART adapter.
  HPS still sees **only usb1/root hub**, no downstream USB device or plug event.
  Its only serial ports are ttyS0 (Linux console) and ttyS1 (not a verified
  route to the fabric). Do not use the console port for AI packets.
- Running kernel config: `CONFIG_USB_DWC2_HOST=y`, but
  **`CONFIG_USB_SERIAL` and `CONFIG_USB_ACM` are disabled**. No matching driver
  modules, build/source links, or kernel headers are installed. `modprobe`
  cannot supply a driver omitted from this kernel.

### Remaining steps for FPGA inference specifically over Ethernet

1. Check the adapter is connected to DE10 micro-USB OTG through a host/OTG
   cable, with suitable power; it must enumerate as a downstream USB device.
   Obtain adapter model/VID/PID. USB enumeration must work before driver binding.
2. Install/build a **board-compatible** kernel with `CONFIG_USB_SERIAL` and
   the actual adapter driver (FTDI_SIO, CP210X, CH341, etc.), or USB_ACM for a
   CDC ACM device. Matching source/config and boot/recovery procedure are
   needed before changing this custom HPS kernel. No kernel or bootloader was
   replaced during this session.
3. Once the adapter has a tty, grant `fpga` access to its actual device group,
   verify the JP1 TX/RX/GND wiring, and run known-vector UART validation at
   **921600** using the isolated interpreter.
4. Run fixed/matrix real FPGA Ethernet inference, fault injection, latency
   acceptance, then configure the real UART gateway service. Do not substitute
   the successful network-only test for FPGA acceptance.

## Initial measurements before HPS console access

- Host: AArch64, NVIDIA Tegra kernel `5.15.148-tegra`.
- Wired interface is **enP8p1s0**, not eth0.
- Ethernet carrier is **1**, link **1000 Mb/s full duplex**, autonegotiation on.
  This establishes a physical link to a peer, not the identity or Linux readiness
  of that peer.
- Jetson already has **192.168.50.1/24**. Route to 192.168.50.2 selects
  enP8p1s0 with source 192.168.50.1. Wi-Fi retains the default route.
- Three interface-bound pings to **192.168.50.2**: 0 replies, 100% loss.
- Neighbor entry for that address: INCOMPLETE, subsequently FAILED. No other
  known IPv4 neighbor was reported on the wired interface.
- TCP/22 connection times out. One validated network-only UDP/8080 request
  also times out: Requested=1, Attempted=1, Passed=0.
- `lsusb` shows hubs, keyboards and Bluetooth, **no DE10 FT232R console**,
  USB-Blaster or external USB serial adapter. No /dev/ttyUSB*, /dev/ttyACM*,
  or /dev/serial/by-id directory is present.
- NetworkManager's current enP8p1s0 profile has autoconnect=no. The current
  address should not be assumed to survive reboot. No OS/network-manager
  settings were changed during this diagnosis.

The initial failure was peer IP/L2 reachability. It precedes the gateway and
FPGA inference protocol. Possible causes include HPS Linux not booted, a
wrong HPS IP/interface, or the cable reaching another peer. Carrier alone
cannot distinguish these. No evidence supports blaming the Jetson PHY or
solving this by forcing link speed.

## Repository corrections

- ROS bringup default UDP endpoint now matches 192.168.50.2:8080.
- Temporary network helper selects enP8p1s0 when present, otherwise a unique
  physical wired interface; defaults to 192.168.50.1/24, uses address replace,
  and reports errors instead of suppressing them. It preserves other addresses
  and routes. Shell syntax checked; live mutation was unnecessary and not run.
- Regenerated standalone tools/de10_connect.py from current source assets;
  its embedded assets had different line endings from the checked-out files,
  causing the standalone/source equivalence regression to fail.
- README and pipeline_docs now point to current Ethernet instructions.
  test.md now describes actual UART framing and gateway commands.

## Verification on the Jetson

| Check | Result |
|---|---|
| Ethernet regression, real localhost UDP + simulated UART | 16/16 pass |
| Connection automation / standalone bundle | 18/18 pass |
| UART regression fixtures | 14/14 pass |
| Host/bridge/controller fail-closed regression | 29/29 pass |
| ROS Humble launch description construction and endpoint assertion | pass |
| Network helper bash syntax and launch Python compilation | pass |
| Physical DE10 UDP transaction | timeout, not accepted |

Ethernet regression needed execution outside the sandbox because sandbox
policy denies sockets. Its initial permission errors were environment errors.
ROS launch construction used ROS_LOG_DIR under /tmp because the sandbox does
not allow writing ~/.ros. No motors were commanded, no FPGA programmed, and no
hardware inference success is claimed. Host regression refreshed its source
hash evidence in fpga/evidence/current_host/results.json.

## Required next input and hardware steps

1. Connect the DE10 **USB-UART console** connector to a Jetson USB HOST port
   using a data cable. Supply the actual HPS Linux username; enter credentials
   interactively, rather than storing passwords in the repository. Alternatively
   use its console on another PC and provide boot output and `ip -br addr`.
2. Confirm a compatible HPS Linux microSD boots. From that console inspect
   `uname -m`, `ip -br link`, and `ip -br addr`. On the actual HPS wired interface,
   configure 192.168.50.2/24 and enable its existing SSH server. Merely loading
   the neural FPGA SOF does not supply these Linux services.
3. Retry ping and `python3 tools/connect_de10.py --user ACTUAL_HPS_USER`.
   This deploys/tests a network-only gateway; it is not hardware AI acceptance.
4. For actual inference, install the **HPS-local USB-to-3.3 V TTL UART adapter**
   specified in eth_direction.md. The supplied FPGA image has UART rather than
   a native HPS bridge. A console cable is separate from this adapter.
5. Program the matching Parallel8 image, test local fabric UART, then run
   fixed and matrix Ethernet inference and fault-injection acceptance tests
   from eth_direction.md. Use 921600 for latency testing; 9600 needs at least
   171 ms per exchange and cannot meet 50 Hz.
6. Once the link works, persist the existing wired profile with static address,
   autoconnect and never-default settings, and install the edited HPS service
   only after its manual hardware test passes.
7. Before motion, attach/verify LiDAR and STM32, measure full inference latency
   against the 20 ms control period, and check sensor freshness under actual
   scan rate. The controller's 25 ms freshness threshold and documented ~10 Hz
   LiDAR rate need acceptance testing; weakening guards does not establish
   safe operation. Complete a restrained motor STOP/fault test before routes.

The implemented payload is a 74-feature observation prepared on Jetson
(64 LiDAR features, six IMU values, nominal twist, heading). Full raw scans
are not sent. AI residuals return to Jetson for filtering/kinematics and STM32
motor commands. A native Ethernet/HPS-to-fabric memory path or raw-sensor FPGA
preprocessing would require additional hardware/software implementation.

## Follow-up after connecting the USB data cable

A subsequent inventory detects **09fb:6010 Altera DE-SoC** with two
vendor-specific USB interfaces. This is the programming/JTAG connection;
there is still no serial port in pyserial or /dev/ttyUSB*. The USB-UART console
connector must also be connected to reach HPS Linux. HPS username was supplied
as `fpga`; no password is recorded in this report or repository. Reading the
kernel log through noninteractive sudo was unavailable because sudo requires
local authentication; USB descriptors and sysfs were readable without it.

Reference: [Intel DE10-Nano setup guide](https://www.intel.com/content/www/us/en/developer/articles/guide/terasic-de10-nano-get-started-guide.html)
distinguishes the UART console from the embedded USB-Blaster programming cable.

## Direct Jetson GPIO UART test after wiring correction

User clarified that FPGA UART is connected to Jetson header pins, rather than
an HPS-local USB adapter, and confirmed correcting the previously wrong wiring.
The HPS USB kernel limitations apply only to the gateway adapter approach;
they do not block this direct UART path.

- Jetson exposes ttyTHS1 at serial@3100000 and ttyTHS2 at serial@3140000.
  Existing repository diagnostics select ttyTHS1 for header UART.
- User has dialout membership; ttyTHS1 opens successfully with exclusive access.
  nvgetty and serial-getty@ttyTHS1 are disabled/inactive; no competing owner
  was reported by fuser.
- Physical test: ttyTHS1, 921600 8N1, three known vectors, one-second deadline.
  **0/3 passed; every transaction received zero bytes.** Expected output was
  raw Q8.8 [-46, 60, 34]. Capture is
  [jetson_direct_uart_20261018_run1.jsonl](ethernet_validation/jetson_direct_uart_20261018_run1.jsonl).
- Requested user release KEY1 and press/release KEY0 to clear any latched
  FPGA fault from the former wiring error, then report LED7–LED4 before retry.
- No pinmux, boot configuration, console services or FPGA image was changed.
  No motor command was sent.

If reset does not restore communication, isolate Jetson TX/RX with a temporary
header loopback **after disconnecting both FPGA signal wires**, and/or measure
TX/RX with a logic analyzer. Do not join TX to RX while both boards drive the
line. Verify common GND and JP1 physical orientation. A successful UART test
would establish direct serial AI offload; it would not establish the separate
HPS-to-fabric leg needed for Ethernet AI offload.

### Retry after confirmed FPGA reset

After user confirmed reset, repeated three known vectors at ttyTHS1/921600.
Again **0/3 passed, zero received bytes on every frame**. Capture:
[jetson_direct_uart_20261018_run2.jsonl](ethernet_validation/jetson_direct_uart_20261018_run2.jsonl).
A reset alone did not restore communication. Requested an isolated Jetson
header pin 8–10 loopback, with both FPGA signal wires disconnected, and the
FPGA LED7–LED4 pattern. No loopback transmission will be attempted before the
user confirms the isolated jumper is ready.

### Isolated Jetson UART loopback passed

After user confirmed that FPGA TX/RX were disconnected and Jetson pins 8/10
joined, ran `tools/uart_diagnose.py --port /dev/ttyTHS1 --mode loopback`.
Both **115200 and 921600 baud passed**, returning all **512 bytes exactly**;
no background RX was observed. Capture:
[jetson_loopback_20261018_run1.json](ethernet_validation/jetson_loopback_20261018_run1.json).
This validates the selected Jetson UART/header TX/RX path at both rates.
The remaining no-response fault is outside the isolated Jetson loopback path;
FPGA wiring, shared ground, reset/E-stop, loaded image and FPGA operation still
need validation. Requested removal of loopback jumper, restoration of FPGA
wiring, reset, LEDs and confirmation of programming since last power-up.

Parallel8 RTL defines LED[7:4]=error_code, LED3=stop_active,
LED2=response_valid, LED1=rst_n, LED0=permit. Quartus/JTAG CLI tools were not
found on Jetson PATH, so the running SRAM image has not been identified or
reprogrammed in this session.

### FPGA retry after successful Jetson loopback

After user confirmed FPGA reconnection, repeated known-vector testing at
921600 baud. **0/3 replies**, each zero bytes. Capture:
[jetson_direct_uart_20261018_run3.jsonl](ethernet_validation/jetson_direct_uart_20261018_run3.jsonl).
Requested actual LED0–LED7 state and confirmation of the programmed file since
last power-up, rather than another identical retry.

The checked-out `fpga/bitstreams/igor_src_policy_parallel8.sof` and experimental
SOF are **132-byte Git LFS pointers**, not programmable bitstreams. Expected
real Parallel8 object: size 6,690,394 bytes, SHA256
`cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49`.
Neither git-lfs nor Quartus/JTAG CLI is installed on this Jetson. Do not use
the pointer file in Quartus. A real bitstream and programming tool are needed
if the loaded image must be restored. No programming action was attempted.

### Reported FPGA LEDs identify active/latched E-stop

User reported LED1, LED3 and LED4 lit, and clarified the board had previously
been programmed at 9600 baud but has now been changed to Parallel8.
For the Parallel8 RTL, this pattern is reset released (LED1), stop_active
(LED3), and error_code=1 (LED4). `igor_src_policy_uart.v` assigns code 1 on
E-stop and holds its UART transmitter in reset while E-stop is active.
This explains absent replies for that reported state, assuming the loaded
image matches this RTL. The current pattern after image change still needs
confirmation.

Requested KEY1 remain fully released, followed by pressing/releasing only
KEY0. Expected idle after reset: LED1 on, LED3–LED7 off. Do not transmit another
inference request until user confirms the state. If LED3/4 remain on after
that sequence, inspect KEY1/button signal or image/pin assignment rather than
bypassing E-stop in software or RTL. No safety logic was altered.

### ROS packaging validation after hardware inference acceptance

Exposed `fpga_baudrate` (default 921600) and `fpga_timeout` (default 0.3 s)
in bringup and forwarded both to the controller. Direct UART run instructions
explicitly select ttyTHS1/921600 and a 20 ms deadline; no freshness guards changed.
Added the missing waypoint_action dependency to igor_controller/package.xml.

ROS Humble colcon build passed for waypoint_action, igor_navigation,
igor_controller and igor_bringup (4 packages, 15.5 s). Installed controller,
bridge, planner and generated action imports pass without instantiating nodes.
Installed launch `--show-args` passes. Build/install/logs are under
/tmp/igor-uart-build, /tmp/igor-uart-install and /tmp/igor-uart-build-logs.
No ROS hardware nodes or motor drivers were launched.
The 98-record physical capture was revalidated for expected integers and
16 distinct fixture cases. Diff whitespace checks pass.

## Wheel/sensor checks and requested rectangle implementation

See [JetAuto rectangle test report](jetauto_rectangle_test.md) for subsequent
physical tests and run commands. User confirmed all four individually pulsed
wheels moved in the expected order and stopped. Ten physical LiDAR scans and
550 CRC-valid IMU frames in five seconds were captured. The live
sensor→FPGA→controller pipeline now reports healthy diagnostics while commanded
zero. Both measured-pose and explicitly requested no-localization rectangle
runners are implemented. Source controller/MCU fail-closed gaps discovered
during hardware bringup were corrected and tested.

The timed 5 m first / 4 m second / four-left-turn route was requested on the
floor, but its preflight blocked it on 0.284 m close LiDAR returns. It did not
drive the route. Final STOP packets were sent. A follow-up diagnostic found
returns around +80° at 0.294 m and −121° at 0.408 m; clearance clarification
is pending. A repeat individual wheel test was requested; waiting for wheels
to be lifted again before sending nonzero wheel pulses.
