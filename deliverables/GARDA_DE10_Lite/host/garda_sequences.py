"""Hardware sequences for the GARDA Control Center.

Every step returns pass/fail from values actually received from the FPGA; a
failed required step stops the sequence. Nothing here fabricates data: when
the link is down, steps fail with the real error.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import garda_protocol as p
import garda_quartus as q
from garda_link import GardaLink

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/neural_24_64_64_4"
TRACE_DIR = ROOT / "traces"
MANIFEST = ROOT / "output/build_manifest.json"
ESTOP_TEST_DELAY_CYCLES = 400_000   # 8 ms after the planner result (lease is 20 ms)


class StepFailed(Exception):
    pass


STEP_TEXT = {
 "check_quartus": ("Check Quartus installation", "Find a Quartus install that can drive the USB-Blaster.",
                   "Mencari Quartus yang bisa memakai USB-Blaster."),
 "verify_sof": ("Verify programming file", "The bitstream must be built for the MAX 10 10M50DAF484C7G and match its build manifest.",
                "Bitstream harus dibuat untuk chip MAX 10 dan cocok dengan manifest build."),
 "detect_blaster": ("Detect USB-Blaster", "Scan the JTAG cable (read-only).", "Memindai kabel JTAG (hanya baca)."),
 "confirm_target": ("Confirm programming target", "Exactly one device, IDCODE 0x031050DD (DE10-Lite MAX 10). Anything else is refused.",
                    "Harus tepat satu chip dengan IDCODE 0x031050DD. Selain itu ditolak."),
 "program": ("Program FPGA over JTAG", "Load the GARDA circuit into the FPGA's configuration memory (volatile, no flash write).",
             "Memuat rangkaian GARDA ke FPGA (sementara, flash tidak diubah)."),
 "check_program": ("Check programmer result", "Quartus must report 'Configuration succeeded'.", "Quartus harus melaporkan 'Configuration succeeded'."),
 "connect_uart": ("Connect UART", "Open the serial port at 115200 baud, 8N1.", "Membuka port serial 115200 baud, 8N1."),
 "identify": ("Identify the FPGA", "Ask the chip who it is. Only a CRC-valid GARDA signature counts as a live FPGA.",
              "Menanyakan identitas chip. Hanya tanda tangan GARDA dengan CRC valid yang dihitung."),
 "safe_reset": ("Safe reset", "Return the hardware to its power-on safe state: motors off, nothing configured.",
                "Mengembalikan hardware ke kondisi aman: motor mati, belum dikonfigurasi."),
 "crc_test": ("Corrupted-message test", "Send a message with a wrong checksum. GARDA must ignore it and lock out until reset.",
              "Mengirim pesan dengan checksum salah. GARDA harus menolak dan mengunci sampai reset."),
 "neural": ("Sensor data and neural inference", "Send 24 sensor values; the on-chip neural network (24-64-64-4) must reproduce the reference outputs bit for bit.",
            "Mengirim 24 nilai sensor; neural network di chip harus menghasilkan output referensi persis sama."),
 "planner": ("Plan a motion", "Upload a 128x128 cost map, lock the speed limits and let 4 hardware tiles score 512 trajectories.",
             "Mengunggah peta 128x128, mengunci batas kecepatan, lalu 4 tile hardware menilai 512 lintasan."),
 "safety_gate": ("Hardware safety intervention", "While motion is permitted, an E-stop fires. The capture register shows when motor permission was removed.",
                 "Saat gerak diizinkan, E-stop dipicu. Register capture mencatat kapan izin motor dicabut."),
 "estop": ("E-stop behaviour", "A host E-stop latches: motors stay at zero until a deliberate reset.",
           "E-stop dari host terkunci: motor tetap nol sampai reset yang disengaja."),
 "watchdog": ("Link-loss watchdog", "If the computer goes silent, GARDA stops the motors on its own.",
              "Jika komputer berhenti mengirim, GARDA menghentikan motor sendiri."),
 "summary": ("Verification summary", "All results above were read back from the FPGA.", "Semua hasil di atas dibaca langsung dari FPGA."),
}

PROGRAM_STEPS = ["check_quartus", "verify_sof", "detect_blaster", "confirm_target", "program", "check_program"]
DEMO_STEPS = ["connect_uart", "identify", "safe_reset", "crc_test", "neural", "planner", "safety_gate", "estop", "watchdog", "summary"]


class Runner:
    def __init__(self, link: GardaLink):
        self.link = link
        self.lock = threading.Lock()
        self.state = {"name": None, "mode": None, "running": False, "steps": [], "result": None, "progress": None}
        self.ctx = {}
        self.abort = threading.Event()

    # ------------------------------------------------------------------ API
    def start(self, name: str, steps: list[str], ctx: dict) -> bool:
        with self.lock:
            if self.state["running"]:
                return False
            self.abort.clear()
            self.ctx = ctx
            self.state = {"name": name, "mode": "LIVE HARDWARE", "running": True, "result": None, "progress": None,
                          "started": time.time(),
                          "steps": [{"id": s, "title": STEP_TEXT[s][0], "explain": STEP_TEXT[s][1], "explain_id": STEP_TEXT[s][2],
                                     "status": "pending", "detail": "", "data": {}} for s in steps]}
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def snapshot(self) -> dict:
        return json.loads(json.dumps(self.state, default=str))

    # -------------------------------------------------------------- engine
    def _run(self):
        self.link.capture = []
        ok_all = True
        for step in self.state["steps"]:
            if self.abort.is_set():
                step["status"], step["detail"] = "skipped", "aborted by operator"
                ok_all = False
                continue
            if not ok_all:
                step["status"], step["detail"] = "skipped", "not run: an earlier required step failed"
                continue
            step["status"] = "running"
            self.state["progress"] = None
            try:
                detail, data = getattr(self, "s_" + step["id"])(step)
                step["status"], step["detail"], step["data"] = "pass", detail, data or {}
            except (StepFailed, p.ProtocolError, OSError) as e:
                step["status"], step["detail"] = "fail", str(e)
                ok_all = False
        self.state["result"] = "PASS" if ok_all else "FAIL"
        self.state["running"] = False
        self.state["finished"] = time.time()
        self._save_trace()

    def _save_trace(self):
        frames = self.link.capture or []
        self.link.capture = None
        if not any(f.get("kind") == "frame" and f.get("result") == "OK" for f in frames):
            return  # nothing came from hardware: do not create a "recorded hardware trace"
        TRACE_DIR.mkdir(exist_ok=True)
        ident = self.link.ident or {}
        trace = {"provenance": "RECORDED HARDWARE TRACE", "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "port": self.link.port, "baud": self.link.baud, "fpga_build_id": ident.get("build_id"),
                 "sequence": self.state["name"], "result": self.state["result"], "steps": self.state["steps"], "frames": frames}
        name = time.strftime("hw_%Y%m%d_%H%M%S.json")
        (TRACE_DIR / name).write_text(json.dumps(trace, indent=1, default=str))
        self.state["trace_file"] = name

    def _need_link(self):
        if not self.link.connected:
            raise StepFailed("UART not connected")

    def _status(self) -> dict:
        return p.decode_status(self.link.transact(p.OP_STATUS).value)

    def _safe_reset(self):
        try:
            self.link.transact(p.OP_SAFE_RESET, p.SAFE_RESET_MAGIC)
        except p.ProtocolError:
            pass  # a latched protocol fault suppresses the reply; the sniffer still resets
        time.sleep(0.05)
        self.link.ser.reset_input_buffer()

    # ----------------------------------------------------------- program steps
    def s_check_quartus(self, step):
        b = q.find_quartus_bin(for_compile=False)
        if not b:
            raise StepFailed("Quartus Programmer not found (set GARDA_QUARTUS_BIN)")
        self.ctx["qbin"] = b
        return f"{b} ({q.edition(b)})", {"bin": str(b)}

    def s_verify_sof(self, step):
        ok, msg, info = q.verify_sof(Path(self.ctx["sof"]), MANIFEST)
        if not ok:
            raise StepFailed(msg)
        man = info.get("manifest", {})
        if man.get("sof_file") == info["file"] and not man.get("release"):
            msg += "  WARNING: build did not meet timing at every corner"
        return msg, {"sha256": info["sha256"]}

    def s_detect_blaster(self, step):
        scan = q.jtag_scan(self.ctx.get("qbin"))
        self.ctx["scan"] = scan
        if scan["state"] != "USB_BLASTER_DETECTED":
            raise StepFailed({"BOARD_DISCONNECTED": "no USB-Blaster found: connect the DE10-Lite USB cable",
                              "CHAIN_BROKEN": "USB-Blaster found but JTAG chain broken: is the board powered on?"}
                             .get(scan["state"], scan["state"]))
        return scan["raw"].replace("\n", "  "), {}

    def s_confirm_target(self, step):
        ok, msg, cable = q.verify_target(self.ctx["scan"])
        if not ok:
            raise StepFailed(msg)
        if self.ctx.get("confirm_idcode", "").upper() != q.EXPECTED_IDCODE:
            raise StepFailed("operator confirmation of IDCODE 031050DD missing")
        self.ctx["cable"] = cable
        return msg + " - confirmed by operator", {}

    def s_program(self, step):
        self.ctx["pgm"] = q.program_sof(Path(self.ctx["sof"]), self.ctx["cable"], self.ctx.get("qbin"))
        last = [l for l in self.ctx["pgm"].get("log", "").splitlines() if "209" in l or "Error" in l]
        if not self.ctx["pgm"]["ok"]:
            raise StepFailed("quartus_pgm reported failure: " + " | ".join(last[-3:] or [self.ctx["pgm"].get("error", "")]))
        return " | ".join(l.strip() for l in last[-3:]), {}

    def s_check_program(self, step):
        if not self.ctx.get("pgm", {}).get("ok"):
            raise StepFailed("programming not verified - stopping before any hardware-dependent step")
        time.sleep(0.3)
        return "Configuration succeeded (exit code 0)", {}

    # -------------------------------------------------------------- demo steps
    def s_connect_uart(self, step):
        if not self.link.connected:
            port = self.ctx.get("port")
            if not port:
                raise StepFailed("no serial port selected")
            r = self.link.connect(port, self.ctx.get("baud", 115200))
            if not r["ok"]:
                raise StepFailed(r["error"])
        return f"{self.link.port} @ {self.link.baud} 8N1", {}

    def s_identify(self, step):
        self._need_link()
        try:
            info = self.link.identify()
        except p.ProtocolError:
            self._safe_reset()            # a stale protocol fault (e.g. cable plugged in live) blocks replies
            info = self.link.identify()
        man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
        match = man.get("build_id") == info["build_id"]
        info["manifest_build_id"] = man.get("build_id")
        info["build_matches_manifest"] = match
        return (f"GARDA DE10-Lite interface v{info.get('interface_version', '?')}, build {info['build_id']}"
                f"{' (matches build manifest)' if match else ' (differs from local build manifest)'}, "
                f"{info['baud']} baud, {info['clock_hz'] // 1_000_000} MHz"), info

    def s_safe_reset(self, step):
        self._need_link()
        self._safe_reset()
        st = self._status()
        if st["protocol_fault"] or st["invalid_command"] or st["motor_enable"]:
            raise StepFailed(f"not in a clean safe state after reset: {st}")
        return f"motor_enable=0, fault {st['fault_code']} ({st['fault_text']})", st

    def s_crc_test(self, step):
        self._need_link()
        try:
            self.link.transact(p.OP_STATUS, 0, corrupt_crc=True)
            raise StepFailed("FPGA answered a corrupted frame")
        except p.ProtocolError:
            pass
        try:
            self.link.transact(p.OP_STATUS)
            raise StepFailed("FPGA kept answering after a CRC error (expected lockout)")
        except p.ProtocolError:
            pass
        self._safe_reset()
        st = self._status()
        if st["protocol_fault"]:
            raise StepFailed("safe reset did not clear the protocol fault")
        return "corrupted frame rejected, link locked out, safe reset recovered it", {}

    def s_neural(self, step):
        self._need_link()
        ins, gold = p.read_mem(ASSETS / "test_inputs.mem"), p.read_mem(ASSETS / "test_outputs.mem")
        results = []
        for n in range(3):
            for i, x in enumerate(ins[n * 24:n * 24 + 24]):
                self.link.transact(p.OP_NN_LOAD, i | (x << 8), quiet=i not in (0, 23))
            self.link.transact(p.OP_NN_START)
            deadline = time.monotonic() + 1
            while True:
                nn = p.decode_nn(self.link.transact(p.OP_NN_READ, 0).value)
                if nn["fault"]:
                    raise StepFailed(f"neural core fault on vector {n}")
                if nn["done"]:
                    break
                if time.monotonic() > deadline:
                    raise StepFailed("neural inference timeout")
            got = [self.link.transact(p.OP_NN_READ, i).value & 0xFFFF for i in range(4)]
            exp = gold[n * 4:n * 4 + 4]
            results.append({"vector": n, "outputs": [p.signed(g, 16) / 256 for g in got], "match": got == exp})
            if got != exp:
                raise StepFailed(f"vector {n}: FPGA {got} != reference {exp}")
        cyc = self.link.transact(p.OP_NN_CYCLES).value
        mhz = (self.link.ident or {}).get("clock_hz", 45_000_000) / 1e6
        return f"3 vectors x 4 outputs bit-exact; {cyc} cycles = {cyc / mhz:.1f} us per inference at {mhz:g} MHz", {"vectors": results, "cycles": cyc}

    def s_planner(self, step):
        self._need_link()
        lk = self.link
        lk.transact(p.OP_CFG_WRITE, p.DEFAULT_CONFIG)
        lk.transact(p.OP_CFG_LOCK)
        lk.transact(p.OP_MAP_BEGIN, 1)
        t0 = time.monotonic()
        for i in range(16384):
            y, x = i >> 7, i & 127
            cell = 254 if 70 <= y < 74 and 60 <= x < 68 else 0
            st = lk.transact(p.OP_MAP_WRITE, i | (cell << 16), quiet=True).value
            if st & 0x18:
                raise StepFailed(f"protocol fault while writing cell {i}")
            if i % 256 == 0:
                self.state["progress"] = {"label": "map upload", "done": i, "total": 16384}
            if self.abort.is_set():
                raise StepFailed("aborted")
        self.state["progress"] = {"label": "map upload", "done": 16384, "total": 16384}
        upload_s = time.monotonic() - t0
        lk.transact(p.OP_ESTOP_TEST, ESTOP_TEST_DELAY_CYCLES)
        lk.transact(p.OP_MAP_COMMIT)
        lk.transact(p.OP_RUN)
        st = self._status()
        tries = 0
        while not st["done"] and st["fault_code"] in (9, 0) and tries < 5:
            st = self._status(); tries += 1
        cmd = p.decode_command(lk.transact(p.OP_COMMAND).value)
        lat = lk.transact(p.OP_LATENCY).value
        self.ctx["planner_status"] = st
        if not st["done"] and not st["motor_enable"]:
            raise StepFailed(f"planner did not produce a result: fault {st['fault_code']} ({st['fault_text']})")
        live = "observed motor_enable=1 live" if st["motor_enable"] else "result reached (permission window passed before the host poll)"
        mhz = (lk.ident or {}).get("clock_hz", 45_000_000) / 1e6
        return (f"map uploaded in {upload_s:.1f} s; planner {lat} cycles = {lat / mhz:.1f} us; {live}; "
                f"command v={cmd['v']} omega={cmd['omega']}"), {"status": st, "command": cmd, "latency_cycles": lat}

    def s_safety_gate(self, step):
        self._need_link()
        time.sleep(0.03)
        cap = p.decode_capture(self.link.transact(p.OP_ESTOP_CAPTURE).value)
        st = self._status()
        if not cap["valid"]:
            raise StepFailed(f"no E-stop capture recorded: {cap}")
        if not cap["enable_before"]:
            raise StepFailed(f"motor permission was not active when the E-stop fired: {cap}")
        if st["motor_enable"] or st["fault_code"] != 2:
            raise StepFailed(f"after E-stop expected enable=0 fault 2, got {st}")
        return (f"before E-stop: motor_enable=1 v={cap['v_before']} omega={cap['omega_before']}; "
                f"after: motor_enable=0, fault 2; disabled {cap['latency_cycles']} clock edges after the stop "
                f"({'same clock cycle, < 23 ns at 45 MHz' if cap['latency_cycles'] == 0 else str(round(cap['latency_cycles'] * 22.2)) + ' ns'})"), cap

    def s_estop(self, step):
        self._need_link()
        self._safe_reset()
        self.link.transact(p.OP_HOST_ESTOP)
        ext = p.decode_ext_status(self.link.transact(p.OP_EXT_STATUS).value)
        st = self._status()
        if not ext["host_estop"] or st["motor_enable"] or st["fault_code"] != 2:
            raise StepFailed(f"host E-stop not latched: {ext}")
        time.sleep(0.2)
        st2 = self._status()
        if st2["fault_code"] != 2:
            raise StepFailed("E-stop did not stay latched")
        self._safe_reset()
        return "E-stop latched (fault 2, motors zero), still latched after 200 ms, cleared only by deliberate safe reset", ext

    def s_watchdog(self, step):
        self._need_link()
        self.link.transact(p.OP_WATCHDOG, 20)      # 20 ms
        time.sleep(0.12)
        st = self._status()
        ext = p.decode_ext_status(self.link.transact(p.OP_EXT_STATUS).value)
        if st["fault_code"] != 3 or not ext["watchdog_trip"]:
            raise StepFailed(f"watchdog did not trip: {st}")
        self._safe_reset()
        return "host silent for 120 ms > 20 ms timeout: protective stop (fault 3) latched by hardware", ext

    def s_summary(self, step):
        done = [s for s in self.state["steps"] if s["status"] == "pass"]
        c = self.link.counters
        return (f"{len(done)} steps passed; UART TX {c['tx_frames']} / RX {c['rx_frames']} frames, "
                f"{c['timeouts']} timeouts ({'incl. the intentional CRC test' if c['timeouts'] else 'none'}), "
                f"{c['crc_errors']} CRC errors"), dict(c)
