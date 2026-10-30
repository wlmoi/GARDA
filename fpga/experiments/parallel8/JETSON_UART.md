# Jetson Orin Nano to Parallel8 FPGA over UART

The existing Parallel8 bitstream receives observations on UART_RX, runs the
74 -> 128 -> 64 -> 3 neural policy using weights stored in FPGA ROM, and
returns three residual values on UART_TX. No HPS program or runtime weight
upload is required. The Jetson must produce the observations and send the
binary protocol below; this is a request/response interface.

## Wiring

For the NVIDIA Orin Nano developer kit 40-pin J12 header:

| Jetson | DE10-Nano FPGA header JP1 |
| --- | --- |
| Pin 8, UART TX | Pin 1, UART_RX, FPGA ball V12 |
| Pin 10, UART RX | Pin 2, UART_TX, FPGA ball E8 |
| Pin 6, GND | Pin 12 or 30, GND |

Use 3.3 V TTL signals and a common ground. Power each board normally; do not
connect the headers' power pins. These FPGA pins are separate from the
DE10-Nano HPS USB serial console. Custom Jetson carrier boards can differ.
Check header orientation against the board manuals before wiring.

NVIDIA reference:
https://developer.nvidia.com/downloads/assets/embedded/secure/jetson/orin_nano/docs/jetson_orin_nano_devkit_carrier_board_specification_sp.pdf

## FPGA and serial setup

1. Configure the FPGA with `fpga/bitstreams/igor_src_policy_parallel8.sof`
   through JTAG, or load the corresponding `.rbf` using a compatible FPGA
   configuration loader. Creating an RBF alone does not configure the board
   or make configuration persistent after power loss.
2. Keep KEY1 released. Press and release KEY0 once after configuration to
   initialize/reset the design. KEY1 latches an inhibit until KEY0 reset.
3. Enable the Jetson header UART and ensure no console/service owns it.
   On JetPack 6 the header UART is commonly `/dev/ttyTHS1`; verify the device
   for the installed JetPack and carrier rather than assuming its name.
4. Use 921600 baud, 8 data bits, no parity, one stop bit, no RTS/CTS.

## Binary protocol

Send one complete request, receive and validate its response, then send the
next request. Sending while inference or response transmission is busy is
rejected. Do not stream ASCII, JSON, float32 bytes, or overlapping requests.

Request (153 bytes):

```text
5A A5 01 94 [74 signed int16 values, little endian] [CRC8]
```

Inputs are Q8.8: encode a normalized scalar as `round(value * 256)`.
Inputs 0..63 must be in [0, 1]; inputs 64..73 must be in [-1, 1].
Use the observation ordering produced by the navigation software.

Response (11 bytes):

```text
5A A5 02 06 [3 signed int16 values, little endian] [CRC8]
```

Decode each result by dividing by 256. Results are clipped to [-1, 1].
CRC is CRC-8/MAXIM, initial value 0, reflected polynomial 0x8C, no final
XOR, covering command, length and payload (excluding 5A A5 and the CRC byte).
Invalid packets or an active inhibit produce no successful response.

The existing host implementation is
`fpga/software_integration/src/igor_controller/igor_controller/fpga_bridge.py`.
Use `FPGABridge(port="/dev/ttyTHS1", baudrate=921600, mock=False)` and
`infer(observation_74)` to encode, transmit, validate and decode an exchange.
It requires NumPy and pyserial. On a communication fault it latches failure;
reset the FPGA and restart the bridge before retrying.

For the integrated ROS workspace, after building and sourcing it:

```bash
ros2 launch igor_bringup bringup.launch.py algorithm:=cl_drl_cbf use_fpga:=true fpga_port:=/dev/ttyTHS1 fpga_baudrate:=921600
```

The three results are neural residuals, not wheel commands. Host blending,
filtering and kinematics remain in the navigation/controller software.
RTL simulation does not establish that the physical link has been tested.
