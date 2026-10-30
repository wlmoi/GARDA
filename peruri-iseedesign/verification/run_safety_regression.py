"""Reproducible fail-closed regression with Icarus; no Python packages required.

Evidence is RTL simulation. No serial hardware is touched by this script.
"""
from __future__ import annotations
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/current_safety"
SEED = 16523109
CONTROL = ["rst_n", "ready", "estop", "protective_stop", "map_ok", "cfg_ok", "result_valid", "all_done", "arithmetic_fault", "timeout"]
FIELDS = ["candidate_v", "previous_v", "max_v", "max_dv", "candidate_w", "previous_w", "max_w", "max_dw"]

def oracle(x):
    tests = [not x["rst_n"], x["estop"], x["protective_stop"], not x["ready"], not x["map_ok"], not x["cfg_ok"], x["arithmetic_fault"], x["timeout"], not x["all_done"] or not x["result_valid"], x["candidate_v"] > x["max_v"] or abs(x["candidate_w"]) > x["max_w"], abs(x["candidate_v"] - x["previous_v"]) > x["max_dv"] or abs(x["candidate_w"] - x["previous_w"]) > x["max_dw"]]
    return next((i + 1 for i, active in enumerate(tests) if active), 0)

def vectors():
    base = dict(zip(CONTROL, [1, 1, 0, 0, 1, 1, 1, 1, 0, 0]))
    base.update(candidate_v=3, previous_v=3, max_v=31, max_dv=31, candidate_w=0, previous_w=0, max_w=127, max_dw=127)
    yield base.copy()
    overrides = [{"rst_n": 0}, {"estop": 1}, {"protective_stop": 1}, {"ready": 0}, {"map_ok": 0}, {"cfg_ok": 0}, {"arithmetic_fault": 1}, {"timeout": 1}, {"all_done": 0}, {"candidate_v": 31, "max_v": 30}, {"candidate_w": -64, "max_dw": 63}]
    for update in overrides:
        yield base | update
    for bits in range(1024):
        yield base | {name: (bits >> i) & 1 for i, name in enumerate(CONTROL)}
    # Every signed angular candidate/previous pair at each reachable slew edge.
    for candidate in range(-64, 64):
        for previous in range(-64, 64):
            delta = abs(candidate - previous)
            for limit in sorted({max(0, delta - 1), delta, min(127, delta + 1)}):
                yield base | {"candidate_w": candidate, "previous_w": previous, "max_dw": limit}
    # Every unsigned velocity candidate/previous pair and all 32 limits.
    for candidate in range(32):
        for previous in range(32):
            for limit in range(32):
                yield base | {"candidate_v": candidate, "previous_v": previous, "max_dv": limit}
    # Every absolute angular speed bound, including signed minimum -64.
    for candidate in range(-64, 64):
        for limit in range(128):
            yield base | {"candidate_w": candidate, "max_w": limit}
    rng = random.Random(SEED)
    for _ in range(12000):
        x = base | {name: rng.randrange(2) for name in CONTROL}
        x.update({name: rng.randrange(-64, 64) if name in ["candidate_w", "previous_w"] else rng.randrange(128 if name in ["max_w", "max_dw"] else 32) for name in FIELDS})
        yield x

def executable(name):
    found = shutil.which(name)
    fallback = Path("C:/iverilog/bin") / f"{name}.exe"
    if found:
        return found
    if os.name == "nt" and fallback.is_file():
        return str(fallback)
    raise RuntimeError(f"Missing {name}; install Icarus Verilog and put its bin directory on PATH")

def run(command, log):
    completed = subprocess.run(command, cwd=OUT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    log.write(completed.stdout)
    log.flush()
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(map(str, command))}\n{completed.stdout[-3000:]}")
    return completed.stdout

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    counts = {str(i): 0 for i in range(12)}
    total = 0
    with (OUT / "gate_vectors.hex").open("w", encoding="ascii") as stream:
        for x in vectors():
            expected = oracle(x)
            ctrl = sum(x[name] << i for i, name in enumerate(CONTROL))
            stream.write(" ".join(f"{v:x}" for v in [ctrl] + [x[name] & (127 if "_w" in name or name in ["max_w", "max_dw"] else 31) for name in FIELDS] + [expected]) + "\n")
            counts[str(expected)] += 1
            total += 1
    all_rtl = sorted((ROOT / "rtl").glob("*.v"))
    # ROM file paths are relative to simulator cwd, exactly like board projects.
    assets_link = OUT / "assets"
    if not assets_link.exists():
        shutil.copytree(ROOT / "assets", assets_link)
    started = time.monotonic()
    summary = {"status": "RUNNING", "generated_utc": datetime.now(timezone.utc).isoformat(), "evidence_kind": "RTL simulation, not a physical FPGA measurement", "seed": SEED, "gate_comparisons": total, "gate_fault_bins": counts, "limits": "Exhaustive control combinations and enumerated numeric domains; directed top/protocol cases. Not exhaustive 16384-byte maps, analog timing, metastability, all temporal interleavings, or formal proof.", "suites": {}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for suite in ["gate", "units", "top", "uart"]:
        top = f"tb_safety_{suite}"
        tb = ROOT / "verification" / f"{top}.v"
        with (OUT / f"{suite}.log").open("w", encoding="utf-8") as log:
            run([executable("iverilog"), "-g2012", "-Wall", "-s", top, "-o", str(OUT / f"{suite}.vvp")] + [str(path) for path in all_rtl] + [str(tb)], log)
            output = run([executable("vvp"), str(OUT / f"{suite}.vvp")], log)
            if f"PASS {suite}:" not in output or "ERROR:" in output:
                raise RuntimeError(f"{suite}: missing PASS marker or simulator memory initialization error")
        with (OUT / f"{suite}_checkpoints.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise RuntimeError(f"{suite}: empty checkpoints")
        signal_map = {
            "gate": ["ctrl[9:0]", "motor_enable", "v_command[4:0]", "omega_command[6:0]", "fault_code[7:0]"],
            "units": ["rst_n", "begin_frame", "write_byte", "commit_frame", "valid", "map_fault", "fresh", "cfg_fault", "event_count[31:0]", "last_fault[7:0]"],
            "top": ["estop", "protective_stop", "ready", "start", "motor_enable", "v_command[4:0]", "omega_command[6:0]", "fault_code[7:0]", "event_count[31:0]", "last_fault[7:0]", "busy", "done"],
            "uart": ["rx", "tx", "led[7:0]", "dut.invalid_command", "dut.protocol_fault", "dut.enable", "dut.vc[4:0]", "dut.wc[6:0]", "dut.fault[7:0]", "dut.events[31:0]", "dut.last[7:0]"]}
        saved = [f'[dumpfile] "{suite}.vcd"', "[timestart] 0", "[size] 1500 900", "@28"]
        saved += [f"{top}.{signal}" for signal in signal_map[suite]]
        (OUT / f"{suite}.gtkw").write_text("\n".join(saved) + "\n", encoding="utf-8")
        summary["suites"][suite] = {"status": "PASS", "checkpoints": len(rows), "waveform": f"{suite}.vcd", "gtkwave_save": f"{suite}.gtkw", "log": f"{suite}.log"}
        print(f"PASS {suite}: {len(rows)} traceable checkpoints", flush=True)
    combined = []
    for suite in summary["suites"]:
        with (OUT / f"{suite}_checkpoints.csv").open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                combined.append({"suite": suite, "case": row["case"], "status": "PASS", "time_ns": row["time_ns"], "waveform": f"{suite}.vcd", "signals": json.dumps(row, sort_keys=True)})
    with (OUT / "cases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["suite", "case", "status", "time_ns", "waveform", "signals"])
        writer.writeheader()
        writer.writerows(combined)
    provenance_files = all_rtl + sorted((ROOT / "verification").glob("tb_safety_*.v")) + [Path(__file__).resolve()]
    summary["source_sha256"] = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in provenance_files}
    summary["tool_versions"] = {"python": sys.version.split()[0], "iverilog": subprocess.run([executable("iverilog"), "-V"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.splitlines()[0]}
    summary.update(status="PASS", elapsed_seconds=round(time.monotonic() - started, 3), checkpoint_count=len(combined), hardware_tests_executed=False)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["status", "gate_comparisons", "checkpoint_count", "elapsed_seconds", "hardware_tests_executed"]}, indent=2))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / "summary.json"
        summary = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        summary.update(status="FAIL", error=str(error), hardware_tests_executed=False)
        path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
