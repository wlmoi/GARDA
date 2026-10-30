#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rplidar_driver_node.py - Pure-Python RPLiDAR A1/A2 Serial Driver & ROS 2 Publisher
Target Platform: Slamtec RPLiDAR A1 (/dev/lidar @ 115200 bps)
PERURI Chip Hackathon 2026 - Project IGOR

Features:
- Native binary protocol parser for RPLiDAR A1/A2 continuous scanning.
- Publishes sensor_msgs/msg/LaserScan on topic /scan at 10 Hz.
- Transparent fallback to mock/simulated scan if physical device is absent,
  enabling robust headless testing without crashing the ROS 2 bringup graph.
"""

import math
import time
import struct
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

        self.port = str(self.get_parameter('serial_port').value)
        self.baudrate = int(self.get_parameter('serial_baudrate').value)
        self.frame_id = str(self.get_parameter('frame_id').value)
        self.mock = bool(self.get_parameter('mock').value)

        self.publisher = self.create_publisher(
            LaserScan,
            '/scan',
            rclpy.qos.qos_profile_sensor_data
        )

        self.ser = None
        self._running = False
        self._thread = None

        self._current_scan = np.full(360, 3.50, dtype=np.float32)
        self._scan_lock = threading.Lock()

        # Connect
        self._connect()

        # Publish timer at 10 Hz
        self.timer = self.create_timer(0.1, self._publish_scan)
        self.get_logger().info(f"RPLidarDriverNode initialized (Port: {self.port}, Baud: {self.baudrate}, Mock: {self.mock})")

    def _connect(self):
        if self.mock or serial is None:
            self.mock = True
            self.get_logger().warn("RPLiDAR running in MOCK mode (serial unavailable or mock=True)")
            return

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

            # Read 7-byte response descriptor
            descriptor = self.ser.read(7)
            if len(descriptor) == 7 and descriptor[0] == self.SYNC_BYTE1 and descriptor[1] == self.SYNC_BYTE2:
                self.get_logger().info(f"Connected to RPLiDAR on {self.port}. Response descriptor validated.")
            else:
                self.get_logger().warn(f"RPLiDAR descriptor unexpected ({descriptor.hex()}), proceeding in streaming mode.")

            self._running = True
            self._thread = threading.Thread(target=self._read_lidar_stream, daemon=True)
            self._thread.start()
        except Exception as e:
            self.get_logger().warn(f"Could not open {self.port}: {e}. Falling back to MOCK LiDAR generator.")
            self.mock = True
            self.ser = None

    def _read_lidar_stream(self):
        """Thread continuously parsing 5-byte measurement packets."""
        scan_buf = np.full(360, 3.50, dtype=np.float32)

        while self._running and self.ser and self.ser.is_open:
            try:
                # RPLiDAR standard measurement packet: 5 bytes
                raw = self.ser.read(5)
                if len(raw) < 5:
                    continue

                b0, b1, b2, b3, b4 = raw
                # Check bits
                sync = b0 & 0x01
                not_sync = (b0 >> 1) & 0x01
                if sync == not_sync:
                    # Sync bit and inverse bit must differ
                    continue

                check_bit = b1 & 0x01
                if check_bit != 1:
                    continue

                angle_q6 = (b1 >> 1) | (b2 << 7)
                angle_deg = angle_q6 / 64.0
                dist_q2 = b3 | (b4 << 8)
                dist_m = (dist_q2 / 4.0) / 1000.0

                if 0.15 <= dist_m <= 12.0:
                    deg_idx = int(round(angle_deg)) % 360
                    scan_buf[deg_idx] = dist_m

                # When a full revolution completes (sync==1 indicates new scan)
                if sync == 1:
                    with self._scan_lock:
                        self._current_scan = scan_buf.copy()
            except Exception as e:
                self.get_logger().debug(f"LiDAR stream error: {e}")
                time.sleep(0.01)

    def _publish_scan(self):
        """Publishes LaserScan message."""
        scan_msg = LaserScan()
        now = self.get_clock().now().to_msg()
        scan_msg.header.stamp = now
        scan_msg.header.frame_id = self.frame_id

        scan_msg.angle_min = 0.0
        scan_msg.angle_max = 2.0 * math.pi
        scan_msg.angle_increment = (2.0 * math.pi) / 360.0
        scan_msg.time_increment = 0.1 / 360.0
        scan_msg.scan_time = 0.1
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
            with self._scan_lock:
                scan_msg.ranges = [float(r) for r in self._current_scan]

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
