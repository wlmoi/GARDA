"""Quartus discovery, USB-Blaster detection and guarded JTAG programming.

Safety rules enforced here (the dashboard cannot bypass them):
  * only `.sof` files are programmed, only with the JTAG operation `p` (volatile
    SRAM configuration; flash/.pof is never written by this tool);
  * the JTAG chain must contain exactly one device whose IDCODE is the
    DE10-Lite MAX 10 10M50DA (0x031050DD);
  * the .sof must contain the 10M50DAF484C7G device string and, when a build
    manifest exists, match its SHA-256;
  * success is reported only when quartus_pgm exits 0 AND prints
    "Configuration succeeded".
Works on Windows and inside WSL (calls the Windows .exe through interop).
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

EXPECTED_IDCODE = "031050DD"
EXPECTED_DEVICE = "10M50DAF484C7G"
IN_WSL = "microsoft" in Path("/proc/version").read_text().lower() if Path("/proc/version").exists() else False


def _candidates() -> list[str]:
    env = os.environ.get("GARDA_QUARTUS_BIN")
    roots = [env] if env else []
    pats = ["{d}:/OldQuartus/quartus/bin64", "{d}:/intelFPGA_lite/*/quartus/bin64", "{d}:/altera_lite/*/quartus/bin64",
            "{d}:/Quartus-Program/quartus/bin64", "{d}:/intelFPGA/*/quartus/bin64"]
    for d in "DC":
        for p in pats:
            p = p.format(d=d)
            if IN_WSL:
                p = f"/mnt/{d.lower()}" + p[2:]
            roots += sorted(glob.glob(p), reverse=True)
    return [r for r in roots if r]


def _exe(bin_dir: Path, name: str) -> Path:
    return bin_dir / (name + ".exe") if (bin_dir / (name + ".exe")).exists() else bin_dir / name


def edition(bin_dir: Path) -> str:
    vt = bin_dir.parent / "version.txt"
    if vt.exists():
        m = re.search(r"Edition=(\w+)", vt.read_text(errors="replace"))
        v = re.search(r"Version=(\S+)", vt.read_text(errors="replace"))
        return f"{v.group(1) if v else '?'} {m.group(1) if m else '?'}"
    return "unknown"


def find_quartus_bin(for_compile: bool = True) -> Path | None:
    """Prefer a Lite install for compiling (no licence needed for MAX 10)."""
    found = [Path(c) for c in _candidates() if _exe(Path(c), "quartus_pgm").exists()]
    if for_compile:
        lite = [f for f in found if "lite" in edition(f).lower()]
        found = lite + [f for f in found if f not in lite]
    return found[0] if found else None


def win_path(p: Path) -> str:
    if not IN_WSL:
        return str(p)
    return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True, check=True).stdout.strip()


def jtag_scan(bin_dir: Path | None = None, timeout: float = 30) -> dict:
    """Run jtagconfig (read-only) and parse cables and devices."""
    bin_dir = bin_dir or find_quartus_bin(for_compile=False)
    if not bin_dir:
        return {"ok": False, "state": "QUARTUS_NOT_FOUND", "cables": [], "raw": ""}
    try:
        r = subprocess.run([str(_exe(bin_dir, "jtagconfig"))], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "state": "JTAGCONFIG_FAILED", "error": str(e), "cables": [], "raw": ""}
    raw = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "TBBmalloc" not in l)
    cables, cur = [], None
    for line in raw.splitlines():
        m = re.match(r"\s*\d+\)\s+(.+?)\s*$", line)
        if m:
            cur = {"name": m.group(1), "devices": [], "error": None}
            cables.append(cur)
            continue
        m = re.match(r"\s+([0-9A-Fa-f]{8})\s+(.+)$", line)
        if m and cur is not None:
            cur["devices"].append({"idcode": m.group(1).upper(), "name": m.group(2).strip()})
        elif cur is not None and line.strip():
            cur["error"] = line.strip()
    if not cables:
        state = "BOARD_DISCONNECTED"
    elif any(c["error"] and not c["devices"] for c in cables):
        state = "CHAIN_BROKEN"   # cable present, board unpowered or not attached
    else:
        state = "USB_BLASTER_DETECTED"
    return {"ok": True, "state": state, "cables": cables, "raw": raw, "quartus_bin": str(bin_dir)}


def verify_target(scan: dict) -> tuple[bool, str, str | None]:
    """Exactly one cable with exactly one 10M50DA device."""
    if scan.get("state") != "USB_BLASTER_DETECTED":
        return False, f"JTAG state is {scan.get('state')}", None
    good = [c for c in scan["cables"] if len(c["devices"]) == 1 and c["devices"][0]["idcode"] == EXPECTED_IDCODE]
    if len(scan["cables"]) != 1 or len(good) != 1:
        return False, ("refusing: need exactly one USB-Blaster with exactly one 10M50DA "
                       f"(IDCODE 0x{EXPECTED_IDCODE}) in the chain; found "
                       + "; ".join(f"{c['name']}: {[d['idcode'] for d in c['devices']]}" for c in scan["cables"])), None
    return True, f"{good[0]['name']}: {good[0]['devices'][0]['name']} (0x{EXPECTED_IDCODE})", good[0]["name"]


def verify_sof(sof: Path, manifest_path: Path | None = None) -> tuple[bool, str, dict]:
    if sof.suffix.lower() != ".sof" or not sof.is_file():
        return False, f"not a .sof file: {sof}", {}
    data = sof.read_bytes()
    if EXPECTED_DEVICE.encode() not in data:
        return False, f"{sof.name} was not built for {EXPECTED_DEVICE}", {}
    info = {"file": sof.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "mtime": sof.stat().st_mtime}
    if manifest_path and manifest_path.exists():
        man = json.loads(manifest_path.read_text())
        info["manifest"] = man
        if man.get("sof_file") == sof.name and man.get("sof_sha256") != info["sha256"]:
            return False, "SHA-256 differs from build_manifest.json (file changed after build)", info
    return True, f"{sof.name}: {EXPECTED_DEVICE}, {len(data)} bytes", info


def program_sof(sof: Path, cable: str, bin_dir: Path | None = None, timeout: float = 120) -> dict:
    """Volatile JTAG configuration of device index 1. Caller must have verified target and file."""
    bin_dir = bin_dir or find_quartus_bin(for_compile=False)
    cmd = [str(_exe(bin_dir, "quartus_pgm")), "-c", cable, "-m", "JTAG", "-o", f"p;{win_path(sof)}@1"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "state": "PROGRAMMING_FAILED", "error": str(e), "command": cmd}
    log = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "TBBmalloc" not in l)
    ok = r.returncode == 0 and "Configuration succeeded" in log
    return {"ok": ok, "state": "PROGRAMMING_SUCCESSFUL" if ok else "PROGRAMMING_FAILED",
            "exit_code": r.returncode, "log": log, "command": cmd}
