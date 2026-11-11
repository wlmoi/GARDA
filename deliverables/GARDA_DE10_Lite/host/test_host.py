#!/usr/bin/env python3
"""Host-side tests (no hardware needed): protocol, link states, sequences, JTAG guards, service security.

  python host/test_host.py -v
"""
import http.client
import json
import struct
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garda_protocol as p  # noqa: E402
import garda_quartus as q  # noqa: E402
from garda_link import GardaLink  # noqa: E402
import garda_sequences as seqmod  # noqa: E402


class FakeFPGA:
    """Minimal serial stand-in. mode: 'ok' answers like the RTL, 'silent' never answers, 'badcrc' corrupts CRC."""
    def __init__(self, mode="ok", ident=p.IDENT_VALUE):
        self.mode, self.ident, self.out, self.timeout = mode, ident, b"", 0.05
        self.fault = 0

    def reset_input_buffer(self): self.out = b""
    def flush(self): pass
    def close(self): pass

    def write(self, data):
        op, val = data[1], struct.unpack("<I", data[2:6])[0]
        if self.mode == "silent" or p.crc8(data[:6]) != data[6]:
            return len(data)
        resp = {p.OP_IDENT: self.ident, p.OP_LINK_INFO: (434 << 16) | 50000, p.OP_BUILD_ID: 0x1234ABCD}.get(op, 5 << 8)
        body = bytes([0x5A, op]) + struct.pack("<I", resp)
        crc = p.crc8(body) ^ (0xFF if self.mode == "badcrc" else 0)
        self.out = body + bytes([crc, 0xA5])
        return len(data)

    def read(self, n):
        r, self.out = self.out[:n], self.out[n:]
        return r


def linked(mode="ok", **kw):
    lk = GardaLink()
    lk.ser, lk.port, lk.state = FakeFPGA(mode, **kw), "fake", "CONNECTED"
    return lk


class ProtocolTests(unittest.TestCase):
    def test_vectors_confirmed_by_rtl_simulation(self):
        # Frames the RTL testbench accepted (sim/build/board_trace.jsonl).
        self.assertEqual(p.encode_request(p.OP_IDENT).hex(" "), "a5 20 00 00 00 00 3e 5a")
        self.assertEqual(p.encode_request(p.OP_SAFE_RESET, p.SAFE_RESET_MAGIC).hex(" "), "a5 22 54 45 53 52 92 5a")
        self.assertEqual(p.encode_request(p.OP_STATUS).hex(" "), "a5 07 00 00 00 00 73 5a")

    def test_bad_responses_are_errors(self):
        good = bytes([0x5A, 7, 1, 2, 3, 4])
        good += bytes([p.crc8(good), 0xA5])
        self.assertEqual(p.decode_response(good, 7).value, 0x04030201)
        for raw in (b"", good[:7], b"\x00" + good[1:], good[:7] + b"\x00", good[:6] + bytes([good[6] ^ 1, 0xA5])):
            with self.assertRaises(p.ProtocolError):
                p.decode_response(raw, 7)
        with self.assertRaises(p.ProtocolError):
            p.decode_response(good, 8)   # wrong opcode echo

    def test_decoders(self):
        self.assertEqual(p.decode_command((5 << 5) | 12), {"v": 12, "omega": 5})
        self.assertEqual(p.decode_command((0x7D << 5) | 1)["omega"], -3)
        c = p.decode_capture(1 | 4 | 8 | (15 << 8))
        self.assertTrue(c["valid"] and c["enable_before"] and c["source_host"] and c["v_before"] == 15)
        self.assertEqual(p.decode_link_info((434 << 16) | 50000)["baud"], 115207)


class LinkTests(unittest.TestCase):
    def test_responding_requires_valid_ident(self):
        lk = linked("ok")
        self.assertEqual(lk.state, "CONNECTED")
        info = lk.identify()
        self.assertEqual(lk.state, "FPGA_RESPONDING")
        self.assertEqual(info["build_id"], "0x1234ABCD")

    def test_open_port_without_answer_is_not_responding(self):
        lk = linked("silent")
        with self.assertRaises(p.ProtocolError):
            lk.identify()
        self.assertEqual(lk.state, "TIMEOUT / CRC ERROR")
        self.assertEqual(lk.counters["timeouts"], 3)      # IDENT is read-only: 1 try + 2 retries
        self.assertEqual(lk.counters["rx_frames"], 0)

    def test_state_recovers_after_a_valid_answer(self):
        lk = linked("ok")
        lk.identify()
        lk.ser.mode = "silent"
        with self.assertRaises(p.ProtocolError):
            lk.transact(p.OP_MAP_WRITE, 1)
        self.assertEqual(lk.state, "TIMEOUT / CRC ERROR")
        lk.ser.mode = "ok"
        lk.transact(p.OP_STATUS)
        self.assertEqual(lk.state, "FPGA_RESPONDING")      # CRC-valid answer after an earlier timeout

    def test_state_changing_commands_are_never_retried(self):
        lk = linked("silent")
        with self.assertRaises(p.ProtocolError):
            lk.transact(p.OP_MAP_WRITE, 5)
        self.assertEqual(lk.counters["tx_frames"], 1)      # a duplicate MAP_WRITE would corrupt the upload

    def test_crc_error_counted(self):
        lk = linked("badcrc")
        with self.assertRaises(p.ProtocolError):
            lk.transact(p.OP_STATUS)
        self.assertEqual(lk.counters["crc_errors"], 1)
        self.assertEqual(lk.log[-1]["result"], "CRC_ERROR")

    def test_foreign_image_rejected(self):
        lk = linked("ok", ident=0xDEADBEEF)
        with self.assertRaises(p.ProtocolError):
            lk.identify()
        self.assertNotEqual(lk.state, "FPGA_RESPONDING")


class SequenceTests(unittest.TestCase):
    def run_seq(self, lk, steps):
        r = seqmod.Runner(lk)
        with tempfile.TemporaryDirectory() as d:
            seqmod.TRACE_DIR = Path(d)
            r.start("test", steps, {})
            for _ in range(200):
                if not r.state["running"]:
                    break
                time.sleep(0.02)
            return r.snapshot(), list(Path(d).glob("*.json"))

    def test_failure_stops_sequence_and_records_nothing(self):
        st, traces = self.run_seq(linked("silent"), ["identify", "safe_reset", "neural"])
        self.assertEqual(st["result"], "FAIL")
        self.assertEqual([s["status"] for s in st["steps"]], ["fail", "skipped", "skipped"])
        self.assertEqual(traces, [], "a run without any valid hardware response must not create a hardware trace")

    def test_not_connected(self):
        st, _ = self.run_seq(GardaLink(), ["identify"])
        self.assertIn("not connected", st["steps"][0]["detail"])


class JtagGuardTests(unittest.TestCase):
    def scan(self, cables, state="USB_BLASTER_DETECTED"):
        return {"state": state, "cables": cables}

    def test_only_single_10m50da(self):
        dev = {"idcode": "031050DD", "name": "10M50DA"}
        ok, _, cable = q.verify_target(self.scan([{"name": "USB-Blaster [USB-0]", "devices": [dev]}]))
        self.assertTrue(ok and cable == "USB-Blaster [USB-0]")
        for bad in ([{"name": "c", "devices": [{"idcode": "02D020DD", "name": "5CSEBA6"}]}],          # DE10-Nano
                    [{"name": "c", "devices": [dev, dev]}],                                          # two devices
                    [{"name": "a", "devices": [dev]}, {"name": "b", "devices": [dev]}]):             # two cables
            self.assertFalse(q.verify_target(self.scan(bad))[0])
        self.assertFalse(q.verify_target(self.scan([], "CHAIN_BROKEN"))[0])

    def test_sof_checks(self):
        with tempfile.TemporaryDirectory() as d:
            pof = Path(d) / "x.pof"; pof.write_bytes(b"10M50DAF484C7G")
            self.assertFalse(q.verify_sof(pof)[0])
            wrong = Path(d) / "nano.sof"; wrong.write_bytes(b"5CSEBA6U23I7")
            self.assertFalse(q.verify_sof(wrong)[0])
            good = Path(d) / "g.sof"; good.write_bytes(b"xx10M50DAF484C7Gxx")
            self.assertTrue(q.verify_sof(good)[0])
            man = Path(d) / "m.json"; man.write_text(json.dumps({"sof_file": "g.sof", "sof_sha256": "0" * 64}))
            self.assertFalse(q.verify_sof(good, man)[0])


class ServiceSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import garda_service as svc
        from http.server import ThreadingHTTPServer
        cls.svc = svc
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), svc.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"127.0.0.1:{self.port}", **(headers or {})}
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        return r.status, r.read()

    def test_dns_rebinding_host_rejected(self):
        self.assertEqual(self.req("GET", "/api/state", headers={"Host": "evil.example"})[0], 403)

    def test_post_requires_token_and_origin(self):
        self.assertEqual(self.req("POST", "/api/command", {"name": "status"})[0], 403)
        tok = {"X-GARDA-Token": self.svc.TOKEN}
        self.assertEqual(self.req("POST", "/api/command", {"name": "status"}, {**tok, "Origin": "https://evil.example"})[0], 403)
        code, body = self.req("POST", "/api/command", {"name": "rm -rf"}, tok)
        self.assertEqual(code, 400)

    def test_programming_needs_typed_idcode(self):
        code, body = self.req("POST", "/api/run", {"sequence": "program_and_test"}, {"X-GARDA-Token": self.svc.TOKEN})
        self.assertEqual(code, 400)
        self.assertIn(b"031050DD", body)

    def test_no_path_traversal(self):
        self.assertEqual(self.req("GET", "/../host/garda_service.py")[0], 404)
        self.assertEqual(self.req("GET", "/api/hw-trace?name=../output/build_manifest.json")[0], 404)

    def test_page_carries_token_and_state_is_honest(self):
        code, body = self.req("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(self.svc.TOKEN.encode(), body)
        st = json.loads(self.req("GET", "/api/state")[1])
        self.assertNotEqual(st["uart"]["state"], "FPGA RESPONDING")


if __name__ == "__main__":
    unittest.main()
