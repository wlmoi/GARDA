"""GARDA UART protocol v1: encoder, decoder, stream assembler.

Authoritative source: dashboard/dist/source/rtl/garda_uart_protocol.v (+ _rx/_tx/_top).
  Request  (host -> FPGA, 8 bytes): A5 | opcode | payload[7:0] .. payload[31:24] (little-endian) | CRC8 | 5A
  Response (FPGA -> host, 8 bytes): 5A | opcode (echo) | data[7:0] .. data[31:24] (little-endian) | CRC8 | A5
  CRC8: poly 0x07, init 0, no reflection, no final XOR.
        Request CRC covers A5,op,payload (bytes 0..5); response CRC covers 5A,op,data (bytes 0..5).
  Framing: 8N1, LSB first, CLKS_PER_BIT=434 @ 50 MHz -> 115207 baud (nominal 115200).
"""
from __future__ import annotations
import struct

REQ_SOF, REQ_EOF = 0xA5, 0x5A
RSP_SOF, RSP_EOF = 0x5A, 0xA5
FRAME_LEN = 8
BAUD = 115200
CLK_HZ = 50_000_000
CLKS_PER_BIT = 434
DATA_BITS, STOP_BITS, PARITY = 8, 1, "none"

FAULT_CODES = {
    0: "Gate permits command", 1: "Reset asserted", 2: "Emergency input KEY1",
    3: "Protective stop SW3", 4: "Not ready / sticky control fault / UART fault",
    5: "Map absent, stale or invalid", 6: "Configuration absent, unlocked or invalid",
    7: "Tile arithmetic fault", 8: "Deadline or command lease expired",
    9: "Tiles/result incomplete or no valid candidate",
    10: "Velocity bound exceeded", 11: "Command delta bound exceeded",
}

# name, payload description, response description, mirrors payload_ok in garda_uart_top.v
OPCODES = {
    1: ("MAP_BEGIN", "map sequence number (first = 1)", "status"),
    2: ("MAP_WRITE", "address[14:0] | cell<<16 ; bits 31:24 and 15 zero", "status"),
    3: ("MAP_COMMIT", "0 (after 16384 ascending writes)", "status"),
    4: ("CONFIG_WRITE", "version=1<<20 | max_dw[19:14] | max_dv[13:10] | max_w[9:4] | max_v[3:0]", "status"),
    5: ("CONFIG_LOCK", "0", "status"),
    6: ("DWA_RUN", "0 (starts DWA planner)", "status"),
    7: ("STATUS", "0", "status (op0/default response)"),
    8: ("ROM_READ", "ROM address 0..6019", "ROM word [15:0]"),
    9: ("DWA_LATENCY", "0", "DWA latency cycles"),
    10: ("NN_INPUT", "index[4:0] | signed Q8.8 value<<8", "status"),
    11: ("NN_START", "0 (after 24 inputs loaded)", "status"),
    12: ("NN_RESULT", "output index 0..3", "result[15:0] signed | done<<16 | busy<<17 | fault<<18"),
    13: ("NN_LATENCY", "0", "NN latency cycles"),
    14: ("GATE_COMMAND", "0", "v[4:0] | signed omega[11:5]  (final permitted command)"),
    15: ("EVENT_COUNT", "0", "event counter"),
    16: ("LAST_FAULT", "0", "last fault code [7:0]"),
}


def crc8(data: bytes, init: int = 0) -> int:
    c = init
    for v in data:
        c ^= v
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def payload_ok(op: int, data: int) -> bool:
    """Exact mirror of the payload_ok case statement in garda_uart_top.v."""
    if op == 1: return True
    if op == 2: return (data >> 24) == 0 and not (data >> 15) & 1
    if op == 4: return (data >> 28) == 0 and (data >> 20) & 0xFF == 1 and (data >> 4) & 0x3F <= 16 and (data >> 14) & 0x3F <= 32
    if op == 8: return data < 6020
    if op == 10: return (data >> 5) & 7 == 0 and (data >> 24) == 0 and (data & 0x1F) < 24
    if op == 12: return (data >> 2) == 0
    if op in (3, 5, 6, 7, 9, 11, 13, 14, 15, 16): return data == 0
    return False


def encode_request(op: int, payload: int = 0) -> bytes:
    if not 0 <= op <= 255: raise ValueError("opcode out of range")
    if not 0 <= payload <= 0xFFFFFFFF: raise ValueError("payload out of range")
    body = bytes([REQ_SOF, op]) + struct.pack("<I", payload)
    return body + bytes([crc8(body), REQ_EOF])


def encode_response(op: int, data: int) -> bytes:  # used by the simulation + tests
    body = bytes([RSP_SOF, op]) + struct.pack("<I", data & 0xFFFFFFFF)
    return body + bytes([crc8(body), RSP_EOF])


def _s(v: int, bits: int) -> int:
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def decode_status(v: int) -> dict:
    fc = (v >> 8) & 0xFF
    return {"enable": bool(v & 1), "busy": bool(v & 2), "done": bool(v & 4),
            "protocol_fault": bool(v & 8), "invalid_command": bool(v & 16),
            "fault_code": fc, "fault_reason": FAULT_CODES.get(fc, "unknown"),
            "candidate_index": (v >> 16) & 0x1FF}


def decode_value(op: int, v: int) -> dict:
    if op == 8: return {"rom_word": v & 0xFFFF}
    if op in (9, 13, 15): return {"count": v}
    if op == 12: return {"result_q8_8": _s(v & 0xFFFF, 16), "result_raw": v & 0xFFFF,
                         "done": bool(v >> 16 & 1), "busy": bool(v >> 17 & 1), "fault": bool(v >> 18 & 1)}
    if op == 14: return {"v_command": v & 0x1F, "omega_command": _s((v >> 5) & 0x7F, 7)}
    if op == 16: return {"last_fault": v & 0xFF, "fault_reason": FAULT_CODES.get(v & 0xFF, "unknown")}
    return decode_status(v)


def decode_request(raw: bytes) -> dict:
    out = {"kind": "request", "length": len(raw), "valid": False, "errors": []}
    if len(raw) != FRAME_LEN: out["errors"].append(f"length {len(raw)} != 8"); return out
    out["sof"], out["opcode"] = raw[0], raw[1]
    out["payload"] = struct.unpack("<I", raw[2:6])[0]
    out["crc_tx"], out["crc_calc"] = raw[6], crc8(raw[:6])
    out["crc_ok"] = out["crc_tx"] == out["crc_calc"]
    out["op_name"] = OPCODES.get(raw[1], ("UNKNOWN",))[0]
    if raw[0] != REQ_SOF: out["errors"].append("bad SOF")
    if raw[7] != REQ_EOF: out["errors"].append("bad EOF")
    if not out["crc_ok"]: out["errors"].append("CRC mismatch")
    out["payload_ok"] = payload_ok(raw[1], out["payload"])
    out["valid"] = not out["errors"]
    return out


def decode_response(raw: bytes, expect_op: int | None = None) -> dict:
    out = {"kind": "response", "length": len(raw), "valid": False, "errors": []}
    if len(raw) != FRAME_LEN: out["errors"].append(f"length {len(raw)} != 8"); return out
    out["sof"], out["opcode"] = raw[0], raw[1]
    out["data"] = struct.unpack("<I", raw[2:6])[0]
    out["crc_tx"], out["crc_calc"] = raw[6], crc8(raw[:6])
    out["crc_ok"] = out["crc_tx"] == out["crc_calc"]
    out["op_name"] = OPCODES.get(raw[1], ("UNKNOWN",))[0]
    if raw[0] != RSP_SOF: out["errors"].append("bad SOF")
    if raw[7] != RSP_EOF: out["errors"].append("bad EOF")
    if not out["crc_ok"]: out["errors"].append("CRC mismatch")
    if expect_op is not None and raw[1] != expect_op:
        out["errors"].append(f"opcode echo {raw[1]} != request {expect_op}")
    out["fields"] = decode_value(raw[1], out["data"])
    out["valid"] = not out["errors"]
    return out


def uart_frame_bits(byte: int) -> list[int]:
    """Logical 8N1 line levels for one byte: start(0), D0..D7 (LSB first), stop(1)."""
    return [0] + [(byte >> i) & 1 for i in range(8)] + [1]


def bit_time_us(baud: int = BAUD) -> float: return 1e6 / baud
def byte_time_us(baud: int = BAUD) -> float: return 10e6 / baud
