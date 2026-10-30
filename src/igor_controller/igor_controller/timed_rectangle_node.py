#!/usr/bin/env python3
"""Supervised 5x4 m rectangle using command dead reckoning; no localization."""
import json
import math
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from .timed_rectangle_path import TimedRectanglePath


class TimedRectangleNode(Node):
    def __init__(self):
        super().__init__('igor_timed_rectangle')
        self.declare_parameter('armed',False)
        self.declare_parameter('output','/tmp/igor_timed_rectangle.jsonl')
        self.armed=bool(self.get_parameter('armed').value)
        self.log=Path(str(self.get_parameter('output').value)).open('x')
        self.route=TimedRectanglePath()
        self.pub=self.create_publisher(Twist,'/cmd_vel_in',10)
        self.create_subscription(LaserScan,'/scan',self.on_scan,qos_profile_sensor_data)
        self.create_subscription(String,'/igor/diagnostics',self.on_diag,10)
        self.create_subscription(Twist,'/igor/cmd_vel_safe',self.on_safe,10)
        self.scan_time=self.diag_time=self.safe_time=None
        self.clear=self.ready=False
        self.safe=(0.,0.,0.)
        self.started=False
        self.halted=False
        self.last=time.monotonic()
        self.created=self.last
        self.pause_until=self.last+2.5
        self.last_index=0
        self.timer=self.create_timer(.05,self.tick)
        self.get_logger().warn('COMMAND DEAD RECKONING: distances approximate; armed='+str(self.armed))

    def on_scan(self,msg):
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        age=self.get_clock().now().nanoseconds/1e9-stamp
        r=list(msg.ranges)
        valid=(len(r)>=180 and math.isfinite(msg.angle_increment)
               and abs(abs(msg.angle_increment)*len(r)-2*math.pi)<.1
               and -.1<=age<.25 and all((math.isfinite(v) and v>.05) or v==math.inf for v in r))
        self.scan_time=time.monotonic() if valid else None
        self.clear=valid and min(r)>.45

    def on_diag(self,msg):
        try:
            d=json.loads(msg.data)
            self.ready=(d.get('safety_permit') is True and d.get('mock') is False
                        and d.get('fpga') is True and not d.get('fault')
                        and d.get('heading',{}).get('calibrated') is True)
        except (ValueError,TypeError,AttributeError):self.ready=False
        self.diag_time=time.monotonic()

    def on_safe(self,msg):
        self.safe=(msg.linear.x,msg.linear.y,msg.angular.z)
        self.safe_time=time.monotonic()

    def command(self,vx=0.,wz=0.):
        if self.armed:
            msg=Twist();msg.linear.x=vx;msg.angular.z=wz
            self.pub.publish(msg)

    def tick(self):
        now=time.monotonic();dt=now-self.last;self.last=now
        if not self.armed:return
        if self.halted:
            self.command()
            return
        fresh=lambda t,limit:t is not None and 0<=now-t<limit
        healthy=(fresh(self.scan_time,.25) and self.clear and fresh(self.safe_time,.15)
                 and fresh(self.diag_time,.50) and self.ready)
        if not healthy:
            self.command()
            if self.started or now-self.created>12:
                self.route.fault='SENSOR_OBSTACLE_OR_CONTROLLER_NOT_READY'
                self.halted=True
                self.get_logger().error(self.route.fault)
                self.record(now,0.,0.)
            return
        if now<self.pause_until:
            self.command()
            return
        self.started=True
        vx,wz=self.route.update(dt,*self.safe)
        if self.route.index!=self.last_index:
            self.get_logger().info('Completed stage '+str(self.last_index+1)+' (estimated)')
            self.last_index=self.route.index
            self.pause_until=now+.5
        if self.route.done or self.route.fault:
            self.halted=True;vx=wz=0.
            self.get_logger().info('Route '+('DONE (command estimate)' if self.route.done else 'FAULT '+self.route.fault))
        self.command(vx,wz)
        self.record(now,vx,wz)

    def record(self,now,vx,wz):
        self.log.write(json.dumps({'monotonic':now,'stage':self.route.index+1,'progress_command_estimate':self.route.progress,
            'nominal':[vx,0.,wz],'safe':self.safe,'done':self.route.done,'fault':self.route.fault,
            'localization':False})+'\n');self.log.flush()


def main(args=None):
    rclpy.init(args=args);node=None
    try:
        node=TimedRectangleNode()
        while rclpy.ok() and not node.halted:
            rclpy.spin_once(node,timeout_sec=.1)
    except KeyboardInterrupt:pass
    finally:
        if node:
            for _ in range(3):node.command();time.sleep(.02)
            node.log.close();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
