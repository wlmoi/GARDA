"""Read real IGOR FPGA safety evidence over UART into timestamped JSONL.

This is an acquisition tool, not pre-recorded hardware evidence. Requires
pyserial and a physically attached board running the matching UART bitstream.
No command is sent until --port is explicitly supplied. Fault injection is
opt-in; query-only acquisition is the default.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import time

def crc8(data):
    value = 0
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = ((value << 1) ^ (0x07 if value & 0x80 else 0)) & 0xff
    return value

def transact(port, opcode, payload=0):
    body = bytes([0xa5, opcode]) + struct.pack("<I", payload)
    port.write(body + bytes([crc8(body), 0x5a]))
    port.flush()
    raw = port.read(8)
    if len(raw) != 8 or raw[0] != 0x5a or raw[1] != opcode or raw[7] != 0xa5 or raw[6] != crc8(raw[:6]):
        raise RuntimeError(f"Invalid or absent FPGA response to opcode {opcode}: {raw.hex()}")
    return struct.unpack("<I", raw[2:6])[0], raw.hex()

def decode(status):
    return {"motor_enable": bool(status & 1), "busy": bool(status & 2), "done": bool(status & 4), "protocol_fault": bool(status & 8), "invalid_command": bool(status & 16), "fault_code": (status >> 8) & 255, "selected_index": (status >> 16) & 511}

def snapshot(port):
    before, a = transact(port, 7)
    commands, b = transact(port, 14)
    events, c = transact(port, 15)
    last, d = transact(port, 16)
    after, e = transact(port, 7)
    w = (commands >> 5) & 127
    if w & 64:
        w -= 128
    return {"utc": datetime.now(timezone.utc).isoformat(), "monotonic_ns": time.monotonic_ns(), "evidence_kind": "physical UART response", "status_before": decode(before), "status_after": decode(after), "status_unchanged": before == after, "v_command": commands & 31, "omega_command": w, "event_count": events, "last_fault": last & 255, "raw_frames": [a, b, c, d, e], "sample_atomic": False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", required=True, help="Explicit board serial port, e.g. COM5 or /dev/ttyUSB1")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--case", required=True, help="Physical fixture/test case identifier, e.g. H01_estop_held")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seconds", type=float, default=3)
    p.add_argument("--interval", type=float, default=0.05)
    p.add_argument("--bitstream", type=Path, help="Records supplied SOF SHA256; this is not a readback proof")
    p.add_argument("--expect-zero", action="store_true")
    p.add_argument("--expected-fault", type=int)
    p.add_argument("--require-enabled-baseline", action="store_true", help="Require nonzero enabled output before injection; needs a host continually refreshing safe runs")
    p.add_argument("--inject", choices=["none", "invalid-map-write", "invalid-run-payload"], default="none")
    args = p.parse_args()
    if args.seconds <= 0 or args.interval < 0:
        p.error("seconds must be positive and interval non-negative")
    try:
        import serial
    except ImportError:
        p.error("Install the optional hardware dependency: python -m pip install pyserial")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"record_type": "acquisition_metadata", "case": args.case, "port": args.port, "baud": args.baud, "utc": datetime.now(timezone.utc).isoformat(), "inject": args.inject, "evidence_kind": "physical acquisition attempt", "readback_verified": False}
    if args.bitstream:
        metadata["operator_supplied_bitstream_sha256"] = hashlib.sha256(args.bitstream.read_bytes()).hexdigest()
    checked = 0
    with args.output.open("x", encoding="utf-8") as log:
        def record(row):
            log.write(json.dumps(row, sort_keys=True) + "\n")
            log.flush()
        record(metadata)
        try:
            with serial.Serial(args.port, args.baud, timeout=0.5, write_timeout=0.5) as port:
                port.reset_input_buffer()
                baseline = snapshot(port)
                record(baseline | {"record_type": "baseline", "case": args.case})
                if args.require_enabled_baseline and (not baseline["status_unchanged"] or not baseline["status_after"]["motor_enable"] or (baseline["v_command"] == 0 and baseline["omega_command"] == 0)):
                    raise RuntimeError("Required enabled, nonzero baseline was not observed")
                if args.inject != "none":
                    opcode, payload = (2, 0) if args.inject == "invalid-map-write" else (6, 1)
                    _, raw = transact(port, opcode, payload)
                    record({"record_type": "fault_injection", "case": args.case, "utc": datetime.now(timezone.utc).isoformat(), "opcode": opcode, "payload": payload, "response": raw})
                deadline = time.monotonic() + args.seconds
                while time.monotonic() < deadline:
                    row = snapshot(port) | {"record_type": "sample", "case": args.case}
                    record(row)
                    if not row["status_unchanged"]:
                        continue
                    if args.expect_zero and (row["status_after"]["motor_enable"] or row["v_command"] or row["omega_command"]):
                        raise RuntimeError("Fail-closed hardware assertion failed")
                    if args.expected_fault is not None and (row["status_after"]["fault_code"] != args.expected_fault or row["last_fault"] != args.expected_fault):
                        raise RuntimeError("FPGA fault or retained logger cause differs from expected code")
                    checked += 1
                    time.sleep(args.interval)
                if not checked:
                    raise RuntimeError("No stable snapshots were acquired")
                record({"record_type": "result", "status": "PASS", "case": args.case, "stable_samples_checked": checked, "output_zero_checked": args.expect_zero, "expected_fault_checked": args.expected_fault})
        except Exception as error:
            record({"record_type": "result", "status": "FAIL", "case": args.case, "error": str(error), "stable_samples_checked": checked})
            raise
    print(f"PASS: {checked} real UART snapshots; evidence: {args.output}")

if __name__ == "__main__":
    main()
