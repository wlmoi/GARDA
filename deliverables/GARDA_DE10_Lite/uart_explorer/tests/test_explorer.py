import csv, io, json, sys, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import protocol as P, explorer as X


class Proto(unittest.TestCase):
    def test_crc_standard_check_value(self):      # CRC-8 poly 0x07 init 0: "123456789" -> 0xF4
        self.assertEqual(P.crc8(b"123456789"), 0xF4)
    def test_request_known_frames(self):
        self.assertEqual(P.encode_request(7, 0).hex(), "a50700000000735a")
        r = P.encode_request(8, 0x1234)
        self.assertEqual(r[:6].hex(), "a508" + "34120000"); self.assertEqual(r[6], P.crc8(r[:6])); self.assertEqual(r[7], 0x5A)
    def test_roundtrip_and_endianness(self):
        d = P.decode_request(P.encode_request(10, 5 | (0xFFC0 << 8)))
        self.assertTrue(d["valid"]); self.assertEqual(d["payload"], 5 | (0xFFC0 << 8)); self.assertTrue(d["payload_ok"])
    def test_response_decode(self):
        d = P.decode_response(P.encode_response(12, (1 << 16) | 0xFF9E), expect_op=12)
        self.assertTrue(d["valid"]); self.assertEqual(d["fields"]["result_q8_8"], -98); self.assertTrue(d["fields"]["done"])
        self.assertEqual(d["raw_sof"] if "raw_sof" in d else d["sof"], 0x5A)
    def test_status_and_gate_fields(self):
        f = P.decode_status((2 << 8) | (5 << 16)); self.assertEqual(f["fault_code"], 2); self.assertFalse(f["enable"]); self.assertEqual(f["candidate_index"], 5)
        self.assertEqual(P.decode_value(14, (0x7F << 5) | 3), {"v_command": 3, "omega_command": -1})
    def test_malformed(self):
        good = bytearray(P.encode_response(7, 0))
        for i, msg in ((0, "bad SOF"), (7, "bad EOF"), (6, "CRC mismatch")):
            b = bytearray(good); b[i] ^= 0xFF; d = P.decode_response(bytes(b)); self.assertFalse(d["valid"]); self.assertIn(msg, d["errors"])
        self.assertFalse(P.decode_response(bytes(good[:5]))["valid"])
        self.assertIn("opcode echo", " ".join(P.decode_response(bytes(good), expect_op=9)["errors"]))
    def test_payload_ok_mirrors_rtl(self):
        self.assertTrue(P.payload_ok(8, 6019)); self.assertFalse(P.payload_ok(8, 6020))
        self.assertFalse(P.payload_ok(10, 24)); self.assertFalse(P.payload_ok(7, 1)); self.assertFalse(P.payload_ok(99, 0))
        self.assertTrue(P.payload_ok(12, 3)); self.assertFalse(P.payload_ok(12, 4))
    def test_uart_bit_order(self):                  # 0xA5, LSB first, start low, stop high
        self.assertEqual(P.uart_frame_bits(0xA5), [0, 1, 0, 1, 0, 0, 1, 0, 1, 1])
        self.assertEqual(P.uart_frame_bits(0x01), [0, 1, 0, 0, 0, 0, 0, 0, 0, 1])
        self.assertAlmostEqual(P.bit_time_us(), 8.6806, 3)


class Hub(unittest.TestCase):
    def setUp(self): self.h = X.Hub(); self.h.connect("SIMULATION")
    def types(self): return [e["type"] for e in self.h.ring]
    def test_event_sequence_and_rtt(self):
        r = self.h.transact(8, 0)
        self.assertTrue(r["ok"]); self.assertEqual(r["response"]["fields"]["rom_word"], X.read_mem(X.ROOT / "data/bram_unified_weights.mem")[0])
        t = self.types()
        for a, b in zip(["PORT_OPENED", "TX_STARTED", "TX_COMPLETED", "RX_DATA_RECEIVED", "FRAME_DECODED", "CRC_VALID", "FPGA_RESPONSE_RECEIVED", "COMMAND_ACCEPTED"], t):
            self.assertEqual(a, b)
        self.assertGreater(r["rtt_us"], 0)
        ids = [e["id"] for e in self.h.ring]; self.assertEqual(ids, sorted(set(ids)))
    def test_every_event_labelled_simulation(self):
        self.h.transact(7); self.assertTrue(all(e["mode"] == "SIMULATION" for e in self.h.ring))
        self.assertTrue(all(e["source"] == "SIM" for e in self.h.ring))
    def test_nn_vector_matches_reference(self):
        v = X.load_vectors()[0]
        for i, x in enumerate(v["inputs"]): self.assertTrue(self.h.transact(10, i | ((x & 0xFFFF) << 8))["ok"])
        self.h.transact(11)
        got = [self.h.transact(12, i)["response"]["fields"]["result_q8_8"] for i in range(4)]
        self.assertEqual(got, v["expected"])
    def test_estop_sim(self):
        self.h.dev.estop = True
        r = self.h.transact(7)
        self.assertEqual(r["response"]["fields"]["fault_code"], 2); self.assertIn("ESTOP_CONFIRMED", self.types())
        self.assertEqual(self.h.transact(14)["response"]["fields"], {"v_command": 0, "omega_command": 0})
    def test_switches_and_keys_match_rtl_priority(self):   # expected values come from tests/rtl_cosim/run_io.py
        want = [((0, 0, 0, 0), 0, 5), ((1, 1, 0, 0), 0, 5), ((0, 0, 1, 0), 0, 4), ((0, 0, 0, 1), 0, 3), ((0, 0, 0, 0), 1, 2), ((0, 0, 0, 1), 1, 2)]
        for sw, k1, fc in want:
            self.h.dev.io(list(sw), bool(k1)); self.assertEqual(self.h.transact(7)["response"]["fields"]["fault_code"], fc)
    def test_key0_clears_sticky_fault(self):
        bad = bytearray(P.encode_request(7, 0)); bad[6] ^= 1
        self.h.transact(7, raw_override=bytes(bad), timeout=0.05); self.assertTrue(self.h.transact(7, timeout=0.05)["timeout"])
        self.h.dev.io(key0=True); self.assertTrue(self.h.transact(7)["ok"])
    def test_invalid_payload_refused_without_tx(self):
        n = len(self.h.ring)
        with self.assertRaises(ValueError): self.h.transact(8, 9999)
        self.assertEqual(len(self.h.ring), n)
    def test_timeout_after_bad_frame(self):
        bad = bytearray(P.encode_request(7, 0)); bad[6] ^= 1
        r = self.h.transact(7, raw_override=bytes(bad), timeout=0.05)
        self.assertTrue(r["timeout"]); self.assertIn("COMMAND_TIMEOUT", self.types())
        self.assertTrue(self.h.dev.pfault)                       # sticky fault like the RTL
        self.assertTrue(self.h.transact(7, timeout=0.05)["timeout"])
    def test_crc_error_event(self):
        class Bad(X.SimDevice):
            def write(s, d):
                super().write(d); s.rx[6] ^= 0xFF
        self.h.dev = Bad(); r = self.h.transact(7)
        self.assertFalse(r["ok"]); self.assertIn("CRC_ERROR", self.types()); self.assertNotIn("FPGA_RESPONSE_RECEIVED", self.types())
    def test_disconnected(self):
        self.h.disconnect()
        with self.assertRaises(RuntimeError) as c: self.h.transact(7)
        self.assertIn("UNAVAILABLE", str(c.exception))
        with self.assertRaises(RuntimeError): self.h.start_demo()
    def test_live_missing_port_reports_unavailable(self):
        with self.assertRaises(RuntimeError) as c: self.h.connect("LIVE", "COM_DOES_NOT_EXIST")
        self.assertIn("LIVE HARDWARE UNAVAILABLE", str(c.exception)); self.assertEqual(self.h.mode, "NONE")
    def test_demo_sim_and_exports(self):
        self.h.start_demo(); self.h.demo_thread.join(20)
        d = self.h.demo; self.assertEqual(d["overall"], "PASS"); self.assertEqual(d["summary"], {"PASS": 5})
        _, js = self.h.export("json"); evs = json.loads(js)["events"]
        tx = [e["raw"] for e in evs if e["type"] == "TX_STARTED"]
        _, hx = self.h.export("hex"); self.assertEqual([l.split(" ", 3)[3] for l in hx.splitlines() if "HOST->FPGA" in l], tx)
        rows = list(csv.DictReader(io.StringIO(self.h.export("csv")[1]))); self.assertEqual(len(rows), len(evs))
        self.assertEqual([r["raw_hex"] for r in rows if r["type"] == "TX_STARTED"], tx)
    def test_ring_is_bounded(self):
        h = X.Hub(); h.connect("SIMULATION")
        for _ in range(X.RING + 50): h.emit("X", "T")
        self.assertEqual(len(h.ring), X.RING)
    def test_slow_subscriber_does_not_block(self):
        q = self.h.subscribe(); t = time.time()
        for _ in range(5000): self.h.emit("X", "T")
        self.assertLess(time.time() - t, 3); self.assertLessEqual(q.qsize(), 2000)


if __name__ == "__main__": unittest.main(verbosity=2)
