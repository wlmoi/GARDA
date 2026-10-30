"""Preserve literal identifier backslashes in malformed Netgen JSON reports."""
import json
from pathlib import Path
import re


def normalize_sram_power_pins(text):
    """Adapt only the SRAM's supply-pin tokens to Netgen's Verilog dialect."""
    instance = re.compile(
        r'(\bRM_IHPSG13_1P_256x16_c2_bm_bist\s+\\program_store\.i_sram\s+\()(.*?)(\);)',
        re.DOTALL,
    )
    matches = list(instance.finditer(text))
    if len(matches) != 1:
        raise ValueError('Expected one program_store.i_sram in the powered netlist')
    match = matches[0]
    body = match[2]
    for pin in ('VDD!', 'VDDARRAY!', 'VSS!'):
        token = re.compile(r'\.\\?' + re.escape(pin) + r'\s*\(')
        body, count = token.subn('.' + pin + '(', body)
        if count != 1:
            raise ValueError(f'Expected one SRAM supply connection for {pin}')
    return text[:match.start(2)] + body + text[match.end(2):]


def repair_identifier_escapes(text):
    """Repair unsupported string escapes, preserving valid JSON escapes."""
    output = []
    in_string = False
    repairs = 0
    i = 0
    while i < len(text):
        char = text[i]
        if char == '"':
            in_string = not in_string
        if in_string and char == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            valid = next_char in '"\\/bfnrt' or (
                next_char == 'u' and re.fullmatch(r'[0-9a-fA-F]{4}', text[i + 2:i + 6])
            )
            if valid:
                output.append(text[i:i + 2])
                i += 2
                continue
            output.append('\\\\')
            repairs += 1
            i += 1
            continue
        output.append(char)
        i += 1
    return ''.join(output), repairs


def repair_report(path):
    """Validate first and retain the original report when repairing escapes.

    Structural errors still raise JSONDecodeError. Counts and comparisons are
    unchanged, so LibreLane's normal LVS metric/checker path remains active.
    """
    path = Path(path)
    original = path.read_text()
    try:
        json.loads(original)
        return 0
    except json.JSONDecodeError as error:
        if error.msg not in ('Invalid \\escape', 'Invalid \\uXXXX escape'):
            raise
    repaired, count = repair_identifier_escapes(original)
    json.loads(repaired)
    path.with_suffix(path.suffix + '.original').write_text(original)
    path.write_text(repaired)
    return count
