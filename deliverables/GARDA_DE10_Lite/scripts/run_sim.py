#!/usr/bin/env python3
"""Run every RTL regression with Icarus Verilog and collect logs in reports/sim/.

  1. tb_legacy_uart (original garda_uart_top)  - existing GARDA UART contract test (baseline)
  2. tb_legacy_uart (DE10-Lite garda_lite_uart_top) - same test on the DE10-Lite top
  3. tb_lockstep    - cycle-by-cycle equivalence on random legacy traffic + planner + neural
  4. tb_board       - full board top system test (writes the SOFTWARE SIMULATION trace)
  5. tb_baud        - real host bit periods at 115200 against divisor 434 (IDENT/STATUS)
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "sim/build"
R = ROOT / "reports/sim"
CORE = sorted(str(p) for p in (ROOT / "rtl/garda_core").glob("*.v"))
LITE = sorted(str(p) for p in (ROOT / "rtl/de10_lite").glob("*.v"))
LITE_TOP = [str(ROOT / "rtl/de10_lite/garda_lite_uart_top.v")]

JOBS = [
    ("legacy_uart_original", "sim/tb_legacy_uart.v", CORE, ["-DDUT_MODULE=garda_uart_top", '-DCSV_NAME="sim/build/legacy_garda_uart_top.csv"'], "PASS uart"),
    ("legacy_uart_de10lite", "sim/tb_legacy_uart.v", CORE + LITE_TOP, ["-DDUT_MODULE=garda_lite_uart_top", '-DCSV_NAME="sim/build/legacy_garda_lite_uart_top.csv"'], "PASS uart"),
    ("lockstep", "sim/tb_lockstep.v", CORE + LITE_TOP, [], "PASS lockstep"),
    ("board", "sim/tb_board.v", CORE + LITE, [], "PASS board"),
    ("baud_115200", "sim/tb_board.v", CORE + LITE, ["-DCLKS=391", "-DHALF_NS=11.111", "-DHOST_BIT_NS=(1.0e9/115200.0)", "-DSHORT", '-DTRACE_FILE="sim/build/baud_trace.jsonl"'], "PASS board"),
]


def main(selected):
    B.mkdir(parents=True, exist_ok=True)
    R.mkdir(parents=True, exist_ok=True)
    ok_all = True
    for name, tb, srcs, defs, marker in JOBS:
        if selected and name not in selected:
            continue
        vvp = B / f"{name}.vvp"
        t0 = time.time()
        top = {"sim/tb_legacy_uart.v": "tb_safety_uart", "sim/tb_lockstep.v": "tb_lockstep", "sim/tb_board.v": "tb_board"}[tb]
        c = subprocess.run(["iverilog", "-g2005", "-DGARDA_SIM_PLL", "-s", top, "-I", "rtl/de10_lite", *defs, "-o", str(vvp), tb, *srcs],
                           cwd=ROOT, capture_output=True, text=True)
        out = c.stdout + c.stderr
        if c.returncode == 0:
            r = subprocess.run(["vvp", "-n", str(vvp)], cwd=ROOT, capture_output=True, text=True)
            out += r.stdout + r.stderr
        passed = marker in out and "FATAL" not in out
        ok_all &= passed
        (R / f"{name}.log").write_text(out)
        print(f"{'PASS' if passed else 'FAIL'}  {name:24s} {time.time() - t0:7.1f} s")
    if (R / "board.log").exists() and (not selected or "board" in selected):
        shutil.copy2(R / "board.log", B / "board.log")   # make_sim_trace reads the checks from here
        subprocess.run([sys.executable, str(ROOT / "scripts/make_sim_trace.py")], check=False)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
