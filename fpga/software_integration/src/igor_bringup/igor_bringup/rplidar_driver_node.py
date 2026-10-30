#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rplidar_driver_node.py - Pure-Python RPLiDAR A1/A2 Serial Driver & ROS 2 Publisher
Target Platform: Slamtec RPLiDAR A1 (/dev/lidar @ 115200 bps)
PERURI Chip Hackathon 2026 - Project IGOR

Features:
- Native binary protocol parser for RPLiDAR A1/A2 continuous scanning.
- Publishes sensor_msgs/msg/LaserScan on topic /scan at 10 Hz.
- Simulation requires explicit mock=True. Missing hardware fails closed.
- Publishes each fresh, completed revolution once, with acquisition timestamps.
"""

import math
import time
import logging
import threading
import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger("rplidar_driver")


class ScanAssembler:
    """Build complete standard-mode revolutions without reusing old bins.

    Unknown/invalid bins remain at the conservative minimum range. NaN/Inf
    would be unsafe here because the current host subsampler treats them as
    clear space. At least min_scan_bins distinct valid returns are required.
    """

    def __init__(self, min_scan_bins=180, max_scan_age_sec=0.25):
        if not 1 <= min_scan_bins <= 360:
            raise ValueError("min_scan_bins must be in [1,360]")
        if not math.isfinite(max_scan_age_sec) or max_scan_age_sec <= 0:
            raise ValueError("max_scan_age_sec must be positive and finite")
        self.min_scan_bins = min_scan_bins
        self.max_scan_age_sec = max_scan_age_sec
        self._started = None
        self._stamp = None
        self._ranges = np.full(360, 0.15, dtype=np.float32)
        self._seen = set()

    @staticmethod
    def decode(raw):
        if len(raw) != 5:
            return None
        b0, b1, b2, b3, b4 = raw
        sync, not_sync = b0 & 1, (b0 >> 1) & 1
        if sync == not_sync or not (b1 & 1):
            return None
        angle = ((b1 >> 1) | (b2 << 7)) / 64.0
        if not 0 <= angle < 360:
            return None
        distance = (b3 | (b4 << 8)) / 4000.0
        return bool(sync), angle, distance, b0 >> 2

    def feed(self, raw, acquired_monotonic, acquired_stamp):
        decoded = self.decode(raw)
        if decoded is None:
            return None
        sync, angle, distance, quality = decoded
        completed = None
        if sync:
            # The marker belongs to the NEXT scan, never the previous one.
            if self._started is not None:
                duration = acquired_monotonic - self._started
                if (0 < duration <= self.max_scan_age_sec and
                        len(self._seen) >= self.min_scan_bins):
                    completed = (self._ranges.copy(), self._started,
                                 acquired_monotonic, self._stamp, duration)
            self._started = acquired_monotonic
            self._stamp = acquired_stamp
            self._ranges.fill(0.15)
            self._seen.clear()
        if self._started is not None and quality > 0 and 0.15 <= distance <= 12.0:
            index = int(round(angle)) % 360
            # If several measurements land in one degree bin, retain the closest.
            if index not in self._seen:
                self._ranges[index] = distance
            else:
                self._ranges[index] = min(self._ranges[index], distance)
            self._seen.add(index)
        return completed


class RPLidarDriverNode(Node):
    SYNC_BYTE1 = 0xA5
    SYNC_BYTE2 = 0x5A
    CMD_STOP = b'\xA5\x25'
    CMD_RESET = b'\xA5\x40'
    CMD_SCAN = b'\xA5\x20'

    def __init__(self):
        super().__init__('rplidar_driver_node')

        self.declare_parameter('serial_port', '/dev/lidar')
        self.declare_parameter('serial_baudrate', 115200)
        self.declare_parameter('frame_id', 'laser')
        self.declare_parameter('mock', False)
        self.declare_parameter('min_scan_bins', 180)
        self.declare_parameter('max_scan_age_sec', 0.25)

        self.port = str(self.get_parameter('serial_port').value)
        self.baudrate = int(self.get_parameter('serial_baudrate').value)
        self.frame_id = str(self.get_parameter('frame_id').value)
        self.mock = bool(self.get_parameter('mock').value)
        self.min_scan_bins = int(self.get_parameter('min_scan_bins').value)
        self.max_scan_age_sec = float(self.get_parameter('max_scan_age_sec').value)
        self._assembler = ScanAssembler(self.min_scan_bins, self.max_scan_age_sec)

        self.publisher = self.create_publisher(
            LaserScan,
            '/scan',
            rclpy.qos.qos_profile_sensor_data
        )

        self.ser = None
        self._running = False
        self._thread = None

        self._current_scan = None
        self._scan_acquired_monotonic = None
        self._scan_completed_monotonic = None
        self._scan_stamp = None
        self._scan_duration = None
        self._scan_sequence = 0
        self._published_sequence = 0
        self._scan_lock = threading.Lock()

        # Connect
        self._connect()

        # Publish timer at 10 Hz
        self.timer = self.create_timer(0.1, self._publish_scan)
        self.get_logger().info(f"RPLidarDriverNode initialized (Port: {self.port}, Baud: {self.baudrate}, Mock: {self.mock})")

    def _connect(self):
        if self.mock:
            self.get_logger().warn("RPLiDAR running in EXPLICIT MOCK mode (mock=True)")
            return
        if serial is None:
            raise RuntimeError("pyserial unavailable; physical LiDAR required unless mock=True")

        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            # Send stop and reset
            self.ser.write(self.CMD_STOP)
            time.sleep(0.05)
            self.ser.write(self.CMD_SCAN)
            time.sleep(0.05)

            # Standard measurement: payload size 5, continuous send mode 1,
            # response type 0x81 (Slamtec SDK sl_lidar_protocol.h/cmd.h).
            descriptor = bytearray()
            deadline = time.monotonic() + 1.0
            while len(descriptor) < 7 and time.monotonic() < deadline:
                chunk = self.ser.read(7-len(descriptor))
                if not chunk:
                    break
                descriptor.extend(chunk)
            if bytes(descriptor) != b'\xa5\x5a\x05\x00\x00\x40\x81':
                raise RuntimeError(f"Invalid standard-scan descriptor: {descriptor.hex()}")
            self.get_logger().info(f"Connected to RPLiDAR on {self.port}. Response descriptor validated.")

            self._running = True
            self._thread = threading.Thread(target=self._read_lidar_stream, daemon=True)
            self._thread.start()
        except Exception as e:
            self._running = False
            if self.ser is not None:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            raise RuntimeError(f"Physical LiDAR connection failed on {self.port}: {e}") from e

    def _read_lidar_stream(self):
        """Thread continuously parsing 5-byte measurement packets."""
        pending = bytearray()
        while self._running and self.ser and self.ser.is_open:
            try:
                raw = self.ser.read(5)
                if not raw:
                    continue
                pending.extend(raw)
                while len(pending) >= 5:
                    packet = bytes(pending[:5])
                    decoded = self._assembler.decode(packet)
                    if decoded is None:
                        del pending[0]  # resynchronize without discarding partial reads
                        continue
                    del pending[:5]
                    acquired = time.monotonic()
                    stamp = self.get_clock().now().to_msg() if decoded[0] else None
                    completed = self._assembler.feed(packet, acquired, stamp)
                    if completed is None:
                        continue
                    ranges, started, finished, scan_stamp, duration = completed
                    with self._scan_lock:
                        self._current_scan = ranges
                        self._scan_acquired_monotonic = started
                        self._scan_completed_monotonic = finished
                        self._scan_stamp = scan_stamp
                        self._scan_duration = duration
                        self._scan_sequence += 1
            except Exception as e:
                self.get_logger().error(f"LiDAR stream stopped; no synthetic scans will be published: {e}")
                self._running = False
                with self._scan_lock:
                    self._current_scan = None
                break

    def _publish_scan(self):
        """Publishes LaserScan message."""
        if not self.mock:
            with self._scan_lock:
                if (self._current_scan is None or self._scan_acquired_monotonic is None or
                        self._scan_sequence == self._published_sequence):
                    return
                age = time.monotonic() - self._scan_acquired_monotonic
                if not 0 <= age <= self.max_scan_age_sec:
                    return
                ranges = self._current_scan.copy()
                stamp = self._scan_stamp
                duration = self._scan_duration
                self._published_sequence = self._scan_sequence
        else:
            stamp = self.get_clock().now().to_msg()
            duration = 0.1
        scan_msg = LaserScan()
        # ROS LaserScan stamp is acquisition of the first ray, never timer time.
        scan_msg.header.stamp = stamp
        scan_msg.header.frame_id = self.frame_id

        scan_msg.angle_min = 0.0
        scan_msg.angle_increment = (2.0 * math.pi) / 360.0
        scan_msg.angle_max = 2.0 * math.pi - scan_msg.angle_increment
        scan_msg.time_increment = duration / 360.0
        scan_msg.scan_time = duration
        scan_msg.range_min = 0.15
        scan_msg.range_max = 12.0

        if self.mock:
            # Generate simulated scan: free floor with a corridor wall at 2.5m and front obstacle at 1.8m
            mock_ranges = np.full(360, 2.50, dtype=np.float32)
            # Front obstacle around 0 degrees (from 350 to 10 deg)
            mock_ranges[350:360] = 1.80
            mock_ranges[0:10] = 1.80
            scan_msg.ranges = [float(r) for r in mock_ranges]
        else:
            scan_msg.ranges = [float(r) for r in ranges]

        self.publisher.publish(scan_msg)

    def destroy_node(self):
        self._running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(self.CMD_STOP)
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RPLidarDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
