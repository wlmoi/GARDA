#!/usr/bin/env python3
"""GARDA FPGA Control Center - local hardware bridge.

  python host/garda_service.py [--port 8770] [--serial /dev/ttyUSB0]

Serves the dashboard and a small JSON API on 127.0.0.1 ONLY. A static website
(Vercel / GitHub Pages) cannot reach Quartus or the USB-Blaster; this process is
the local bridge, and it exposes only the fixed operations below - there is no
shell, no arbitrary file path and no arbitrary opcode.

Protection against other web pages in the same browser:
  * Host header must be 127.0.0.1:<port> or localhost:<port> (DNS rebinding);
  * POST needs the per-launch token embedded in the served page and, when an
    Origin header is present, it must be this server's origin (CSRF).
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garda_protocol as p  # noqa: E402
import garda_quartus as q  # noqa: E402
from garda_link import GardaLink, list_ports  # noqa: E402
from garda_sequences import DEMO_STEPS, MANIFEST, PROGRAM_STEPS, ROOT, TRACE_DIR, Runner  # noqa: E402
from garda_physai import PhysAI  # noqa: E402

DASH = ROOT / "dashboard"
SIM_TRACE = DASH / "data/simulation_trace.json"
TOKEN = secrets.token_urlsafe(24)
link = GardaLink()
runner = Runner(link)
physai = PhysAI(link)
jtag = {"state": "NOT_SCANNED", "cables": [], "raw": "", "t": None}
fpga = {"state": "BOARD DISCONNECTED", "detail": ""}
lock = threading.Lock()
SAFE_COMMANDS = {
    "status": (p.OP_STATUS, 0), "ext_status": (p.OP_EXT_STATUS, 0), "ident": (p.OP_IDENT, 0),
    "counters": (p.OP_COUNTERS, 0), "capture": (p.OP_ESTOP_CAPTURE, 0), "command": (p.OP_COMMAND, 0),
    "estop": (p.OP_HOST_ESTOP, 0), "safe_reset": (p.OP_SAFE_RESET, p.SAFE_RESET_MAGIC),
    "watchdog_off": (p.OP_WATCHDOG, 0), "events": (p.OP_EVENTS, 0), "last_fault": (p.OP_LAST_FAULT, 0),
    "ports": (p.OP_PORT_STATS, 0), "port_info": (p.OP_PORT_INFO, 0), "board_io": (p.OP_BOARD_IO, 0),
}


def default_sof() -> Path | None:
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    if man.get("sof_file") and (ROOT / "output" / man["sof_file"]).exists():
        return ROOT / "output" / man["sof_file"]
    sofs = sorted((ROOT / "output").glob("*.sof"), key=lambda f: f.stat().st_mtime, reverse=True)
    return sofs[0] if sofs else None


scan_lock = threading.Lock()


def scan_jtag():
    with scan_lock:            # never run two jtagconfig processes at once
        s = q.jtag_scan()
    with lock:
        jtag.update(s, t=time.time())
        ok, msg, _ = q.verify_target(s)
        if runner.state.get("running") and any(st["id"] == "program" and st["status"] == "running" for st in runner.state["steps"]):
            return
        if s["state"] == "USB_BLASTER_DETECTED":
            fpga.update(state="READY TO PROGRAM" if ok and default_sof() else "USB-BLASTER DETECTED", detail=msg)
        elif s["state"] == "CHAIN_BROKEN":
            fpga.update(state="USB-BLASTER DETECTED", detail="cable found, JTAG chain broken: board powered off?")
        else:
            fpga.update(state="BOARD DISCONNECTED", detail=s.get("error") or s["state"])


def fpga_state_from_runner():
    steps = {s["id"]: s for s in runner.state.get("steps", [])}
    if "program" in steps:
        st = steps["program"]["status"]
        if st == "running":
            fpga.update(state="PROGRAMMING", detail="quartus_pgm running")
        elif st == "pass":
            fpga.update(state="PROGRAMMING SUCCESSFUL", detail=steps["program"]["detail"])
        elif st == "fail":
            fpga.update(state="PROGRAMMING FAILED", detail=steps["program"]["detail"])


def state() -> dict:
    fpga_state_from_runner()
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    sof = default_sof()
    if not sof or man.get("sof_file") != sof.name:
        man = {}   # never attribute one build's reports to a different programming file
    ports = list_ports()
    if not link.connected:
        link.state = "PORT DETECTED" if ports else "PORT NOT FOUND"
    return {
        "fpga": dict(fpga), "jtag": {k: jtag.get(k) for k in ("state", "cables", "raw", "t")},
        "uart": {"state": link.state.replace("_", " "), "port": link.port if link.connected else None,
                 "baud": link.baud, "connected": link.connected, "ident": link.ident, "counters": link.counters,
                 "last_rx": link.last_rx_time, "ports": ports},
        "engineering": {"device": man.get("device", q.EXPECTED_DEVICE), "programming_file": sof.name if sof else None,
                        "build_id": man.get("build_id"), "build_time_utc": man.get("build_time_utc"),
                        "quartus_version": man.get("quartus_version"), "clock_hz": man.get("clock_hz", 50_000_000),
                        "logic_elements": man.get("logic_elements"), "memory_bits": man.get("memory_bits"),
                        "multipliers": man.get("multipliers_9bit"), "timing_met": man.get("timing_met"),
                        "worst_slack_ns": man.get("worst_slack_ns"), "fmax_mhz": man.get("fmax_mhz_worst_corner"),
                        "timing_corners": man.get("timing_corners"), "release": man.get("release"),
                        "sof_sha256": man.get("sof_sha256")},
        "log": list(link.log)[-120:], "sequence": runner.snapshot(),
        "traces": sorted((f.name for f in TRACE_DIR.glob("hw_*.json")), reverse=True) if TRACE_DIR.exists() else [],
        "simulation_trace": SIM_TRACE.exists(), "server_time": time.time(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "GARDA-ControlCenter/1"

    def log_message(self, fmt, *args):  # keep the console readable
        pass

    def _host_ok(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, default=str).encode())

    def do_GET(self):
        if not self._host_ok():
            return self._send(HTTPStatus.FORBIDDEN, b"forbidden host", "text/plain")
        path = self.path.split("?")[0]
        if path == "/api/state":
            return self._json(state())
        if path == "/api/physai":
            s = physai.snapshot()
            s["uart"] = {"state": link.state.replace("_", " "), "connected": link.connected, "ident": link.ident,
                         "counters": link.counters}
            return self._json(s)
        if path == "/api/sim-trace":
            return self._send(200, SIM_TRACE.read_bytes()) if SIM_TRACE.exists() else self._json({"error": "no simulation trace"}, 404)
        if path == "/api/hw-trace":
            name = self.path.split("name=")[-1]
            f = TRACE_DIR / name
            if not name.startswith("hw_") or "/" in name or "\\" in name or not f.exists():
                return self._json({"error": "unknown trace"}, 404)
            return self._send(200, f.read_bytes())
        rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        f = (DASH / rel).resolve()
        if DASH.resolve() not in f.parents or not f.is_file():
            return self._send(404, b"not found", "text/plain")
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
                 ".png": "image/png", ".woff2": "font/woff2", ".json": "application/json"}.get(f.suffix, "application/octet-stream")
        body = f.read_bytes()
        if f.suffix == ".html":
            body = body.replace(b"__GARDA_TOKEN__", TOKEN.encode())
        self._send(200, body, ctype)

    def do_POST(self):
        port = self.server.server_address[1]
        origin = self.headers.get("Origin")
        if (not self._host_ok() or self.headers.get("X-GARDA-Token") != TOKEN
                or (origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"))):
            return self._json({"ok": False, "error": "forbidden"}, 403)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
        except json.JSONDecodeError:
            return self._json({"ok": False, "error": "bad json"}, 400)
        path = self.path
        try:
            if path == "/api/scan-jtag":
                scan_jtag()
                return self._json({"ok": True, "jtag": jtag})
            if path == "/api/connect":
                if runner.state.get("running"):
                    return self._json({"ok": False, "error": "sequence running"}, 409)
                r = link.connect(str(body.get("port", "")), int(body.get("baud", 115200)))
                if r["ok"]:
                    try:
                        r["ident"] = link.identify()
                    except p.ProtocolError as e:
                        r["warning"] = f"port open but no valid GARDA response: {e}"
                return self._json(r)
            if path == "/api/disconnect":
                link.disconnect()
                return self._json({"ok": True})
            if path == "/api/command":
                name = body.get("name")
                if name not in SAFE_COMMANDS or runner.state.get("running"):
                    return self._json({"ok": False, "error": "unknown command or sequence running"}, 400)
                op, payload = SAFE_COMMANDS[name]
                if op in p.V2_OPS and (link.ident or {}).get("interface_version", 0) < 2:
                    return self._json({"ok": False, "error": f"{name} needs FPGA interface v2 (program the current build); "
                                       "not sent, because an older image would latch invalid_command"})
                try:
                    r = link.transact(op, payload)
                    return self._json({"ok": True, "value": r.value})
                except p.ProtocolError as e:
                    return self._json({"ok": False, "error": str(e)})
            if path == "/api/run":
                seq = body.get("sequence")
                sof = default_sof()
                ctx = {"port": body.get("port") or link.port, "baud": int(body.get("baud", 115200)),
                       "sof": str(sof) if sof else "", "confirm_idcode": str(body.get("confirm_idcode", ""))}
                if physai.running:
                    return self._json({"ok": False, "error": "stop the Physical AI simulator first"}, 409)
                if seq == "program":
                    if ctx["confirm_idcode"].upper() != q.EXPECTED_IDCODE:
                        return self._json({"ok": False, "error": "confirm the detected target (IDCODE 031050DD) to program"}, 400)
                    steps, name = PROGRAM_STEPS, "PROGRAM FPGA"
                elif seq == "program_and_test":
                    if ctx["confirm_idcode"].upper() != q.EXPECTED_IDCODE:
                        return self._json({"ok": False, "error": "type the target IDCODE 031050DD to confirm programming"}, 400)
                    steps, name = PROGRAM_STEPS + DEMO_STEPS, "PROGRAM FPGA & RUN UART TEST"
                elif seq == "demo":
                    steps, name = DEMO_STEPS, "RUN DEMO ONLY"
                elif seq == "judge":
                    steps, name = DEMO_STEPS, "JUDGE DEMO MODE"
                else:
                    return self._json({"ok": False, "error": "unknown sequence"}, 400)
                return self._json({"ok": runner.start(name, steps, ctx)})
            if path == "/api/physai/start":
                if runner.state.get("running"):
                    return self._json({"ok": False, "error": "a demo sequence is using the FPGA"}, 409)
                ok, msg = physai.start(str(body.get("backend", "model")), str(body.get("inputs", "golden")))
                return self._json({"ok": ok, "error": None if ok else msg})
            if path == "/api/physai/stop":
                physai.stop()
                return self._json({"ok": True})
            if path == "/api/physai/estop":
                try:
                    physai.estop()
                    return self._json({"ok": True})
                except p.ProtocolError as e:
                    return self._json({"ok": False, "error": f"E-stop not acknowledged: {e}. Press KEY1."})
            if path == "/api/physai/reset":
                physai.safe_reset()
                return self._json({"ok": True})
            if path == "/api/abort":
                runner.abort.set()
                return self._json({"ok": True})
        except Exception as e:  # noqa: BLE001 - report, never crash the bridge
            return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
        return self._json({"ok": False, "error": "unknown endpoint"}, 404)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--serial", help="connect to this serial port at start-up (e.g. COM5 or /dev/ttyUSB0)")
    args = ap.parse_args()
    def jtag_watch():          # keep the FPGA status card current (read-only jtagconfig)
        while True:
            if not runner.state.get("running"):
                try:
                    scan_jtag()
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(10)
    threading.Thread(target=jtag_watch, daemon=True).start()

    def uart_watch():          # auto-reconnect: adapter re-plugged / USB re-enumerated / latched protocol fault
        bad_since = None
        while True:
            time.sleep(2)
            if runner.state.get("running") or physai.running or not link.port:
                bad_since = None
                continue
            healthy = link.connected and link.state == "FPGA_RESPONDING"
            if healthy:
                bad_since = None
                continue
            bad_since = bad_since or time.time()
            if link.connected and time.time() - bad_since < 3:   # give a live-but-slow link a moment
                continue
            port = link.port
            try:
                # Reopen + IDENT only. Never an automatic reset: that could silently clear a latched
                # host E-stop. A silent FPGA (latched protocol fault) needs a deliberate SAFE RESET.
                if link.connect(port, link.baud)["ok"]:
                    link.identify()
                    bad_since = None
            except Exception:  # noqa: BLE001 - keep trying quietly
                pass
    if args.serial:
        link.port = args.serial
    threading.Thread(target=uart_watch, daemon=True).start()   # connects --serial in the background
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"GARDA Control Center on http://127.0.0.1:{args.port}/  (localhost only, Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        link.disconnect()


if __name__ == "__main__":
    main()
