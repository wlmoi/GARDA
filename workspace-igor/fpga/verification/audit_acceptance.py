#!/usr/bin/env python3
"""Check recorded evidence against raw source bytes; never infer a board test."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_hashes(mapping, base):
    mismatches = []
    for name, expected in mapping.items():
        path = (base / name.replace("\\", "/")).resolve()
        if not path.is_relative_to(WORKSPACE):
            mismatches.append({"path": name, "actual": "outside workspace"})
            continue
        actual = sha(path) if path.is_file() else "MISSING"
        if actual != expected:
            mismatches.append({"path": name, "expected": expected, "actual": actual})
    return {"checked": len(mapping), "mismatches": mismatches,
            "passed": bool(mapping) and not mismatches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "evidence/current_acceptance/audit.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("Audit output must stay inside fpga")
    suites = {}
    entries = [
        ("policy", "verification/src_policy/artifacts/results.json", "rtl_and_testbench_sha256"),
        ("safety", "evidence/current_safety/summary.json", "source_sha256"),
        ("board_wrapper", "evidence/current_board_wrapper/summary.json", "source_sha256"),
        ("host", "evidence/current_host/results.json", "sha256"),
    ]
    for name, rel, key in entries:
        path = ROOT / rel
        if not path.is_file():
            suites[name] = {"passed": False, "error": f"MISSING {rel}"}
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        check = check_hashes(doc.get(key, {}), ROOT)
        result_pass = (doc.get("status") == "PASS" or doc.get("success") is True
                       or (doc.get("core", {}).get("passed") is True
                           and doc.get("uart", {}).get("passed") is True))
        suites[name] = {"summary": rel, "summary_sha256": sha(path),
                        "recorded_result_pass": result_pass, **check,
                        "passed": check["passed"] and result_pass}
    provenance = ROOT / "verification/src_policy/artifacts/model_provenance.json"
    if provenance.is_file():
        doc = json.loads(provenance.read_text(encoding="utf-8"))
        suites["model_provenance"] = check_hashes(doc.get("sha256", {}), WORKSPACE)
    else:
        suites["model_provenance"] = {"passed": False, "error": "Missing provenance"}
    lidar_path = ROOT / "evidence/current_lidar/results.json"
    if lidar_path.is_file():
        doc = json.loads(lidar_path.read_text(encoding="utf-8"))
        source = ROOT / "software_integration/src/igor_bringup/igor_bringup/rplidar_driver_node.py"
        runner = ROOT / "verification/run_lidar_regression.py"
        check = check_hashes({str(source.relative_to(ROOT)): doc.get("source_sha256"),
                              str(runner.relative_to(ROOT)): doc.get("runner_sha256")}, ROOT)
        suites["lidar"] = {**check, "recorded_result_pass": doc.get("passed") is True,
                            "passed": check["passed"] and doc.get("passed") is True}
    else:
        suites["lidar"] = {"passed": False, "error": "Missing results"}

    builds = {}
    for name, project, stem in [
        ("policy", "fpga_de10_nano/src_policy", "igor_src_policy"),
        ("planner", "fpga_de10_nano/quartus", "igor"),
    ]:
        base = ROOT / project / "output_files"
        files = {suffix: base / f"{stem}.{suffix}"
                 for suffix in ["sof", "qsf", "flow.rpt", "fit.summary", "sta.summary", "pin"]}
        # QSF is an input in the project directory, not an output file.
        files["qsf"] = ROOT / project / f"{stem}.qsf"
        available = {suffix: sha(path) for suffix, path in files.items() if path.is_file()}
        sta = files["sta.summary"].read_text(errors="replace") if files["sta.summary"].is_file() else ""
        slacks = [float(x) for x in re.findall(r"^Slack\s*:\s*([-+\d.]+)", sta, re.M)]
        flow = files["flow.rpt"].read_text(errors="replace") if files["flow.rpt"].is_file() else ""
        builds[name] = {"files_sha256": available,
                        "reported_flow_success": bool(re.search(r"Flow Status\s*;\s*Successful", flow)),
                        "minimum_reported_slack_ns": min(slacks) if slacks else None,
                        "all_reported_slacks_nonnegative": bool(slacks) and min(slacks) >= 0,
                        "source_to_build_provenance": "Use the separately generated release/build manifest; report presence and hashes alone do not prove the current source produced this SOF."}
    expected_pins = {"FPGA_CLK1_50": "V11", "KEY[0]": "AH17", "KEY[1]": "AH16",
                     "UART_RX": "V12", "UART_TX": "E8", "LED[0]": "W15",
                     "LED[1]": "AA24", "LED[2]": "V16", "LED[3]": "V15",
                     "LED[4]": "AF26", "LED[5]": "AE26", "LED[6]": "Y16", "LED[7]": "AA23"}
    pin_path = ROOT / "fpga_de10_nano/src_policy/output_files/igor_src_policy.pin"
    pin_text = pin_path.read_text(errors="replace") if pin_path.is_file() else ""
    fitted_pins = dict(re.findall(r"^([A-Za-z0-9_]+(?:\[\d+\])?)\s*:\s*([A-Z]+\d+)\s*:", pin_text, re.M))
    pin_errors = {port: {"expected": ball, "actual": fitted_pins.get(port)}
                  for port, ball in expected_pins.items() if fitted_pins.get(port) != ball}
    pin_check = {"expected_pin_count": len(expected_pins), "passed": not pin_errors,
                 "mismatches": pin_errors,
                 "scope": "Fitted report compared with packaged DE10-Nano pin plan; physical wiring has not been measured."}
    passed = all(suite["passed"] for suite in suites.values()) and pin_check["passed"]
    passed &= all(b["reported_flow_success"] and b["all_reported_slacks_nonnegative"]
                  and "sof" in b["files_sha256"] for b in builds.values())
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "status": "PASS" if passed else "FAIL", "source_evidence": suites,
              "build_report_observations": builds, "policy_fitted_pins": pin_check,
              "hardware_tests_executed": False,
              "limits": "Checks integrity of recorded digital evidence, not simulator correctness, formal completeness, SOF-to-source identity, JTAG programming, electrical pins, motor safety, timing on a physical board, or robot performance. Historical evidence/RELEASE_MANIFEST.json is not the current package manifest."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "source_evidence": {
        k: {"passed": v["passed"], "mismatches": len(v.get("mismatches", []))}
        for k, v in suites.items()}, "policy_fitted_pins_pass": pin_check["passed"],
        "output": str(output), "hardware_tests_executed": False}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
