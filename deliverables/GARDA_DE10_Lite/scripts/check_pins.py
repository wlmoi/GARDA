#!/usr/bin/env python3
"""Check every location assignment in the QSF against the DE10-Lite manual pin table.

docs/de10_lite_manual_pin_table.txt is extracted verbatim from the Terasic
DE10-Lite User Manual (2022-10-17). Exit code 0 only if every QSF pin matches.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manual = {}
for line in (ROOT / "docs/de10_lite_manual_pin_table.txt").read_text().splitlines():
    if line and not line.startswith("#"):
        name, pin = line.split()
        manual[name] = pin

# QSF port name -> manual signal name
def manual_name(port: str) -> str:
    m = re.fullmatch(r"(\w+?)\[(\d+)\]", port)
    base, idx = (m.group(1), m.group(2)) if m else (port, None)
    if base == "JP1_RX":          # JP1 pins 1, 3, 5
        return f"GPIO_{2 * int(idx)}"
    if base == "JP1_TX":          # JP1 pins 2, 4, 6
        return f"GPIO_{2 * int(idx) + 1}"
    if base in ("KEY", "SW", "LEDR"):
        return f"{base}{idx}"
    if re.fullmatch(r"HEX[0-5]", base):
        return f"{base}{idx}"
    if base.startswith("VGA_") and idx is not None:
        return f"{base}{idx}"
    return port

errors, checked = [], 0
for m in re.finditer(r"set_location_assignment (PIN_\w+) -to (\S+)", (ROOT / "quartus/garda_de10_lite.qsf").read_text()):
    pin, port = m.groups()
    want = manual.get(manual_name(port))
    checked += 1
    if want != pin:
        errors.append(f"{port}: QSF {pin}, manual {manual_name(port)} = {want}")
print(f"checked {checked} pin assignments against the DE10-Lite manual")
for e in errors:
    print("MISMATCH", e)
print("PASS" if not errors else "FAIL")
sys.exit(1 if errors else 0)
