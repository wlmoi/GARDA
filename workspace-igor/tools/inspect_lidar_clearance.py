#!/usr/bin/env python3
"""Report close physical LiDAR returns; no chassis/motor controller is opened."""
import json
import math
from pathlib import Path
import signal
import subprocess
import time
import argparse
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rclpy.init();node=Node('igor_clearance_diagnostic');records=[]
    def scan(m):
        returns=[(float(v),math.degrees(m.angle_min+i*m.angle_increment))
                 for i,v in enumerate(m.ranges) if math.isfinite(v) and v>0]
        records.append({'closest':sorted(returns)[:12],
                        'under_45cm':sum(v<.45 for v,a in returns),
                        'stamp':m.header.stamp.sec+m.header.stamp.nanosec*1e-9})
    sub=node.create_subscription(LaserScan,'/scan',scan,qos_profile_sensor_data)
    with args.output.open('x') as out, open('/tmp/igor-clearance-driver.log','w') as log:
        p=subprocess.Popen(['/opt/ros/humble/lib/rplidar_ros/rplidar_node','--ros-args','-p','serial_port:=/dev/lidar',
            '-p','serial_baudrate:=115200','-p','angle_compensate:=true'],stdout=log,stderr=subprocess.STDOUT)
        try:
            end=time.monotonic()+8
            while time.monotonic()<end and len(records)<10 and p.poll() is None:
                rclpy.spin_once(node,timeout_sec=.1)
        finally:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=3)
            json.dump(records,out,indent=2);out.write('\n')
            node.destroy_node();rclpy.shutdown()
    print(json.dumps(records[-1] if records else {'error':'No scans'},indent=2))

if __name__=='__main__':main()
