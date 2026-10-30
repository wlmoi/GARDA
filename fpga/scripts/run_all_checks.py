#!/usr/bin/env python3
"""Run the local equivalents of the supplied CI jobs, without opening hardware."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/current_checks"
MOTOR = ROOT / "robot/jetauto/FPGA_UART_TTL_MULTISPEED"
SUITES = ("policy", "safety", "host", "legacy", "motors")


def executable(name):
    found = shutil.which(name)
    windows = Path("C:/iverilog/bin") / (name + ".exe")
    if not found and windows.is_file():
        found = str(windows)
    if not found:
        raise RuntimeError(f"Required program missing from PATH: {name}")
    return found


def commands(suites):
    py = sys.executable
    jobs = []
    def add(name, command, cwd=ROOT, timeout=1800):
        jobs.append((name, list(map(str, command)), cwd, timeout))
    if "policy" in suites:
        add("policy_core_uart", [py, "verification/src_policy/run.py", "--check"])
        add("policy_board_wrapper", [py, "verification/run_board_wrapper.py"])
    if "safety" in suites:
        add("safety", [py, "verification/run_safety_regression.py"])
    if "host" in suites:
        add("host", [py, "verification/run_host_regression.py"])
        add("lidar", [py, "verification/run_lidar_regression.py"])
        add("hardware_capture_fixtures", [py, "verification/test_capture_hardware_safety.py"])
    if "legacy" in suites:
        add("legacy_rtl", [py, "verification/run.py", "all"])
        add("legacy_generic_netlist", [py, "verification/run.py", "tt_generic"])
        add("legacy_release_links", [py, "scripts/test_release_integrity.py"])
    if "motors" in suites:
        iverilog, vvp = executable("iverilog"), executable("vvp")
        add("motor_packets_compile", [iverilog, "-g2012", "-s", "tb_multispeed", "-o", OUT / "motor_packets.vvp",
                                       "rtl/stm_packet_tx_multispeed.v", "tb/tb_multispeed.v"], MOTOR)
        add("motor_packets", [vvp, OUT / "motor_packets.vvp"], MOTOR)
        add("motor_control_compile", [iverilog, "-g2012", "-s", "tb_multispeed_control", "-o", OUT / "motor_control.vvp",
                                       "rtl/stm_packet_tx_multispeed.v", "rtl/stm_uart_multispeed_top.v", "tb/tb_multispeed_control.v"], MOTOR)
        add("motor_control", [vvp, OUT / "motor_control.vvp"], MOTOR)
        add("motor_sdk_oracle", [py, "robot/jetauto/verify_driver.py"])
        # Omitting --run makes this an offline decoder; it cannot open a port.
        add("motor_rtl_frame_oracle", [py, "robot/jetauto/test_rtl_packets_on_stm.py"])
    return jobs


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", choices=SUITES,
                        help="Select one or more jobs; default: all suites")
    parser.add_argument("--list", action="store_true", help="Show selected commands without running tests")
    args = parser.parse_args()
    selected = tuple(name for name in SUITES if name in (args.suite or SUITES))
    # --list is also usable on a fresh machine before Icarus is installed.
    if args.list:
        for name in selected:
            print(name)
        print("See ci/README.md for the individual commands and dependencies.")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"status": "RUNNING", "started_utc": now(), "suites": selected,
              "evidence_kind": "Software and RTL simulation; no physical FPGA or motor measurement",
              "hardware_tests_executed": False, "python": sys.version.split()[0],
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "steps": []}
    def save():
        (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    save()
    try:
        jobs = commands(selected)
        for name, command, cwd, timeout in jobs:
            print(f"RUN {name}", flush=True)
            started = time.monotonic()
            path = OUT / f"{name}.log"
            step = {"name": name, "command": command, "cwd": str(cwd.relative_to(ROOT)) or ".",
                    "started_utc": now(), "status": "RUNNING", "log": path.name}
            report["steps"].append(step)
            save()
            with path.open("w", encoding="utf-8") as log:
                try:
                    result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                            timeout=timeout, text=True)
                    step["returncode"] = result.returncode
                    step["status"] = "PASS" if result.returncode == 0 else "FAIL"
                except subprocess.TimeoutExpired:
                    step.update(status="FAIL", error=f"Exceeded {timeout} seconds")
                except OSError as error:
                    step.update(status="FAIL", error=str(error))
            step.update(elapsed_seconds=round(time.monotonic()-started, 3),
                        log_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            save()
            print(f"{step['status']} {name}: {step['elapsed_seconds']} s; {path.relative_to(ROOT)}", flush=True)
            if step["status"] != "PASS":
                print(path.read_text(encoding="utf-8", errors="replace")[-6000:], file=sys.stderr)
                raise RuntimeError(f"{name} failed; inspect {path}")
        report["status"] = "PASS"
    except Exception as error:
        report.update(status="FAIL", error=str(error))
        print(str(error), file=sys.stderr)
    report["completed_utc"] = now()
    save()
    print(f"{report['status']}: {len(report['steps'])} steps; evidence/current_checks/report.json", flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
