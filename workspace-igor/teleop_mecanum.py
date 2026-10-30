#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
teleop_mecanum.py

Teleoperation script for Hiwonder JetAuto Mecanum robot.
Reads keyboard input (uiojklm,.) to command mecanum drive motors 1 to 4 directly.

Motor mapping and firmware indices:
  Motor 1: Front-Left  (FL) -> Index 0 (0x00)
  Motor 2: Rear-Left   (RL) -> Index 1 (0x01)
  Motor 3: Front-Right (FR) -> Index 2 (0x02)
  Motor 4: Rear-Right  (RR) -> Index 3 (0x03)
"""

import os
import sys
import time
import math
import struct
import signal
import argparse

if sys.platform == 'win32':
    import msvcrt
else:
    import termios
    import tty
    import select

# CRC-8 Table from ros_robot_controller_sdk
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

PACKET_FUNC_MOTOR   = 0x03
SUB_CMD_MOTOR_SPEED = 0x01

# JetAuto Chassis Parameters
WHEELBASE      = 0.216   # Front-to-rear axle distance (meters)
TRACK_WIDTH    = 0.195   # Left-to-right wheel centerline distance (meters)
WHEEL_DIAMETER = 0.0965  # Mecanum wheel diameter (meters)

# Motor Index Mapping:
# Motor ID -> (Firmware Index, Name)
MOTOR_MAP = {
    1: (0, "Front-Left (FL)"),
    2: (1, "Rear-Left (RL)"),
    3: (2, "Front-Right (FR)"),
    4: (3, "Rear-Right (RR)")
}

BANNER = """\
---------------------------
Moving around:
   u    i    o
   j    k    l
   m    ,    .

For Holonomic mode (strafing), hold down the shift key:
---------------------------
   U    I    O
   J    K    L
   M    <    >

t : up (+z)
b : down (-z)

anything else : stop

q/z : increase/decrease max speeds by 10%
w/x : increase/decrease only linear speed by 10%
e/c : increase/decrease only angular speed by 10%

CTRL-C to quit
"""

moveBindings = {
    'i': (1, 0, 0, 0),
    'o': (1, 0, 0, -1),
    'j': (0, 0, 0, 1),
    'l': (0, 0, 0, -1),
    'u': (1, 0, 0, 1),
    ',': (-1, 0, 0, 0),
    '.': (-1, 0, 0, 1),
    'm': (-1, 0, 0, -1),
    'O': (1, -1, 0, 0),
    'I': (1, 0, 0, 0),
    'J': (0, 1, 0, 0),
    'L': (0, -1, 0, 0),
    'U': (1, 1, 0, 0),
    '<': (-1, 0, 0, 0),
    '>': (-1, -1, 0, 0),
    'M': (-1, 1, 0, 0),
    't': (0, 0, 1, 0),
    'b': (0, 0, -1, 0),
}

speedBindings = {
    'q': (1.1, 1.1),
    'z': (0.9, 0.9),
    'w': (1.1, 1.0),
    'x': (0.9, 1.0),
    'e': (1.0, 1.1),
    'c': (1.0, 0.9),
}

def checksum_crc8(data: bytes) -> int:
    check = 0
    for b in data:
        check = CRC8_TABLE[check ^ b]
    return check & 0xFF

def build_motor_speed_packet(speeds_dict):
    """
    Constructs the binary serial packet to command motors 1 to 4.
    speeds_dict: dict mapping motor_id (1..4) -> speed in RPS (rotations/sec)
    
    Payload layout:
      [0x01 (SUB_CMD), 4 (count)] + 4 * [motor_idx (uint8), speed (float32-le)]
    """
    payload = bytearray([SUB_CMD_MOTOR_SPEED, 4])
    for motor_id in (1, 2, 3, 4):
        motor_idx, _ = MOTOR_MAP[motor_id]
        speed = float(speeds_dict.get(motor_id, 0.0))
        payload.extend(struct.pack("<Bf", motor_idx, speed))

    packet = bytearray([0xAA, 0x55, PACKET_FUNC_MOTOR, len(payload)])
    packet.extend(payload)
    packet.append(checksum_crc8(bytes(packet[2:])))
    return bytes(packet)

def compute_mecanum_speeds(linear_x, linear_y, angular_z,
                           wheelbase=WHEELBASE, track_width=TRACK_WIDTH,
                           wheel_diameter=WHEEL_DIAMETER):
    """
    Calculates individual motor rotational speeds (RPS) for the 4 Mecanum wheels
    from body velocities (linear_x m/s, linear_y m/s, angular_z rad/s).

    Chassis layout:
      Motor 1 (Index 0): Front-Left  (FL)
      Motor 2 (Index 1): Rear-Left   (RL)
      Motor 3 (Index 2): Front-Right (FR)
      Motor 4 (Index 3): Rear-Right  (RR)
    """
    vp = angular_z * (wheelbase + track_width) / 2.0
    
    # Wheel contact velocities (m/s)
    # Right-side motors are mirrored physically; opposite motor sign drives wheel forward.
    v1 = linear_x - linear_y - vp   # Motor 1: FL
    v2 = linear_x + linear_y - vp   # Motor 2: RL
    v3 = -linear_x - linear_y - vp  # Motor 3: FR
    v4 = -linear_x + linear_y - vp  # Motor 4: RR

    # Convert linear velocity (m/s) to rotations per second (RPS)
    wheel_circumference = math.pi * wheel_diameter
    rps1 = v1 / wheel_circumference
    rps2 = v2 / wheel_circumference
    rps3 = v3 / wheel_circumference
    rps4 = v4 / wheel_circumference

    return {1: rps1, 2: rps2, 3: rps3, 4: rps4}

class MotorDriver:
    def __init__(self, port="/dev/ttyACM0", baudrate=1000000, hardware_mode=None):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.hardware = False

        if hardware_mode is False:
            self.hardware = False
            return

        try:
            import serial
            # Try user port or common alternatives if not explicitly forced
            candidate_ports = [self.port]
            if hardware_mode is None:
                candidate_ports += ["/dev/rrc", "/dev/ttyACM1"]

            for p in candidate_ports:
                if os.path.exists(p):
                    try:
                        self.ser = serial.Serial(p, self.baudrate, timeout=1.0)
                        self.ser.rts = False
                        self.ser.dtr = False
                        self.port = p
                        self.hardware = True
                        break
                    except Exception:
                        continue

            if self.hardware:
                time.sleep(0.05)
                self.stop_all()
            elif hardware_mode is True:
                raise RuntimeError(f"Could not open hardware serial port {self.port}")
        except ImportError:
            if hardware_mode is True:
                raise RuntimeError("pyserial is not installed! Run: pip install pyserial")
            self.hardware = False

    def send_speeds(self, speeds_dict):
        pkt = build_motor_speed_packet(speeds_dict)
        if self.hardware and self.ser and self.ser.is_open:
            self.ser.write(pkt)
            self.ser.flush()
        return pkt

    def stop_all(self):
        stops = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        return self.send_speeds(stops)

    def close(self):
        if self.hardware and self.ser and self.ser.is_open:
            try:
                self.stop_all()
                self.ser.close()
            except Exception:
                pass

def getKey(settings):
    if sys.platform == 'win32':
        return msvcrt.getwch()
    else:
        tty.setraw(sys.stdin.fileno())
        key = sys.stdin.read(1)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        return key

def saveTerminalSettings():
    if sys.platform == 'win32':
        return None
    return termios.tcgetattr(sys.stdin)

def restoreTerminalSettings(old_settings):
    if sys.platform == 'win32' or old_settings is None:
        return
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def vels(speed, turn):
    return 'currently:\tspeed %.2f\tturn %.2f ' % (speed, turn)

def main():
    parser = argparse.ArgumentParser(description="Teleop script for JetAuto Mecanum robot (Motors 1 to 4)")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--baudrate", type=int, default=1000000, help="Baudrate (default: 1000000)")
    parser.add_argument("--hardware", action="store_true", help="Require hardware serial connection")
    parser.add_argument("--sim", action="store_true", help="Force simulation mode (dry-run)")
    parser.add_argument("--speed", type=float, default=0.50, help="Initial linear speed in m/s (default: 0.50)")
    parser.add_argument("--turn", type=float, default=1.00, help="Initial angular speed in rad/s (default: 1.00)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print motor RPS commands on keypress")
    args = parser.parse_args()

    hw_mode = False if args.sim else (True if args.hardware else None)
    driver = MotorDriver(port=args.port, baudrate=args.baudrate, hardware_mode=hw_mode)

    settings = saveTerminalSettings()

    def signal_handler(sig, frame):
        try:
            driver.stop_all()
            driver.close()
        finally:
            restoreTerminalSettings(settings)
            sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    speed = args.speed
    turn = args.turn
    status = 0

    x = 0.0
    y = 0.0
    z = 0.0
    th = 0.0

    print(BANNER)
    if not driver.hardware:
        print("[Mode: Software Simulation / Dry-Run (No serial port active)]\n")
    else:
        print(f"[Mode: Hardware Actuation connected to {driver.port}]\n")
    print(vels(speed, turn))

    try:
        while True:
            key = getKey(settings)
            if key in moveBindings:
                x = moveBindings[key][0]
                y = moveBindings[key][1]
                z = moveBindings[key][2]
                th = moveBindings[key][3]
            elif key in speedBindings:
                speed = speed * speedBindings[key][0]
                turn = turn * speedBindings[key][1]

                print(vels(speed, turn))
                if status == 14:
                    print(BANNER)
                status = (status + 1) % 15
                continue
            else:
                x = 0.0
                y = 0.0
                z = 0.0
                th = 0.0
                if key == '\x03':  # CTRL-C
                    break

            linear_x = x * speed
            linear_y = y * speed
            angular_z = th * turn

            motor_speeds = compute_mecanum_speeds(linear_x, linear_y, angular_z)
            driver.send_speeds(motor_speeds)

            if args.verbose:
                print(f"[CMD] M1(FL/0): {motor_speeds[1]:+6.2f} rps | "
                      f"M2(RL/1): {motor_speeds[2]:+6.2f} rps | "
                      f"M3(FR/2): {motor_speeds[3]:+6.2f} rps | "
                      f"M4(RR/3): {motor_speeds[4]:+6.2f} rps")

    except Exception as e:
        print(f"\n[Error] {e}")

    finally:
        driver.stop_all()
        driver.close()
        restoreTerminalSettings(settings)
        print("\nMotors stopped. Clean exit.")

if __name__ == '__main__':
    main()
