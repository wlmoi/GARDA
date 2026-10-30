#!/usr/bin/env python3
"""Test the production LiDAR overlay without ROS or physical serial hardware."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE / "software_integration/src/igor_bringup/igor_bringup/rplidar_driver_node.py"
if not SOURCE.exists():
    SOURCE = PACKAGE.parent / "fpga/software_integration/src/igor_bringup/igor_bringup/rplidar_driver_node.py"
if not SOURCE.exists():
    raise SystemExit("Production overlay missing; original ./src is a read-only reference")


class PublisherFixture:
    def __init__(self): self.messages = []
    def publish(self, message): self.messages.append(message)


class NodeFixture:
    overrides = {}
    def __init__(self, name): self.parameters = {}; self.messages = []
    def declare_parameter(self, name, default): self.parameters[name] = self.overrides.get(name, default)
    def get_parameter(self, name): return SimpleNamespace(value=self.parameters[name])
    def create_publisher(self, *args): return PublisherFixture()
    def create_timer(self, *args): return SimpleNamespace()
    def get_logger(self): return self
    def warn(self, value): self.messages.append(value)
    def info(self, value): self.messages.append(value)
    def error(self, value): self.messages.append(value)
    def get_clock(self):
        return SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: SimpleNamespace(sec=999, nanosec=0)))
    def destroy_node(self): pass


class LaserScanFixture:
    def __init__(self): self.header = SimpleNamespace(stamp=None, frame_id=None)


rclpy = ModuleType("rclpy"); rclpy.qos = SimpleNamespace(qos_profile_sensor_data=object())
node_module = ModuleType("rclpy.node"); node_module.Node = NodeFixture
sensor_module = ModuleType("sensor_msgs"); msg_module = ModuleType("sensor_msgs.msg")
msg_module.LaserScan = LaserScanFixture
with patch.dict(sys.modules, {"rclpy": rclpy, "rclpy.node": node_module,
                              "sensor_msgs": sensor_module, "sensor_msgs.msg": msg_module}):
    spec = importlib.util.spec_from_file_location("tested_lidar_driver", SOURCE)
    driver = importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)


def measurement(angle, distance=2.0, sync=False, quality=15):
    angle_q6 = round(angle * 64); distance_q2 = round(distance * 4000)
    return bytes([(quality << 2) | (1 if sync else 2),
                  ((angle_q6 & 127) << 1) | 1, angle_q6 >> 7,
                  distance_q2 & 255, distance_q2 >> 8])


class SerialFixture:
    def __init__(self, chunks): self.chunks = list(chunks); self.is_open = True; self.writes = []
    def write(self, value): self.writes.append(value)
    def close(self): self.is_open = False
    def read(self, length):
        if not self.chunks: return b""
        chunk = self.chunks.pop(0)
        if len(chunk) > length:
            self.chunks.insert(0, chunk[length:]); chunk = chunk[:length]
        return chunk


class ThreadFixture:
    def __init__(self, **kwargs): self.started = False
    def start(self): self.started = True


class LidarRegression(unittest.TestCase):
    def setUp(self):
        self.monotonic = 10.0
        self.patches = [patch.object(driver.time, "monotonic", lambda: self.monotonic),
                        patch.object(driver.time, "sleep", lambda _: None),
                        patch.object(driver.threading, "Thread", ThreadFixture)]
        for item in self.patches: item.start()
        NodeFixture.overrides = {}
    def tearDown(self):
        for item in reversed(self.patches): item.stop()
    def create(self, mock=False, serial_module=None):
        NodeFixture.overrides = {"mock": mock}
        with patch.object(driver, "serial", serial_module):
            return driver.RPLidarDriverNode()
    def physical(self, chunks=None):
        serial = SerialFixture(chunks if chunks is not None else [b"\xa5\x5a\x05\x00\x00\x40\x81"])
        return self.create(serial_module=SimpleNamespace(Serial=lambda **_: serial)), serial
    def queue_scan(self, node, age=0.1):
        node._current_scan = np.full(360, 2.0, dtype=np.float32)
        node._scan_acquired_monotonic = self.monotonic-age
        node._scan_completed_monotonic = self.monotonic
        node._scan_duration = 0.1
        node._scan_stamp = SimpleNamespace(sec=123, nanosec=456)
        node._scan_sequence += 1
    def test_no_automatic_mock_when_serial_missing(self):
        with self.assertRaisesRegex(RuntimeError, "pyserial unavailable"):
            self.create()
    def test_no_automatic_mock_when_port_missing(self):
        def failure(**_): raise OSError("device disconnected")
        with self.assertRaisesRegex(RuntimeError, "Physical LiDAR connection failed"):
            self.create(serial_module=SimpleNamespace(Serial=failure))
    def test_explicit_mock_is_the_only_synthetic_mode(self):
        node = self.create(mock=True)
        node._publish_scan(); node._publish_scan()
        self.assertTrue(node.mock); self.assertEqual(len(node.publisher.messages), 2)
    def test_invalid_descriptor_fails_and_closes_port(self):
        valid = bytearray(b"\xa5\x5a\x05\x00\x00\x40\x81")
        for byte_index in range(7):
            wrong = valid.copy(); wrong[byte_index] ^= 1
            serial = SerialFixture([wrong])
            with self.subTest(byte_index=byte_index), self.assertRaises(RuntimeError):
                self.create(serial_module=SimpleNamespace(Serial=lambda **_: serial))
            self.assertFalse(serial.is_open)
        for short in (b"", valid[:6]):
            with self.subTest(short=len(short)), self.assertRaises(RuntimeError):
                self.physical([short])
    def test_segmented_valid_descriptor_and_boot_no_scan(self):
        node, serial = self.physical([b"\xa5\x5a", b"\x05\x00\x00\x40\x81"])
        self.assertFalse(node.mock); self.assertTrue(node._thread.started)
        self.assertEqual(serial.writes, [node.CMD_STOP, node.CMD_SCAN])
        for _ in range(100): node._publish_scan()
        self.assertEqual(node.publisher.messages, [])
    def test_partial_revolution_never_publishes_default_free_scan(self):
        assembler = driver.ScanAssembler()
        self.assertIsNone(assembler.feed(measurement(0, sync=True), 1.0, object()))
        for angle in range(1, 179): self.assertIsNone(assembler.feed(measurement(angle), 1.01, None))
        self.assertIsNone(assembler.feed(measurement(0, sync=True), 1.1, object()))
    def test_complete_scan_uses_previous_marker_stamp_and_no_next_scan_point(self):
        assembler = driver.ScanAssembler(); stamp = object()
        assembler.feed(measurement(0, sync=True), 1.0, stamp)
        for angle in range(1, 180): assembler.feed(measurement(angle), 1.01, None)
        ranges, started, finished, result_stamp, duration = assembler.feed(measurement(0, 8, True), 1.1, object())
        self.assertIs(result_stamp, stamp); self.assertEqual((started, finished), (1.0, 1.1))
        self.assertAlmostEqual(duration, 0.1); self.assertEqual(float(ranges[0]), 2.0)
        self.assertAlmostEqual(float(ranges[180]), 0.15, places=6)
    def test_scan_bins_never_carry_previous_revolution(self):
        assembler = driver.ScanAssembler(); assembler.feed(measurement(0, sync=True), 1.0, object())
        for angle in range(1, 360): assembler.feed(measurement(angle), 1.01, None)
        self.assertIsNotNone(assembler.feed(measurement(0, 3, True), 1.1, object()))
        for angle in range(1, 180): assembler.feed(measurement(angle, 3), 1.11, None)
        result = assembler.feed(measurement(0, 4, True), 1.2, object())[0]
        self.assertEqual(float(result[0]), 3.0)
        self.assertTrue(np.allclose(result[180:], 0.15)); self.assertFalse(np.any(np.isinf(result)))
    def test_repeated_bin_cannot_fake_coverage_and_keeps_nearest(self):
        assembler = driver.ScanAssembler(); assembler.feed(measurement(0, sync=True), 1.0, object())
        for _ in range(1000): assembler.feed(measurement(1), 1.01, None)
        assembler.feed(measurement(1, 0.5), 1.01, None)
        assembler.feed(measurement(1, 8), 1.01, None)
        self.assertEqual(float(assembler._ranges[1]), 0.5)
        self.assertIsNone(assembler.feed(measurement(0, sync=True), 1.1, object()))
    def test_bad_packets_returns_and_long_or_backward_revolutions_rejected(self):
        for raw in (b"1234", b"\x00\x01\x00\x00\x00", b"\x02\x00\x00\x00\x00", measurement(400)):
            self.assertIsNone(driver.ScanAssembler.decode(raw))
        for duration in (0.0, -0.1, 0.251):
            assembler = driver.ScanAssembler(); assembler.feed(measurement(0, sync=True), 1.0, object())
            for angle in range(1, 180): assembler.feed(measurement(angle), 1.01, None)
            self.assertIsNone(assembler.feed(measurement(0, sync=True), 1.0+duration, object()))
        for distance, quality in ((0,15),(13,15),(2,0)):
            assembler = driver.ScanAssembler(); assembler.feed(measurement(0, distance, True, quality), 1.0, object())
            for angle in range(1,360): assembler.feed(measurement(angle,distance,False,quality),1.01,None)
            self.assertIsNone(assembler.feed(measurement(0, sync=True),1.1,object()))
    def test_publish_once_at_acquisition_timestamp_and_correct_geometry(self):
        node,_ = self.physical(); self.queue_scan(node)
        stamp = node._scan_stamp; node._publish_scan()
        self.monotonic += 0.02; node._publish_scan()
        self.assertEqual(len(node.publisher.messages),1)
        message=node.publisher.messages[0]; self.assertIs(message.header.stamp,stamp)
        self.assertAlmostEqual(message.angle_max,359*message.angle_increment)
        self.assertAlmostEqual(message.scan_time,0.1); self.assertEqual(len(message.ranges),360)
    def test_queued_stale_or_future_scan_never_publishes(self):
        for age in (0.251,-0.001):
            node,_=self.physical(); self.queue_scan(node,age); node._publish_scan()
            self.assertEqual(node.publisher.messages,[])
    def test_frozen_sensor_does_not_republish_or_refresh_timestamp(self):
        node,_=self.physical(); self.queue_scan(node); node._publish_scan()
        for _ in range(100): self.monotonic+=0.1; node._publish_scan()
        self.assertEqual(len(node.publisher.messages),1)
        self.assertEqual(node.publisher.messages[0].header.stamp.sec,123)
    def test_stream_exception_invalidates_unpublished_scan(self):
        node,_=self.physical(); self.queue_scan(node)
        class FailedStream:
            is_open=True
            def read(self,_): raise OSError("unplugged")
        node.ser=FailedStream(); node._read_lidar_stream(); node._publish_scan()
        self.assertFalse(node._running); self.assertFalse(node.mock)
        self.assertEqual(node.publisher.messages,[])
    def test_fragmented_measurements_resynchronize_and_publish_completed_scan(self):
        node,_=self.physical()
        raw=b"\x00\x00\x00"+measurement(0,sync=True)
        raw+=b"".join(measurement(angle) for angle in range(1,180))
        raw+=measurement(0,8,sync=True)
        test=self
        class FragmentedStream:
            is_open=True
            def __init__(self): self.pending=raw; self.turn=0
            def read(self,length):
                if not self.pending:
                    node._running=False
                    return b""
                self.turn+=1; test.monotonic+=0.0001
                size=min(length,1+self.turn%5)
                chunk=self.pending[:size]; self.pending=self.pending[size:]
                return chunk
        node.ser=FragmentedStream(); node._read_lidar_stream()
        self.assertEqual(node._scan_sequence,1)
        self.assertEqual(float(node._current_scan[0]),2.0)
        self.assertTrue(np.allclose(node._current_scan[180:],0.15))
        node._publish_scan(); node._publish_scan()
        self.assertEqual(len(node.publisher.messages),1)
        self.assertEqual(node.publisher.messages[0].header.stamp.sec,999)
    def test_invalid_configuration_rejected(self):
        for bins,age in ((0,0.25),(361,0.25),(180,0),(180,float("nan"))):
            with self.assertRaises(ValueError): driver.ScanAssembler(bins,age)


if __name__ == "__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(LidarRegression)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    evidence=PACKAGE/"evidence/current_lidar"; evidence.mkdir(parents=True,exist_ok=True)
    report={"passed":result.wasSuccessful(),"tests":result.testsRun,
            "failures":len(result.failures),"errors":len(result.errors),
            "source":str(SOURCE),"source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "runner_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scope":"Real production driver with ROS/serial fixtures; no physical A1 measurement",
            "min_scan_bins":180,"max_scan_age_sec":0.25,"unknown_range_m":0.15}
    (evidence/"results.json").write_text(json.dumps(report,indent=2)+"\n")
    sys.exit(0 if result.wasSuccessful() else 1)
