#!/usr/bin/env python3
"""GARDA UART command-line client (laptop or Jetson Nano).

Jetson Nano (J41 header, /dev/ttyTHS1, 3.3 V):
    J41 pin 8  (UART TXD) -> DE10-Lite JP1 pin 3  (port B RX)
    J41 pin 10 (UART RXD) <- DE10-Lite JP1 pin 4  (port B TX)
    J41 pin 6  (GND)      -- DE10-Lite JP1 pin 30 (GND)
    sudo usermod -aG dialout $USER   # once, then log in again
    pip3 install pyserial

Examples:
    python3 garda_cli.py --port /dev/ttyTHS1 ident
    python3 garda_cli.py --port /dev/ttyTHS1 status
    python3 garda_cli.py --port /dev/ttyTHS1 estop
    python3 garda_cli.py --port /dev/ttyTHS1 monitor            # STATUS once per second
    python3 garda_cli.py --port /dev/ttyTHS1 nn-test            # 3 golden neural vectors
Every line printed comes from a CRC-checked FPGA response; on a timeout the
command fails with a non-zero exit code (nothing is assumed).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garda_protocol as p  # noqa: E402
from garda_link import GardaLink, describe  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "assets/neural_24_64_64_4"


def show(op, value):
    print(json.dumps({"op": p.OP_NAMES.get(op, hex(op)), "value": f"0x{value:08X}", **describe(op, value)}))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="/dev/ttyTHS1 (Jetson J41), /dev/ttyUSB0, COM5 ...")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("action", choices=["ident", "status", "ext", "estop", "safe-reset", "ports", "capture", "monitor", "nn-test"])
    a = ap.parse_args()
    lk = GardaLink()
    r = lk.connect(a.port, a.baud)
    if not r["ok"]:
        print(r["error"], file=sys.stderr)
        return 2
    try:
        if a.action == "ident":
            print(json.dumps(lk.identify()))
            info = p.decode_port_info(lk.transact(p.OP_PORT_INFO).value)
            print(json.dumps(info))
        elif a.action in ("status", "ext", "ports", "capture", "estop"):
            op = {"status": p.OP_STATUS, "ext": p.OP_EXT_STATUS, "ports": p.OP_PORT_STATS,
                  "capture": p.OP_ESTOP_CAPTURE, "estop": p.OP_HOST_ESTOP}[a.action]
            show(op, lk.transact(op).value)
            if a.action == "estop":
                show(p.OP_STATUS, lk.transact(p.OP_STATUS).value)
        elif a.action == "safe-reset":
            try:
                lk.transact(p.OP_SAFE_RESET, p.SAFE_RESET_MAGIC)
            except p.ProtocolError:
                pass       # a latched protocol fault suppresses the reply; the reset still happens
            time.sleep(0.05)
            show(p.OP_STATUS, lk.transact(p.OP_STATUS).value)
        elif a.action == "monitor":
            while True:
                show(p.OP_STATUS, lk.transact(p.OP_STATUS).value)
                time.sleep(1)
        elif a.action == "nn-test":
            ins, gold = p.read_mem(ASSETS / "test_inputs.mem"), p.read_mem(ASSETS / "test_outputs.mem")
            for n in range(3):
                for i, x in enumerate(ins[n * 24:n * 24 + 24]):
                    lk.transact(p.OP_NN_LOAD, i | (x << 8))
                lk.transact(p.OP_NN_START)
                time.sleep(0.01)
                got = [lk.transact(p.OP_NN_READ, i).value & 0xFFFF for i in range(4)]
                ok = got == gold[n * 4:n * 4 + 4]
                print(f"vector {n}: {'PASS' if ok else 'FAIL'} outputs {[p.signed(g, 16) / 256 for g in got]}")
                if not ok:
                    return 1
    except p.ProtocolError as e:
        print(f"NO VALID FPGA RESPONSE: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    finally:
        lk.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
