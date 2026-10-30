#!/usr/bin/env python3
"""Run the rectangle through IGOR only with fresh measured pose, scan and diagnostics."""
import json
import math
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseStamped, Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from .rectangle_path import RectanglePath


class RectangleRouteNode(Node):
    def __init__(self):
        super().__init__('igor_rectangle_route')
        for name, value in [('armed', False), ('measured_pose_confirmed', False),
                            ('pose_topic', '/pose'), ('first_side_m', 5.), ('second_side_m', 4.),
                            ('speed_mps', .20), ('turn_speed_radps', .30)]:
            self.declare_parameter(name, value)
        self.path = RectanglePath(*[float(self.get_parameter(n).value) for n in
                                  ('first_side_m','second_side_m','speed_mps','turn_speed_radps')])
        self.armed = bool(self.get_parameter('armed').value)
        if self.armed and not self.get_parameter('measured_pose_confirmed').value:
            raise ValueError('Confirm a measured localization source; command-integrated /pose is unsuitable')
        self.pose = None
        self.pose_time = self.scan_time = self.diag_time = None
        self.pose_frame = None
        self.clear = self.controller_ready = False
        self.started = False
        self.last_state = None
        self.pub = self.create_publisher(Twist, '/cmd_vel_in', 10)
        self.status = self.create_publisher(String, '/igor/rectangle_status', 10)
        self.create_subscription(PoseStamped, str(self.get_parameter('pose_topic').value), self.on_pose, 10)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(String, '/igor/diagnostics', self.on_diag, 10)
        self.timer = self.create_timer(.05, self.tick)
        self.get_logger().info('Rectangle 5 then 4 m, four left turns. Armed='+str(self.armed))

    def on_pose(self, msg):
        p,q = msg.pose.position, msg.pose.orientation
        values = (p.x,p.y,q.x,q.y,q.z,q.w)
        norm = sum(v*v for v in (q.x,q.y,q.z,q.w))
        stamp = msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        age = self.get_clock().now().nanoseconds/1e9-stamp
        if (not all(math.isfinite(v) for v in values) or not .99 < norm < 1.01
                or not -.1 <= age < .25 or not msg.header.frame_id):
            self.pose_time = None
            return
        if self.pose_frame and msg.header.frame_id != self.pose_frame:
            self.pose_time = None
            self.path.abort('POSE_FRAME_CHANGED')
            return
        self.pose_frame = msg.header.frame_id
        yaw = math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        now = time.monotonic()
        if self.pose is not None and self.pose_time is not None:
            dt = now-self.pose_time
            if math.hypot(p.x-self.pose[0],p.y-self.pose[1]) > .10+dt*.8:
                self.path.abort('POSE_JUMP')
        self.pose = (p.x,p.y,yaw)
        self.pose_time = now

    def on_scan(self, msg):
        ranges = list(msg.ranges)
        stamp = msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        age = self.get_clock().now().nanoseconds/1e9-stamp
        valid = (len(ranges)>=180 and math.isfinite(msg.angle_increment)
                 and abs(abs(msg.angle_increment)*len(ranges)-2*math.pi)<.1
                 and -.1<=age<.25 and all((math.isfinite(v) and v>0) or v==math.inf for v in ranges))
        self.scan_time = time.monotonic() if valid else None
        # Conservative all-around clearance for initial rectangle acceptance.
        self.clear = valid and min(ranges)>.45

    def on_diag(self, msg):
        try:
            data=json.loads(msg.data)
            self.controller_ready=(data.get('safety_permit') is True and data.get('mock') is False
                                   and data.get('fpga') is True and not data.get('fault'))
        except (ValueError, TypeError, AttributeError):
            self.controller_ready=False
        self.diag_time=time.monotonic()

    def stop(self):
        self.pub.publish(Twist())

    def tick(self):
        now=time.monotonic()
        fresh=lambda t: t is not None and 0<=now-t<.25
        ready=(fresh(self.pose_time) and fresh(self.scan_time) and self.clear
               and self.diag_time is not None and 0<=now-self.diag_time<.5 and self.controller_ready)
        if not self.armed:
            return  # Disarmed node does not contend with another command source.
        if not ready:
            self.stop()
            if self.started:
                self.path.abort('POSE_SCAN_OR_CONTROLLER_NOT_READY')
            state=self.path.fault or 'WAITING_FOR_MEASURED_POSE_SCAN_AND_HARDWARE_CONTROLLER'
        else:
            self.started=True
            vx,wz=self.path.update(*self.pose,now)
            msg=Twist();msg.linear.x=vx;msg.angular.z=wz
            self.pub.publish(msg)
            state=f'{self.path.phase} side={self.path.side+1} fault={self.path.fault}'
        if state!=self.last_state:
            self.get_logger().info(state)
            self.status.publish(String(data=state))
            self.last_state=state


def main(args=None):
    rclpy.init(args=args)
    node=None
    try:
        node=RectangleRouteNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            if node.armed:
                for _ in range(3):node.stop();time.sleep(.02)
            node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
