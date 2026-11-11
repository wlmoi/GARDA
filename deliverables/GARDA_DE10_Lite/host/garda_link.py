"""Serial link to the GARDA DE10-Lite with packet logging and counters.

UART state machine reported to the dashboard:
  PORT_NOT_FOUND -> PORT_DETECTED -> CONNECTING -> CONNECTED -> FPGA_RESPONDING
                                              \\-> TIMEOUT / CRC_ERROR
A port that merely opens is CONNECTED, never FPGA_RESPONDING: that state needs
a CRC-valid IDENT response carrying 0x47444C01.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path

import garda_protocol as p

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
CLOCK_MHZ = 45.0   # core clock; replaced by the value the FPGA reports in LINK_INFO


def list_ports() -> list[dict]:
    try:
        from serial.tools import list_ports as lp
    except ImportError:
        return []
    out = []
    for info in lp.comports():
        if "Bluetooth" in (info.description or "") or info.device.startswith("/dev/ttyS"):
            continue
        out.append({"device": info.device, "description": info.description or "",
                    "vid": f"{info.vid:04x}" if info.vid else None, "pid": f"{info.pid:04x}" if info.pid else None,
                    "serial": info.serial_number})
    return out


class GardaLink:
    def __init__(self):
        self.ser = None
        self.port = None
        self.baud = 115200
        self.state = "PORT_NOT_FOUND"
        self.lock = threading.RLock()
        self.log = deque(maxlen=400)
        self.seq = 0
        self.counters = {"tx_frames": 0, "rx_frames": 0, "tx_bytes": 0, "rx_bytes": 0,
                         "timeouts": 0, "crc_errors": 0, "frame_errors": 0}
        self.ident = None
        self.last_rx_time = None
        self.session_file = None
        self.capture = None           # list collecting frames for a recorded trace

    # ------------------------------------------------------------- connection
    def connect(self, port: str, baud: int = 115200, timeout: float = 0.25) -> dict:
        import serial
        with self.lock:
            self.disconnect()
            self.state = "CONNECTING"
            try:
                self.ser = serial.serial_for_url(port, baud, timeout=timeout, write_timeout=1)
            except Exception as e:  # noqa: BLE001 - surfaced to the UI verbatim
                self.ser = None
                self.state = "PORT_NOT_FOUND"
                return {"ok": False, "error": f"cannot open {port}: {e}"}
            self.port, self.baud = port, baud
            time.sleep(0.05)
            self.ser.reset_input_buffer()
            self.state = "CONNECTED"
            LOG_DIR.mkdir(exist_ok=True)
            self.session_file = LOG_DIR / time.strftime("uart_%Y%m%d_%H%M%S.jsonl")
            self._event("connect", f"opened {port} at {baud} 8N1")
            return {"ok": True}

    def disconnect(self):
        with self.lock:
            if self.ser is not None:
                try:
                    self.ser.close()
                finally:
                    self._event("disconnect", f"closed {self.port}")
            self.ser = None
            self.ident = None
            if self.state not in ("PORT_NOT_FOUND",):
                self.state = "PORT_DETECTED" if self.port else "PORT_NOT_FOUND"

    @property
    def connected(self) -> bool:
        return self.ser is not None

    # ------------------------------------------------------------- transfers
    def _event(self, kind: str, text: str):
        self._record({"kind": kind, "text": text})

    def _record(self, entry: dict):
        self.seq += 1
        entry = {"seq": self.seq, "t": time.time(), **entry}
        self.log.append(entry)
        if self.capture is not None:
            self.capture.append(entry)
        if self.session_file:
            with self.session_file.open("a") as fh:
                fh.write(json.dumps(entry) + "\n")

    def transact(self, op: int, payload: int = 0, timeout: float = 0.25, quiet: bool = False,
                 corrupt_crc: bool = False, retries: int | None = None) -> p.Response:
        """Send one request; read-only/idempotent requests are retried after a timeout
        (a frame can be dropped when the other host holds the shared link)."""
        if retries is None:
            retries = 2 if op in p.RETRY_SAFE and not corrupt_crc else 0
        for attempt in range(retries + 1):
            try:
                return self._transact_once(op, payload, timeout, quiet, corrupt_crc)
            except p.ProtocolError as e:
                if attempt == retries or "timeout" not in str(e):
                    raise
                time.sleep(0.01 + 0.02 * attempt)

    def _transact_once(self, op: int, payload: int, timeout: float, quiet: bool, corrupt_crc: bool) -> p.Response:
        with self.lock:
            if self.ser is None:
                raise p.ProtocolError("not connected")
            req = bytearray(p.encode_request(op, payload))
            if corrupt_crc:
                req[6] ^= 0x5C
            t0 = time.perf_counter()
            try:
                self.ser.reset_input_buffer()
                self.ser.timeout = timeout
                self.ser.write(req)
                self.ser.flush()
                raw = self.ser.read(p.FRAME_LEN)
            except Exception as e:  # noqa: BLE001 - adapter unplugged / re-enumerated: drop the dead handle
                port = self.port
                try:
                    self.ser.close()
                finally:
                    self.ser = None
                self.ident = None
                self.state = "PORT_DETECTED"
                self.port = port
                self._event("disconnect", f"serial device lost ({type(e).__name__}); will reconnect")
                raise p.ProtocolError(f"serial device lost: {e}")
            rtt = (time.perf_counter() - t0) * 1000
            self.counters["tx_frames"] += 1
            self.counters["tx_bytes"] += len(req)
            self.counters["rx_bytes"] += len(raw)
            entry = {"kind": "frame", "op": op, "op_name": p.OP_NAMES.get(op, f"0x{op:02x}"), "payload": payload,
                     "tx": bytes(req).hex(" "), "rx": raw.hex(" "), "rtt_ms": round(rtt, 2), "corrupt_crc": corrupt_crc}
            try:
                resp = p.decode_response(raw, op)
            except p.ProtocolError as e:
                msg = str(e)
                if len(raw) < p.FRAME_LEN:
                    self.counters["timeouts"] += 1
                    entry["result"] = "TIMEOUT"
                elif "CRC" in msg:
                    self.counters["crc_errors"] += 1
                    entry["result"] = "CRC_ERROR"
                else:
                    self.counters["frame_errors"] += 1
                    entry["result"] = "FRAME_ERROR"
                entry["error"] = msg
                if not corrupt_crc:
                    self.state = "TIMEOUT / CRC ERROR"
                self._record(entry)          # errors are always logged, even for bulk transfers
                raise
            self.counters["rx_frames"] += 1
            self.last_rx_time = time.time()
            if self.ident and self.state == "TIMEOUT / CRC ERROR":
                self.state = "FPGA_RESPONDING"      # a CRC-valid answer proves the FPGA is responding again
            entry["result"] = "OK"
            entry["value"] = resp.value
            entry["decoded"] = describe(op, resp.value)
            if not quiet:                    # bulk map writes are counted, not logged one by one
                self._record(entry)
            return resp

    def identify(self) -> dict:
        """The only path to FPGA_RESPONDING: a CRC-valid IDENT with the GARDA signature."""
        r = self.transact(p.OP_IDENT)
        if r.value & 0xFFFFFF00 != p.IDENT_PREFIX or (r.value & 0xFF) == 0:
            self.state = "TIMEOUT / CRC ERROR"
            raise p.ProtocolError(f"unexpected IDENT value 0x{r.value:08x} (not a GARDA DE10-Lite image)")
        info = p.decode_link_info(self.transact(p.OP_LINK_INFO).value)
        info["build_id"] = f"0x{self.transact(p.OP_BUILD_ID).value:08X}"
        info["interface_version"] = r.value & 0xFF
        self.ident = info
        global CLOCK_MHZ
        CLOCK_MHZ = info["clock_hz"] / 1e6 or CLOCK_MHZ
        self.state = "FPGA_RESPONDING"
        return info


def describe(op: int, v: int) -> dict:
    if op in (p.OP_STATUS, 1, 2, 3, 4, 5, 6, 11, p.OP_HOST_ESTOP, p.OP_SAFE_RESET, p.OP_WATCHDOG, p.OP_ESTOP_TEST):
        return p.decode_status(v)
    return {
        p.OP_IDENT: lambda: {"signature": f"0x{v:08X}", "valid": v & 0xFFFFFF00 == p.IDENT_PREFIX, "interface_version": v & 0xFF},
        p.OP_LINK_INFO: lambda: p.decode_link_info(v),
        p.OP_BUILD_ID: lambda: {"build_id": f"0x{v:08X}"},
        p.OP_EXT_STATUS: lambda: p.decode_ext_status(v),
        p.OP_ESTOP_CAPTURE: lambda: p.decode_capture(v),
        p.OP_COMMAND: lambda: p.decode_command(v),
        p.OP_NN_READ: lambda: p.decode_nn(v),
        p.OP_COUNTERS: lambda: {"frames": v >> 16, "accepted": v & 0xFFFF},
        p.OP_LATENCY: lambda: {"cycles": v, "us": round(v / CLOCK_MHZ, 2)},
        p.OP_NN_CYCLES: lambda: {"cycles": v, "us": round(v / CLOCK_MHZ, 2)},
        p.OP_EVENTS: lambda: {"events": v},
        p.OP_LAST_FAULT: lambda: {"last_fault": v & 0xFF, "text": p.FAULT_TEXT.get(v & 0xFF, "unknown")},
        p.OP_ROM_READ: lambda: {"word": f"0x{v & 0xFFFF:04X}"},
        p.OP_PORT_STATS: lambda: p.decode_port_stats(v),
        p.OP_PORT_INFO: lambda: p.decode_port_info(v),
        p.OP_BOARD_IO: lambda: p.decode_board_io(v),
        p.OP_NN_CMD: lambda: p.decode_nn_cmd(v),
    }.get(op, lambda: {"raw": f"0x{v:08X}"})()
