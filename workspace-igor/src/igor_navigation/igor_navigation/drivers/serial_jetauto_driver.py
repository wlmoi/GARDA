"""
Serial Hardware Driver for Hiwonder JetAuto STM32 Sub-Controller Board.
Communicates via /dev/ttyACM0 or /dev/rrc at 1,000,000 bps (1 Mbps).
Part of IGOR JetAuto Obstacle Avoidance Suite.
"""

import time
import struct
import threading
from typing import Tuple, List, Optional
import numpy as np

try:
    import serial
except ImportError:
    serial = None


def crc8_maxim(data: bytes) -> int:
    """ Compute Dallas/Maxim CRC-8 checksum """
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x01:
                crc = (crc >> 1) ^ 0x8C
            else:
                crc >>= 1
    return crc


class SerialJetAutoDriver:
    """
    Direct low-latency serial driver for JetAuto STM32 Sub-Controller.
    Handles 4-motor RPS actuation and 6-DOF IMU telemetry streaming.
    """

    PACKET_START_1 = 0xAA
    PACKET_START_2 = 0x55
    PACKET_FUNC_MOTOR = 0x03
    PACKET_FUNC_IMU = 0x07

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        baudrate: int = 1000000,
        timeout: float = 0.05,
        mock: bool = False
    ):
        self.port_name = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.mock = mock
        self.ser = None
        self.is_connected = False

        # Latest IMU feedback: (ax, ay, az, gx, gy, gz) in SI units
        self.latest_imu = (0.0, 0.0, 9.81, 0.0, 0.0, 0.0)
        self.lock = threading.Lock()
        self.running = False
        self.read_thread = None

        if not self.mock:
            self._connect()

    def _connect(self):
        """ Attempt to open serial connection """
        if serial is None:
            print("⚠️ pyserial is not installed. Running in mock mode.")
            self.mock = True
            return

        try:
            self.ser = serial.Serial(self.port_name, self.baudrate, timeout=self.timeout)
            self.is_connected = True
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            print(f"✔ SerialJetAutoDriver connected to {self.port_name} @ {self.baudrate} bps.")
        except Exception as e:
            print(f"ℹ Could not connect to physical serial port {self.port_name} ({e}). Falling back to mock driver.")
            self.mock = True
            self.is_connected = False

    def set_motor_speeds(self, rps_fl: float, rps_rl: float, rps_fr: float, rps_rr: float):
        """
        Send 4-motor speeds in RPS (Revolutions Per Second).
        Motor ID:
          0: Front-Left (FL)
          1: Rear-Left (RL)
          2: Front-Right (FR)
          3: Rear-Right (RR)
        """
        if self.mock or not self.is_connected or self.ser is None:
            return

        speeds = [rps_fl, rps_rl, -rps_fr, -rps_rr]  # FR and RR have reversed mechanical mounting

        # Packet framing: Function (0x03), Length (22), SubCmd (0x01), Count (4), [id, float32_speed] x 4
        payload = bytearray([0x01, 0x04])
        for idx, spd in enumerate(speeds):
            payload.extend(struct.pack("<Bf", idx, float(spd)))

        length = len(payload)
        frame_header = bytearray([self.PACKET_FUNC_MOTOR, length])
        frame_to_check = frame_header + payload
        checksum = crc8_maxim(bytes(frame_to_check))

        full_packet = bytearray([self.PACKET_START_1, self.PACKET_START_2]) + frame_to_check + bytearray([checksum])
        try:
            self.ser.write(full_packet)
        except Exception as e:
            print(f"⚠️ Serial write failed: {e}")

    def get_latest_imu(self) -> Tuple[float, float, float, float, float, float]:
        """ Return latest IMU telemetry tuple (ax, ay, az, gx, gy, gz) """
        with self.lock:
            return self.latest_imu

    def _read_loop(self):
        """ Background receiver task parsing incoming IMU packets """
        while self.running and self.ser and self.ser.is_open:
            try:
                b1 = self.ser.read(1)
                if not b1 or b1[0] != self.PACKET_START_1:
                    continue
                b2 = self.ser.read(1)
                if not b2 or b2[0] != self.PACKET_START_2:
                    continue

                func = self.ser.read(1)[0]
                length = self.ser.read(1)[0]
                data = self.ser.read(length)
                crc = self.ser.read(1)[0]

                if crc8_maxim(bytes([func, length]) + data) == crc:
                    if func == self.PACKET_FUNC_IMU and length == 24:
                        # 6x float32: ax, ay, az, gx, gy, gz
                        raw_imu = struct.unpack("<6f", data)
                        # Convert g to m/s^2 and deg/s to rad/s
                        ax = raw_imu[0] * 9.80665
                        ay = raw_imu[1] * 9.80665
                        az = raw_imu[2] * 9.80665
                        gx = np.radians(raw_imu[3])
                        gy = np.radians(raw_imu[4])
                        gz = np.radians(raw_imu[5])
                        with self.lock:
                            self.latest_imu = (ax, ay, az, gx, gy, gz)
            except Exception:
                time.sleep(0.01)

    def close(self):
        """ Safely shutdown serial communication """
        self.running = False
        if self.ser and self.ser.is_open:
            try:
                self.set_motor_speeds(0.0, 0.0, 0.0, 0.0)
                self.ser.close()
            except Exception:
                pass
        self.is_connected = False
