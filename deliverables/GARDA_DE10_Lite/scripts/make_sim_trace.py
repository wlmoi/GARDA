#!/usr/bin/env python3
"""Convert sim/build/board_trace.jsonl (tb_board.v) into dashboard/data/simulation_trace.json.

The result is labelled SOFTWARE SIMULATION: every frame was produced by the
Icarus Verilog RTL model of garda_de10_lite_top, NOT by an FPGA.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
import garda_protocol as p  # noqa: E402
from garda_link import describe  # noqa: E402

STEP_OF = [  # tb step-name prefix -> Control Center step id
    ("identify", "identify"), ("link_info", "identify"), ("build_id", "identify"), ("status", "identify"),
    ("nn_", "neural"), ("config", "planner"), ("map_", "planner"), ("estop_test_arm", "planner"), ("run", "planner"),
    ("status_after_run", "planner"), ("read_command", "planner"), ("status_after_estop", "safety_gate"),
    ("estop_capture", "safety_gate"), ("corrupt_crc", "crc_test"), ("status_while_faulted", "crc_test"),
    ("safe_reset", "safe_reset"), ("status_after_safe_reset", "safe_reset"), ("ext_status_after_reset", "safe_reset"),
    ("host_estop", "estop"), ("estop_capture_key", "estop"), ("ext_status_key1", "estop"), ("ext_status", "estop"),
    ("watchdog", "watchdog"), ("status_after_silence", "watchdog"), ("ext_status_wd", "watchdog"),
    ("ident_bad", "summary"), ("status_after_bad", "summary"), ("status_still", "summary"), ("counters", "summary"),
]


def response_frame(op: int, value: int) -> bytes:
    body = bytes([p.RSP_HEAD, op]) + value.to_bytes(4, "little")
    return body + bytes([p.crc8(body), p.RSP_TAIL])


def step_of(name: str) -> str:
    best = max((k for k, _ in STEP_OF if name.startswith(k)), key=len, default=None)
    return dict(STEP_OF)[best] if best else "summary"


def main():
    src = ROOT / "sim/build/board_trace.jsonl"
    log = (ROOT / "sim/build/board.log").read_text(errors="replace")
    frames, collapsed = [], None
    for line in src.read_text().splitlines():
        e = json.loads(line)
        step = step_of(e["step"])
        if e["step"] in ("map_write", "nn_load_input"):
            if collapsed and collapsed["step_name"] == e["step"]:
                collapsed["count"] += 1
                collapsed["t_ns_end"] = e["t_ns"]
                continue
            collapsed = None
        f = {"t_ns": e["t_ns"], "step": step, "step_name": e["step"], "op": e["op"],
             "op_name": p.OP_NAMES.get(e["op"], f"0x{e['op']:02x}"), "payload": e["payload"],
             "tx": p.encode_request(e["op"], e["payload"]).hex(" ") if not e["corrupt"] else "(CRC corrupted on purpose)",
             "result": {"ok": "OK", "timeout": "TIMEOUT", "bad_frame": "FRAME_ERROR"}[e["result"]],
             "value": e["response"] if e["result"] == "ok" else None,
             "rx": response_frame(e["op"], e["response"]).hex(" ") if e["result"] == "ok" else "",
             "decoded": describe(e["op"], e["response"]) if e["result"] == "ok" else None,
             "motor_enable": e["motor_enable"], "fault": e["fault"], "host_estop": e["host_estop"],
             "watchdog_trip": e["watchdog_trip"], "ledr": e["ledr"]}
        if e["step"] in ("map_write", "nn_load_input"):
            f["count"] = 1
            collapsed = f
        frames.append(f)
    checks = re.findall(r"^(ok|FAIL)\s+(.*)$", log, re.M)
    verdict = re.search(r"BOARD checks=(\d+) failures=(\d+)", log)
    try:
        iv = subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stdout.splitlines()[0]
    except OSError:
        iv = "Icarus Verilog"
    out = {"provenance": "SOFTWARE SIMULATION",
           "source": "Icarus Verilog RTL simulation of garda_de10_lite_top (sim/tb_board.v), UART divisor 8",
           "simulator": iv, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "result": "PASS" if verdict and verdict.group(2) == "0" else "FAIL",
           "checks_total": int(verdict.group(1)) if verdict else len(checks),
           "checks": [{"ok": a == "ok", "text": b} for a, b in checks], "frames": frames}
    dst = ROOT / "dashboard/data/simulation_trace.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=1))
    print(f"wrote {dst}: {len(frames)} frames, {len(checks)} checks, result {out['result']}")


if __name__ == "__main__":
    main()
