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
