"""Verify the actual DE10-Nano source-policy wrapper, without physical hardware."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from run_safety_regression import executable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/current_board_wrapper"
PROJECT = ROOT / "fpga_de10_nano/src_policy"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vector_root = ROOT / "verification/src_policy/artifacts"
    for name in ["observations.hex", "expected.hex", "model_provenance.json"]:
        if not (vector_root / name).is_file():
            raise RuntimeError("Generate independently checked policy vectors first: python verification/src_policy/run.py --check")
    sources = [PROJECT / "igor_src_policy_de10_nano.v", ROOT / "rtl/igor_uart_rx.v", ROOT / "rtl/igor_uart_tx.v"]
    sources += sorted((ROOT / "rtl/igor_src_policy").glob("*.v"))
    sources += [ROOT / "verification/tb_board_wrapper.sv"]
    commands = [[executable("iverilog"), "-g2012", "-Wall", "-s", "tb_board_wrapper", "-o", str(OUT / "board.vvp")] + list(map(str, sources)), [executable("vvp"), str(OUT / "board.vvp")]]
    output = ""
    with (OUT / "simulation.log").open("w", encoding="utf-8") as log:
        for command in commands:
            completed = subprocess.run(command, cwd=PROJECT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
            log.write(completed.stdout)
            log.flush()
            output += completed.stdout
            if completed.returncode:
                raise RuntimeError(completed.stdout[-4000:])
    if "PASS board_wrapper:" not in output or "ERROR:" in output:
        raise RuntimeError("Board wrapper simulation did not pass or ROM initialization failed")
    with (OUT / "checkpoints.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    signals = ["key[1:0]", "rx", "tx", "led[7:0]", "dut.rst_n", "dut.stop_active", "dut.stop_latched", "dut.permit", "dut.a0[15:0]", "dut.a1[15:0]", "dut.a2[15:0]", "dut.error_code[7:0]", "dut.error_flags[15:0]", "dut.accepted[31:0]", "dut.rejected[31:0]"]
    (OUT / "board.gtkw").write_text('[dumpfile] "board.vcd"\n[timestart] 0\n[size] 1500 900\n@28\n' + "\n".join("tb_board_wrapper." + signal for signal in signals) + "\n", encoding="utf-8")
    provenance = sources + [ROOT / "rtl/igor_src_policy/policy_weights.mem", vector_root / "observations.hex", vector_root / "expected.hex", vector_root / "model_provenance.json", Path(__file__).resolve()]
    summary = {"status": "PASS", "generated_utc": datetime.now(timezone.utc).isoformat(), "evidence_kind": "RTL simulation of actual DE10-Nano wrapper; no physical hardware run", "hardware_tests_executed": False, "checkpoints": len(rows), "clock_hz": 50000000, "requested_baud": 921600, "divider_cycles": 54, "effective_baud": 50000000 / 54, "serial_frame_bytes": 153, "reply_bytes": 11, "expected_core_latency_cycles": 54348, "waveform": "board.vcd", "saved_view": "board.gtkw", "source_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in provenance}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["status", "checkpoints", "hardware_tests_executed", "divider_cycles"]}, indent=2))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "summary.json").write_text(json.dumps({"status": "FAIL", "error": str(error), "hardware_tests_executed": False}, indent=2) + "\n", encoding="utf-8")
        print(error, file=sys.stderr)
        raise SystemExit(1)
