#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcu_driver.py - JetAuto STM32 Sub-Controller Bidirectional Serial Driver
Target Platform: Hiwonder JetAuto Mecanum (/dev/ttyACM0 @ 1,000,000 bps)
PERURI Chip Hackathon 2026 - Project IGOR

Features:
- Dedicated background thread for continuous non-blocking RX packet parsing.
- State-machine binary decoder for STM32 protocol:
    Header: 0xAA 0x55
    Func 0x07: MPU-6050 IMU Telemetry (24 bytes: 6x float32 LE)
    Func 0x03: Motor Speed Command TX (SUB_CMD 0x01 + 4x [ID, float32 LE])
- Robust CRC-8 validation on all frames.
- Explicit mock mode only; unavailable hardware fails startup.
"""

import os
import time
import math
import struct
import logging
import threading
from typing import Optional, Tuple, Dict, Any

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger("mcu_driver")

# CRC-8 Lookup Table
CRC8_TABLE = [
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53
]

def checksum_crc8(data: bytes) -> int:
    """Compute CRC-8 checksum over byte sequence."""
    check = 0
    for b in data:
        check = CRC8_TABLE[check ^ b]
    return check & 0x00FF


class STM32Driver:
    """
    Bidirectional STM32 controller driver for Hiwonder JetAuto.
    """
    START_BYTE1 = 0xAA
    START_BYTE2 = 0x55
    FUNC_MOTOR  = 0x03
    FUNC_IMU    = 0x07
    SUB_CMD_MOTOR_SPEED = 0x01

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        baudrate: int = 1000000,
        mock: bool = False
    ):
        self.port = port
        self.baudrate = baudrate
        self.mock = mock

        self.ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._running = False
        self._rx_thread: Optional[threading.Thread] = None

        # Latest IMU State: ax, ay, az (in g), gx, gy, gz (in deg/s)
        self._latest_imu = (0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
        self._latest_imu_time = 0.0
        self._imu_lock = threading.Lock()
        self.total_imu_packets = 0
        self.crc_errors = 0

        self._connect()

    def _connect(self) -> None:
        if self.mock:
            logger.warning("STM32Driver operating in explicitly requested MOCK mode")
            return
        if serial is None:
            raise RuntimeError("pyserial is unavailable for the physical STM32 driver")

        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.05,
                write_timeout=0.05
            )
            if not self.send_motor_speeds(0.0, 0.0, 0.0, 0.0):
                raise RuntimeError("Cannot transmit initial STM32 STOP")
            self._running = True
            self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
            self._rx_thread.start()
            logger.info(f"Connected to STM32 sub-controller on {self.port} @ {self.baudrate} bps")
        except Exception as e:
            self._running = False
            if self.ser is not None:
                self.ser.close()
            self.ser = None
            raise RuntimeError(f"Cannot initialize physical STM32 {self.port}: {e}") from e

    def _rx_loop(self) -> None:
        """Background state-machine thread reading incoming serial stream."""
        state = 0  # 0: wait 0xAA, 1: wait 0x55, 2: func, 3: len, 4: data, 5: crc
        func_id = 0
        length = 0
        buf = bytearray()

        while self._running and self.ser and self.ser.is_open:
            try:
                raw_bytes = self.ser.read(64)
                if not raw_bytes:
                    continue

                for b in raw_bytes:
                    if state == 0:
                        if b == self.START_BYTE1:
                            state = 1
                    elif state == 1:
                        if b == self.START_BYTE2:
                            state = 2
                        elif b == self.START_BYTE1:
                            state = 1
                        else:
                            state = 0
                    elif state == 2:
                        func_id = b
                        state = 3
                    elif state == 3:
                        length = b
                        buf = bytearray()
                        state = 5 if length == 0 else 4
                    elif state == 4:
                        buf.append(b)
                        if len(buf) >= length:
                            state = 5
                    elif state == 5:
                        crc = b
                        expected_crc = checksum_crc8(bytes([func_id, length]) + bytes(buf))
                        if crc == expected_crc:
                            if func_id == self.FUNC_IMU and len(buf) >= 24:
                                ax, ay, az, gx, gy, gz = struct.unpack('<6f', bytes(buf[:24]))
                                with self._imu_lock:
                                    self._latest_imu = (ax, ay, az, gx, gy, gz)
                                    self._latest_imu_time = time.monotonic()
                                    self.total_imu_packets += 1
                        else:
                            self.crc_errors += 1
                        state = 0
            except Exception as e:
                logger.debug(f"RX loop read exception: {e}")
                time.sleep(0.01)

    def get_latest_imu(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], float]:
        """
        Returns:
            ((ax, ay, az) [g], (gx, gy, gz) [deg/s], monotonic timestamp)
        """
        if self.mock:
            # In mock mode, return static 1g on Z and slight zero-noise
            return ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), time.monotonic())

        with self._imu_lock:
            ax, ay, az, gx, gy, gz = self._latest_imu
            t = self._latest_imu_time
        return ((ax, ay, az), (gx, gy, gz), t)

    def send_motor_speeds(
        self,
        rps_m1: float,
        rps_m2: float,
        rps_m3: float,
        rps_m4: float
    ) -> bool:
        """
        Command 4 Mecanum wheel rotational speeds in rotations per second (RPS).
        
        Wheel layout:
          M1 (Index 0): Front-Left
          M2 (Index 1): Rear-Left
          M3 (Index 2): Front-Right (Mirrored)
          M4 (Index 3): Rear-Right  (Mirrored)
        """
        if self.mock:
            return True

        if not self.ser or not self.ser.is_open:
            return False

        # Construct payload: [SUB_CMD, count=4] + 4x [motor_idx, float32_speed]
        payload = bytearray([self.SUB_CMD_MOTOR_SPEED, 4])
        for idx, rps in enumerate([rps_m1, rps_m2, rps_m3, rps_m4]):
            payload.extend(struct.pack("<Bf", idx, float(rps)))

        packet = bytearray([self.START_BYTE1, self.START_BYTE2, self.FUNC_MOTOR, len(payload)])
        packet.extend(payload)
        packet.append(checksum_crc8(bytes(packet[2:])))

        try:
            with self._lock:
                count = self.ser.write(bytes(packet))
            if count != len(packet):
                logger.error(f"Short STM32 write: {count}/{len(packet)}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to transmit motor speeds: {e}")
            return False

    def close(self) -> None:
        """Stop motors and safely close serial link."""
        self._running = False
        try:
            self.send_motor_speeds(0.0, 0.0, 0.0, 0.0)
        except Exception:
            pass

        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=0.2)

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        logger.info("STM32 driver shut down safely.")
