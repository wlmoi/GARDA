"""Preserve literal identifier backslashes in malformed Netgen JSON reports."""
import json
from pathlib import Path
import re


def normalize_sram_power_pins(text):
    """Adapt only the required SRAM supply-pin tokens for Netgen Verilog."""
    from .contracts import EXPECTED_INSTANCES
    seen = set()
    instance = re.compile(
        r'(\b(RM_IHPSG13_1P_(?:2048x64_c2|256x16_c2)_bm_bist)\s+\\(parameter_store\.i_sram|neural\.activation_store\.banks\\?\[\d+\\?\]\.i_sram)\s+\()(.*?)(\);)',
        re.DOTALL,
    )
    def adapt(match):
        name = match[3].replace('\\[', '[').replace('\\]', ']')
        if name in seen or EXPECTED_INSTANCES.get(name) != match[2]:
            raise ValueError('Unexpected, wrong-master or duplicate neural SRAM')
        seen.add(name)
        body = match[4]
        for pin in ('VDD!', 'VDDARRAY!', 'VSS!'):
            token = re.compile(r'\.\\?' + re.escape(pin) + r'\s*\(')
            body, count = token.subn('.' + pin + '(', body)
            if count != 1:
                raise ValueError(f'Expected one SRAM supply connection for {pin}')
        return match[1] + body + match[5]
    adapted = instance.sub(adapt, text)
    # Reject extra SRAMs outside the intended names as well as missing ones.
    if len(re.findall(r'\bRM_IHPSG13_\w+\s+\\?\S+\s+\(',text)) != len(EXPECTED_INSTANCES):
        raise ValueError('Unexpected number of SRAM instances')
    if seen != set(EXPECTED_INSTANCES):
        raise ValueError('Expected one parameter and two activation SRAMs')
    return adapted


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
