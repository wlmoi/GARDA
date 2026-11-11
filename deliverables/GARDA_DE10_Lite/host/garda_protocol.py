"""GARDA UART protocol (pure Python, no I/O).

Matches rtl/garda_core/garda_uart_protocol.v exactly:

  request  (host -> FPGA): A5 | op | d0 d1 d2 d3 (little endian) | CRC8 | 5A
  response (FPGA -> host): 5A | op | r0 r1 r2 r3 (little endian) | CRC8 | A5

CRC-8, polynomial 0x07, init 0x00, no reflection, no final XOR. Request CRC
covers A5..d3; response CRC covers 5A..r3. One request, one response: a byte
arriving while the FPGA is still answering latches protocol_fault.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

REQ_HEAD, REQ_TAIL = 0xA5, 0x5A
RSP_HEAD, RSP_TAIL = 0x5A, 0xA5
FRAME_LEN = 8

# Legacy GARDA opcodes (garda_uart_top.v)
OP_MAP_BEGIN, OP_MAP_WRITE, OP_MAP_COMMIT = 1, 2, 3
OP_CFG_WRITE, OP_CFG_LOCK, OP_RUN, OP_STATUS = 4, 5, 6, 7
OP_ROM_READ, OP_LATENCY = 8, 9
OP_NN_LOAD, OP_NN_START, OP_NN_READ, OP_NN_CYCLES = 10, 11, 12, 13
OP_COMMAND, OP_EVENTS, OP_LAST_FAULT = 14, 15, 16
# DE10-Lite extensions (rtl/de10_lite/garda_lite_uart_top.v)
OP_IDENT, OP_HOST_ESTOP, OP_SAFE_RESET, OP_WATCHDOG = 0x20, 0x21, 0x22, 0x23
OP_EXT_STATUS, OP_ESTOP_TEST, OP_ESTOP_CAPTURE = 0x24, 0x25, 0x26
OP_COUNTERS, OP_BUILD_ID, OP_LINK_INFO = 0x27, 0x28, 0x29
OP_PORT_STATS, OP_PORT_INFO = 0x2A, 0x2B        # two-host arbiter (port A laptop, port B Jetson)
OP_BOARD_IO = 0x2C                              # switches, keys, LEDs, PLL lock
OP_NN_CMD = 0x2D                                # hardware-gated, clamped neural command [-1.00, +0.99]

IDENT_VALUE = 0x47444C02          # "GDL" + interface version 2
IDENT_PREFIX = 0x47444C00         # any "GDL" interface version
V2_OPS = {0x2A, 0x2B, 0x2C, 0x2D} # only understood by interface version >= 2
SAFE_RESET_MAGIC = 0x52534554     # "RSET"
DEFAULT_CONFIG = 0x00143D0F       # max_v 15, max_w 16, max_dv 15, max_dw 16, version 1

OP_NAMES = {
    1: "MAP_BEGIN", 2: "MAP_WRITE", 3: "MAP_COMMIT", 4: "CFG_WRITE", 5: "CFG_LOCK", 6: "RUN",
    7: "STATUS", 8: "ROM_READ", 9: "LATENCY", 10: "NN_LOAD", 11: "NN_START", 12: "NN_READ",
    13: "NN_CYCLES", 14: "COMMAND", 15: "EVENTS", 16: "LAST_FAULT", 0x20: "IDENT",
    0x21: "HOST_ESTOP", 0x22: "SAFE_RESET", 0x23: "WATCHDOG", 0x24: "EXT_STATUS",
    0x25: "ESTOP_TEST", 0x26: "ESTOP_CAPTURE", 0x27: "COUNTERS", 0x28: "BUILD_ID", 0x29: "LINK_INFO",
    0x2A: "PORT_STATS", 0x2B: "PORT_INFO", 0x2C: "BOARD_IO", 0x2D: "NN_CMD",
}

FAULT_TEXT = {
    0: "all checks passed", 1: "reset active", 2: "E-stop", 3: "protective stop",
    4: "not ready / protocol or command contract violated", 5: "map invalid, incomplete or stale",
    6: "configuration not valid or not locked", 7: "rollout arithmetic fault",
    8: "deadline or command lease expired", 9: "result not valid yet",
    10: "absolute v/omega limit exceeded", 11: "v/omega change limit exceeded",
}


def crc8(data: bytes, crc: int = 0) -> int:
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def encode_request(op: int, payload: int = 0) -> bytes:
    if not 0 <= op <= 0xFF or not 0 <= payload <= 0xFFFFFFFF:
        raise ValueError("opcode must be 8 bit and payload 32 bit")
    body = bytes([REQ_HEAD, op]) + struct.pack("<I", payload)
    return body + bytes([crc8(body), REQ_TAIL])


class ProtocolError(Exception):
    """Response frame missing, malformed or failing CRC."""


@dataclass
class Response:
    op: int
    value: int
    raw: bytes


def decode_response(raw: bytes, expected_op: int | None = None) -> Response:
    if len(raw) != FRAME_LEN:
        raise ProtocolError(f"timeout: received {len(raw)} of 8 bytes ({raw.hex(' ') or 'nothing'})")
    if raw[0] != RSP_HEAD or raw[7] != RSP_TAIL:
        raise ProtocolError(f"bad frame markers: {raw.hex(' ')}")
    if crc8(raw[:6]) != raw[6]:
        raise ProtocolError(f"CRC error: computed {crc8(raw[:6]):02x}, received {raw[6]:02x} ({raw.hex(' ')})")
    if expected_op is not None and raw[1] != expected_op:
        raise ProtocolError(f"opcode echo {raw[1]:#04x} != request {expected_op:#04x}")
    return Response(raw[1], struct.unpack("<I", raw[2:6])[0], bytes(raw))


def signed(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def decode_status(v: int) -> dict:
    return {"motor_enable": bool(v & 1), "busy": bool(v & 2), "done": bool(v & 4),
            "protocol_fault": bool(v & 8), "invalid_command": bool(v & 16),
            "fault_code": (v >> 8) & 0xFF, "fault_text": FAULT_TEXT.get((v >> 8) & 0xFF, "unknown"),
            "candidate_index": (v >> 16) & 0x1FF}


def decode_ext_status(v: int) -> dict:
    names = ["host_estop", "key_estop", "watchdog_armed", "watchdog_trip", "estop_test_armed",
             "estop_test_waiting", "capture_valid", "sw2_not_ready", "sw3_protective_stop",
             "motor_enable", "done", "busy", "protocol_fault", "invalid_command"]
    out = {n: bool(v >> i & 1) for i, n in enumerate(names)}
    out["fault_code"] = (v >> 16) & 0xFF
    out["last_fault"] = (v >> 24) & 0xFF
    return out


def decode_capture(v: int) -> dict:
    return {"valid": bool(v & 1), "measuring": bool(v & 2), "enable_before": bool(v & 4),
            "source_host": bool(v & 8), "source_key": bool(v & 16), "v_before": (v >> 8) & 31,
            "omega_before": signed((v >> 13) & 127, 7), "latency_cycles": (v >> 24) & 0xFF}


def decode_command(v: int) -> dict:
    return {"v": v & 31, "omega": signed((v >> 5) & 127, 7)}


def decode_nn(v: int) -> dict:
    return {"value": signed(v & 0xFFFF, 16), "raw": v & 0xFFFF, "done": bool(v >> 16 & 1),
            "busy": bool(v >> 17 & 1), "fault": bool(v >> 18 & 1)}


def decode_link_info(v: int) -> dict:
    clks, cycles_per_ms = v >> 16, v & 0xFFFF
    clock_hz = cycles_per_ms * 1000
    return {"clks_per_bit": clks, "clock_hz": clock_hz,
            "baud": round(clock_hz / clks) if clks else 0}


def read_mem(path) -> list[int]:
    from pathlib import Path
    return [int(x, 16) for line in Path(path).read_text().splitlines()
            for x in line.split("//")[0].split()]


# Read-only or idempotent requests that may be re-sent after a timeout (e.g. a frame
# dropped by the two-host arbiter). State-changing commands are never retried.
RETRY_SAFE = {OP_STATUS, OP_ROM_READ, OP_LATENCY, OP_NN_READ, OP_NN_CYCLES, OP_COMMAND, OP_EVENTS,
              OP_LAST_FAULT, OP_IDENT, OP_HOST_ESTOP, OP_EXT_STATUS, OP_ESTOP_CAPTURE, OP_COUNTERS,
              OP_BUILD_ID, OP_LINK_INFO, OP_PORT_STATS, OP_PORT_INFO, OP_BOARD_IO, OP_NN_CMD}


def decode_port_stats(v: int) -> dict:
    return {"port_a_frames": v & 0xFFFF, "port_b_frames": v >> 16}


def decode_port_info(v: int) -> dict:
    return {"requesting_port": "B (Jetson)" if v & 1 else "A (laptop)", "collisions": v >> 16}


def decode_board_io(v: int) -> dict:
    return {"sw": [v >> i & 1 for i in range(10)], "key0_released": bool(v >> 10 & 1), "key1_released": bool(v >> 11 & 1),
            "ledr": [v >> (12 + i) & 1 for i in range(10)], "pll_locked": bool(v >> 22 & 1)}


def decode_nn_cmd(v: int) -> dict:
    q = signed(v & 0xFFFF, 16)
    return {"value": round(q / 256, 3), "q88": q, "permit": bool(v >> 28 & 1), "done": bool(v >> 29 & 1),
            "busy": bool(v >> 30 & 1), "fault": bool(v >> 31 & 1)}
