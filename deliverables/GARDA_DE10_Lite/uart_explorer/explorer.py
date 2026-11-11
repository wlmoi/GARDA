"""GARDA UART Explorer backend: serial -> packet decoder -> event stream (SSE) -> browser.

Stdlib HTTP server + pyserial (only needed for LIVE). Modes: LIVE, SIMULATION, RECORDED.
The serial path is synchronous and independent of rendering: subscribers get bounded queues and
may lose *display* events; the ring buffer and exports keep everything (up to the ring size).
"""
from __future__ import annotations
import argparse, collections, csv, io, json, os, queue, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import protocol as P

ROOT = Path(__file__).resolve().parent
RING = 20000
RESP_TIMEOUT_S = 0.5   # 8 bytes take ~0.7 ms on the wire; generous allowance for USB-UART latency


def read_mem(path: Path) -> list[int]:
    return [int(x, 16) for line in path.read_text().splitlines() for x in line.split("//")[0].split()]


def _s16(x): return x - 65536 if x & 0x8000 else x


def load_vectors():
    ins, outs = read_mem(ROOT / "data/test_inputs.mem"), read_mem(ROOT / "data/test_outputs.mem")
    n = min(len(ins) // 24, len(outs) // 4)
    return [{"id": i, "inputs": [_s16(x) for x in ins[i*24:i*24+24]],
             "expected": [_s16(x) for x in outs[i*4:i*4+4]]} for i in range(n)]


class SimDevice:
    """SOFTWARE MODEL of the protocol contract (not the RTL). Never presented as a connected FPGA."""
    def __init__(self):
        self.rom = read_mem(ROOT / "data/bram_unified_weights.mem")
        self.vectors = load_vectors(); self.nn_in = [None] * 24; self.nn_out = [0] * 4
        self.nn_done = False; self.estop = False; self.pfault = False; self.sw = [0, 0, 0, 0]
        self.buf = bytearray(); self.rx = bytearray()

    def write(self, data: bytes):
        self.buf += data
        if len(self.buf) < 8: return
        f, self.buf = bytes(self.buf[:8]), self.buf[8:]
        d = P.decode_request(f)
        if not d["valid"] or not d["payload_ok"]:
            self.pfault = True; return          # RTL: sticky fault, no response
        if self.pfault: return
        self.rx += P.encode_response(d["opcode"], self.reply(d["opcode"], d["payload"]))

    def fault(self):   # same priority as garda_top / safety gate (verified in tests/rtl_cosim/run_io.py)
        if self.estop: return 2                 # KEY1 held
        if self.sw[3]: return 3                 # SW3 protective stop
        if self.sw[2]: return 4                 # SW2 inhibits ready
        return 5                                # no map committed

    def io(self, sw=None, key1=None, key0=None):
        if sw is not None: self.sw = [int(bool(x)) for x in sw]
        if key1 is not None: self.estop = bool(key1)
        if key0:                                # KEY0 = reset: clears sticky fault and NN state
            self.pfault = False; self.nn_done = False; self.nn_in = [None] * 24; self.nn_out = [0] * 4; self.buf.clear(); self.rx.clear()

    def status(self):
        return (self.fault() << 8) | (4 if self.nn_done else 0)

    def reply(self, op, pl):
        if op == 8: return self.rom[pl] if pl < len(self.rom) else 0
        if op == 10: self.nn_in[pl & 31] = (pl >> 8) & 0xFFFF; return self.status()
        if op == 11:
            for v in self.vectors:
                if [x & 0xFFFF for x in v["inputs"]] == self.nn_in:
                    self.nn_out = [x & 0xFFFF for x in v["expected"]]
            self.nn_done = True; return self.status()
        if op == 12: return self.nn_out[pl & 3] | (int(self.nn_done) << 16)
        if op == 13: return 18192
        if op == 14: return 0
        if op == 15: return 0
        if op == 16: return self.fault()
        return self.status()

    def flush(self): pass
    def read(self, n): out = bytes(self.rx[:n]); del self.rx[:n]; return out


class Hub:
    def __init__(self):
        self.ring = collections.deque(maxlen=RING); self.seq = 0; self.lock = threading.Lock()
        self.subs: list[queue.Queue] = []
        self.mode = "NONE"; self.port = None; self.baud = P.BAUD; self.dev = None
        self.serial_lock = threading.Lock()
        self.req_id = 0; self.provenance = {}; self.demo_thread = None
        self.demo_stop = threading.Event(); self.replay_stop = threading.Event()
        self.demo = {"state": "idle", "steps": []}

    # ---- event pipeline
    def emit(self, type_, source, direction=None, raw=None, decoded=None, validation=None,
             request_id=None, note=None, verified=True):
        with self.lock:
            self.seq += 1
            ev = {"id": self.seq, "type": type_, "source": source, "mode": self.mode, "ts": time.time(),
                  "t_ns": time.perf_counter_ns(), "direction": direction,
                  "raw": raw.hex(" ").upper() if raw else None, "decoded": decoded,
                  "validation": validation, "request_id": request_id, "note": note, "verified": verified}
            self.ring.append(ev)
            for q in list(self.subs):
                try: q.put_nowait(ev)
                except queue.Full:                 # slow UI: drop a display event, never block serial
                    try: q.get_nowait(); q.put_nowait(ev)
                    except Exception: pass
        return ev

    def subscribe(self, since=0):
        q = queue.Queue(maxsize=2000)
        with self.lock:
            for e in self.ring:
                if e["id"] > since:
                    try: q.put_nowait(e)
                    except queue.Full: break
            self.subs.append(q)
        return q

    # ---- connection
    def connect(self, mode, port=None, baud=P.BAUD):
        self.disconnect()
        self.mode = mode; self.baud = baud; self.provenance = {}
        if mode == "SIMULATION":
            self.dev = SimDevice(); self.port = "SOFTWARE-SIMULATION"
            self.emit("PORT_OPENED", "SIM", note="SIMULATION: software protocol model. No FPGA is connected.", verified=False)
        elif mode == "LIVE":
            try:
                import serial
            except ImportError:
                self.mode = "NONE"; raise RuntimeError("LIVE HARDWARE UNAVAILABLE: pyserial not installed (pip install pyserial)")
            try:
                self.dev = serial.Serial(port, baud, timeout=0.01, write_timeout=1)
                self.dev.reset_input_buffer()
            except Exception as e:
                self.mode = "NONE"
                self.emit("PORT_ERROR", "HOST", note=f"LIVE HARDWARE UNAVAILABLE: {e}", validation="fail")
                raise RuntimeError(f"LIVE HARDWARE UNAVAILABLE: {e}")
            self.port = port
            self.emit("PORT_OPENED", "HOST", note=f"{port} {baud} 8N1 opened (host-side fact; says nothing about FPGA state)")
        else:
            raise ValueError("mode must be LIVE or SIMULATION")

    def disconnect(self):
        self.demo_stop.set(); self.replay_stop.set()
        if self.dev is not None:
            try:
                if hasattr(self.dev, "close"): self.dev.close()
            except Exception: pass
            self.emit("PORT_CLOSED", "HOST" if self.mode == "LIVE" else "SIM")
        self.dev = None; self.port = None

    # ---- one request/response transaction (never delayed or altered for animation)
    def transact(self, op: int, payload: int = 0, force=False, raw_override: bytes | None = None, timeout=RESP_TIMEOUT_S):
        if self.dev is None:
            raise RuntimeError("LIVE HARDWARE UNAVAILABLE: no port open")
        src = "SIM" if self.mode == "SIMULATION" else "HOST"
        if raw_override is None and not force and not P.payload_ok(op, payload):
            raise ValueError(f"payload rejected by the RTL's payload_ok for op {op}; sending it would latch a sticky fault until KEY0")
        with self.serial_lock:
            self.req_id += 1; rid = self.req_id
            frame = raw_override if raw_override is not None else P.encode_request(op, payload)
            req = P.decode_request(frame)
            self.emit("TX_STARTED", src, "HOST->FPGA", frame, req, request_id=rid)
            t0 = time.perf_counter_ns(); self.dev.write(frame); t1 = time.perf_counter_ns()
            if hasattr(self.dev, "flush"): self.dev.flush()
            self.emit("TX_COMPLETED", src, "HOST->FPGA", frame,
                      {"write_return_us": (t1 - t0) / 1e3, "wire_time_us": 8 * P.byte_time_us(self.baud)}, request_id=rid)
            buf = bytearray(); deadline = time.perf_counter() + timeout
            while len(buf) < P.FRAME_LEN and time.perf_counter() < deadline:
                b = self.dev.read(P.FRAME_LEN - len(buf))
                if b:
                    buf += b
                    self.emit("RX_DATA_RECEIVED", src, "FPGA->HOST", bytes(b), {"bytes": len(b), "total": len(buf)}, request_id=rid)
                elif self.mode == "SIMULATION":
                    time.sleep(0.0005)
            rtt = (time.perf_counter_ns() - t0) / 1e3
            if len(buf) < P.FRAME_LEN:
                self.emit("COMMAND_TIMEOUT", src, "FPGA->HOST", bytes(buf) or None,
                          {"expected": 8, "received": len(buf), "rtt_us": rtt}, "fail", rid,
                          "No complete response. The RTL latches a sticky protocol fault on bad input; press KEY0 to clear.")
                return {"ok": False, "timeout": True, "request": req, "request_id": rid, "raw": bytes(buf).hex(" ").upper(), "rtt_us": rtt}
            resp = P.decode_response(bytes(buf), expect_op=op if raw_override is None else None)
            resp["rtt_us"] = rtt; resp["request_id"] = rid
            self.emit("FRAME_DECODED", src, "FPGA->HOST", bytes(buf), resp, "ok" if resp["valid"] else "fail", rid)
            self.emit("CRC_VALID" if resp["crc_ok"] else "CRC_ERROR", src, "FPGA->HOST", bytes(buf),
                      {"crc_rx": resp["crc_tx"], "crc_calc": resp["crc_calc"]}, "ok" if resp["crc_ok"] else "fail", rid)
            if resp["valid"]:
                self.emit("FPGA_RESPONSE_RECEIVED", src, "FPGA->HOST", bytes(buf), resp, "ok", rid,
                          note=f"host-side RTT {rtt:.0f} us (includes USB-UART latency; not RTL cycle latency)")
                f = resp["fields"]
                if "protocol_fault" in f:
                    ok = not f["protocol_fault"] and not f["invalid_command"]
                    self.emit("COMMAND_ACCEPTED" if ok else "COMMAND_REJECTED", src, None, None, f, "ok" if ok else "warn", rid,
                              note="INFERRED from status bits protocol_fault/invalid_command in the response.", verified=False)
                    if f["fault_code"] == 2:
                        self.emit("ESTOP_CONFIRMED", src, None, None, f, "ok", rid,
                                  note="FPGA status reports fault_code 2 (emergency input KEY1)")
            return {"ok": resp["valid"], "request": req, "response": resp, "request_id": rid, "rtt_us": rtt}

    # ---- one-click demo
    def start_demo(self):
        if self.demo_thread and self.demo_thread.is_alive(): raise RuntimeError("demo already running")
        if self.dev is None:
            raise RuntimeError("LIVE HARDWARE UNAVAILABLE: open a LIVE port, or choose SIMULATION explicitly (labelled, not hardware)")
        self.demo_stop.clear()
        self.demo = {"state": "running", "mode": self.mode, "steps": [], "started": time.time()}
        self.demo_thread = threading.Thread(target=self._run_demo, daemon=True); self.demo_thread.start()

    def _step(self, name, fn):
        if self.demo_stop.is_set():
            self.demo["steps"].append({"name": name, "verdict": "NOT_RUN", "detail": "stopped by user"}); return
        self.emit("DEMO_STEP", "DEMO", note=name, decoded={"name": name, "state": "start"})
        try: verdict, detail = fn()
        except Exception as e: verdict, detail = "FAIL", str(e)
        self.demo["steps"].append({"name": name, "verdict": verdict, "detail": detail})
        self.emit("DEMO_STEP", "DEMO", note=name, decoded={"name": name, "state": "done", "verdict": verdict, "detail": detail},
                  validation={"PASS": "ok", "FAIL": "fail"}.get(verdict, "warn"))

    def _run_demo(self):
        vec = load_vectors()[0]; mem = read_mem(ROOT / "data/bram_unified_weights.mem")

        def ping():
            r = self.transact(7)
            if not r["ok"]: return "FAIL", "timeout" if r.get("timeout") else "; ".join(r["response"]["errors"])
            f = r["response"]["fields"]
            return "PASS", f"valid status, host RTT {r['rtt_us']:.0f} us, fault_code={f['fault_code']} ({f['fault_reason']})"

        def rom():
            r = self.transact(8, 0)
            if not r["ok"]: return "FAIL", "no valid ROM response"
            got, exp = r["response"]["fields"]["rom_word"], mem[0]
            return ("PASS" if got == exp else "FAIL"), f"ROM[0]=0x{got:04X}, reference 0x{exp:04X}"

        def nn():
            for i, x in enumerate(vec["inputs"]):
                if not self.transact(10, i | ((x & 0xFFFF) << 8))["ok"]: return "FAIL", f"input {i} not acknowledged"
            if not self.transact(11)["ok"]: return "FAIL", "NN start not acknowledged"
            for _ in range(200):
                r = self.transact(12, 0)
                if not r["ok"]: return "FAIL", "NN poll failed"
                f = r["response"]["fields"]
                if f["fault"]: return "FAIL", "neural fault flag set"
                if f["done"]: break
                time.sleep(0.01)
            else:
                return "FAIL", "NN done never asserted"
            got = [self.transact(12, i)["response"]["fields"]["result_q8_8"] for i in range(4)]
            lat = self.transact(13)["response"]["fields"]["count"]
            return ("PASS" if got == vec["expected"] else "FAIL"), \
                f"outputs {got} vs reference {vec['expected']}; RTL latency {lat} cycles (separate from host RTT)"

        def safety():
            r, c = self.transact(7), self.transact(14)
            if not (r["ok"] and c["ok"]): return "FAIL", "no valid status/command response"
            f, g = r["response"]["fields"], c["response"]["fields"]
            self.demo["safety"] = {"enable": f["enable"], "fault_code": f["fault_code"], "fault_reason": f["fault_reason"],
                                   "v": g["v_command"], "omega": g["omega_command"]}
            return "PASS", f"gate reports enable={f['enable']} fault={f['fault_code']} final v={g['v_command']} omega={g['omega_command']} (no map committed in this demo, so fault 5 is the expected idle state)"

        def estop():
            sim = self.mode == "SIMULATION"
            if sim: self.dev.estop = True
            else:
                self.emit("DEMO_STEP", "DEMO", note="PRESS AND HOLD KEY1 (E-stop) within 15 s. Bench-safe: disconnect actuators.",
                          decoded={"name": "estop", "state": "prompt"}, validation="warn")
            end = time.time() + (2 if sim else 15)
            try:
                while time.time() < end and not self.demo_stop.is_set():
                    r, c = self.transact(7), self.transact(14)
                    if r["ok"] and c["ok"] and r["response"]["fields"]["fault_code"] == 2:
                        f, g = r["response"]["fields"], c["response"]["fields"]
                        zero = g["v_command"] == 0 and g["omega_command"] == 0 and not f["enable"]
                        self.demo["safety"] = {"enable": f["enable"], "fault_code": 2, "fault_reason": P.FAULT_CODES[2], "v": g["v_command"], "omega": g["omega_command"]}
                        return ("PASS" if zero else "FAIL"), f"fault_code=2 reported; permitted v={g['v_command']} omega={g['omega_command']} enable={f['enable']}"
                    time.sleep(0.1)
            finally:
                if sim: self.dev.estop = False
            return "NOT_VERIFIED", "KEY1 not observed asserted; E-stop behaviour NOT verified"

        self._step("1 Status request (op 7)", ping)
        self._step("2 ROM read vs reference (op 8)", rom)
        self._step("3 NN test vector 0 vs reference (ops 10-13)", nn)
        self._step("4 Safety gate readout (ops 7, 14)", safety)
        self._step("5 E-stop confirmation (KEY1, operator-assisted)", estop)
        steps = self.demo["steps"]; c = collections.Counter(s["verdict"] for s in steps)
        self.demo["summary"] = dict(c)
        self.demo["overall"] = "PASS" if c.get("PASS") == len(steps) else ("FAIL" if c.get("FAIL") else "INCOMPLETE")
        self.demo["state"] = "stopped" if self.demo_stop.is_set() else "done"
        self.emit("DEMO_SUMMARY", "DEMO", decoded=self.demo, note=f"mode={self.mode}")

    # ---- recorded trace replay (original provenance preserved)
    def replay(self, trace: dict, speed=1.0):
        self.demo_stop.set(); self.replay_stop.clear()
        evs = trace["events"]

        def run():
            self.mode = "RECORDED"; self.provenance = trace.get("provenance", {})
            self.emit("TRACE_LOADED", "REPLAY", verified=False,
                      note=f"RECORDED TRACE. Original mode: {self.provenance.get('mode')}. {self.provenance.get('note', '')}")
            if not evs: return
            t0, start = evs[0]["ts"], time.time()
            for e in evs:
                if self.replay_stop.is_set(): break
                wait = (e["ts"] - t0) / max(speed, 0.01) - (time.time() - start)
                if wait > 0: time.sleep(min(wait, 2))
                ne = dict(e); ne["replayed_from_id"] = e["id"]; ne["original_mode"] = e["mode"]; ne["mode"] = "RECORDED"
                with self.lock:
                    self.seq += 1; ne["id"] = self.seq; self.ring.append(ne)
                    for q in list(self.subs):
                        try: q.put_nowait(ne)
                        except queue.Full: pass
        threading.Thread(target=run, daemon=True).start()

    # ---- export
    def export(self, fmt):
        evs = list(self.ring)
        if fmt == "json":
            return "application/json", json.dumps({"provenance": {"mode": self.mode, "port": self.port, "baud": self.baud, "framing": "8N1",
                   "exported": time.time(), "note": "host-side pyserial timestamps; not bit-level captures"}, "events": evs}, indent=1)
        if fmt == "csv":
            s = io.StringIO(); w = csv.writer(s)
            w.writerow(["id", "ts", "mode", "source", "type", "direction", "raw_hex", "request_id", "validation", "note", "decoded_json"])
            for e in evs:
                w.writerow([e["id"], f"{e['ts']:.6f}", e["mode"], e["source"], e["type"], e["direction"], e["raw"],
                            e["request_id"], e["validation"], e["note"], json.dumps(e["decoded"])])
            return "text/csv", s.getvalue()
        if fmt == "hex":
            return "text/plain", "\n".join(f"{e['ts']:.6f} {e['mode']} {e['direction']} {e['raw']}"
                                           for e in evs if e["raw"] and e["type"] in ("TX_STARTED", "RX_DATA_RECEIVED"))
        raise ValueError(fmt)

    def state(self):
        return {"mode": self.mode, "port": self.port, "baud": self.baud, "connected": self.dev is not None,
                "demo": self.demo, "events": self.seq, "pyserial": _has_serial(), "provenance": self.provenance}


def _has_serial():
    try:
        import serial
        return serial.VERSION
    except ImportError:
        return None


def list_ports():
    try:
        from serial.tools import list_ports as lp
        return [{"device": p.device, "description": p.description, "hwid": p.hwid} for p in lp.comports()]
    except ImportError:
        return []


HUB = Hub()
CAPS = {  # what the deployed RTL (garda_uart_top) really supports over UART
    "ping": True, "nn_features_24": True, "nn_features_74": False, "run_inference": True, "read_result": True,
    "read_safety": True, "estop_command": False, "reset_command": False}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/events": return self._sse(int(q.get("since", ["0"])[0]))
        if u.path == "/api/state": return self._json(HUB.state())
        if u.path == "/api/ports": return self._json(list_ports())
        if u.path == "/api/vectors": return self._json(load_vectors())
        if u.path == "/api/traces": return self._json(sorted(p.name for p in (ROOT / "traces").glob("*.json")))
        if u.path == "/api/protocol":
            return self._json({"opcodes": P.OPCODES, "faults": P.FAULT_CODES, "caps": CAPS,
                               "framing": {"baud": P.BAUD, "clks_per_bit": P.CLKS_PER_BIT, "clk_hz": P.CLK_HZ,
                                           "data_bits": 8, "parity": "none", "stop_bits": 1}})
        if u.path == "/api/export":
            fmt = q.get("fmt", ["json"])[0]
            try: ct, body = HUB.export(fmt)
            except ValueError: return self._json({"error": "fmt"}, 400)
            b = body.encode(); self.send_response(200); self.send_header("Content-Type", ct)
            self.send_header("Content-Disposition", f"attachment; filename=garda_uart_trace.{fmt}")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        p = ROOT / "web" / ("index.html" if u.path == "/" else u.path.lstrip("/"))
        if not p.resolve().is_relative_to((ROOT / "web").resolve()) or not p.is_file():
            return self._json({"error": "not found"}, 404)
        b = p.read_bytes(); self.send_response(200)
        ctype = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}.get(p.suffix, "application/octet-stream")
        self.send_header("Content-Type", ctype + "; charset=utf-8"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _sse(self, since):
        q = HUB.subscribe(since)
        self.send_response(200); self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache"); self.end_headers()
        try:
            while True:
                try:
                    e = q.get(timeout=10); self.wfile.write(f"id: {e['id']}\ndata: {json.dumps(e)}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except Exception:
            pass
        finally:
            with HUB.lock:
                if q in HUB.subs: HUB.subs.remove(q)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/connect":
                HUB.connect(body["mode"], body.get("port"), int(body.get("baud", P.BAUD))); return self._json(HUB.state())
            if self.path == "/api/disconnect": HUB.disconnect(); return self._json(HUB.state())
            if self.path == "/api/send":
                return self._json(HUB.transact(int(body["op"]), int(body.get("payload", 0)), force=bool(body.get("force"))))
            if self.path == "/api/demo/start": HUB.start_demo(); return self._json(HUB.state())
            if self.path == "/api/demo/stop": HUB.demo_stop.set(); return self._json(HUB.state())
            if self.path == "/api/sim/io":
                if HUB.mode != "SIMULATION":
                    return self._json({"error": "simulation only; on hardware operate the physical switches/keys"}, 409)
                HUB.dev.io(body.get("sw"), body.get("key1"), body.get("key0"))
                HUB.emit("IO_CHANGED", "SIM", decoded={"sw": HUB.dev.sw, "key1_pressed": HUB.dev.estop, "key0_pressed": bool(body.get("key0"))},
                         note="SIMULATED switch/button input (not a physical board)", verified=False)
                return self._json({"sw": HUB.dev.sw, "key1": HUB.dev.estop})
            if self.path == "/api/sim/estop":
                if HUB.mode != "SIMULATION":
                    return self._json({"error": "simulation only; on hardware use the physical KEY1"}, 409)
                HUB.dev.estop = bool(body.get("on")); return self._json({"estop": HUB.dev.estop})
            if self.path == "/api/replay":
                tr = json.loads((ROOT / "traces" / os.path.basename(body["name"])).read_text())
                HUB.replay(tr, float(body.get("speed", 1))); return self._json({"ok": True})
            if self.path == "/api/clear":
                with HUB.lock: HUB.ring.clear()
                return self._json({"ok": True})
        except (RuntimeError, ValueError, KeyError, FileNotFoundError) as e:
            return self._json({"error": str(e)}, 409)
        self._json({"error": "unknown route"}, 404)


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--port", type=int, default=8780)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H); srv.daemon_threads = True
    print(f"GARDA UART Explorer http://127.0.0.1:{a.port}  (pyserial {_has_serial()}, ports {[p['device'] for p in list_ports()]})")
    try: srv.serve_forever()
    except KeyboardInterrupt: pass


if __name__ == "__main__":
    main()
