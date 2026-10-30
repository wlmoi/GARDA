#!/usr/bin/env python3
"""Zero-command hardware preflight, then optional supervised command-estimated rectangle."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--floor-ready',action='store_true')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if args.run and not args.floor_ready:parser.error('--run requires --floor-ready')
    args.output_dir.mkdir(parents=True,exist_ok=False)
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan
    from geometry_msgs.msg import Twist
    from std_msgs.msg import String
    from ament_index_python.packages import get_package_prefix
    rclpy.init();node=Node('igor_rectangle_supervisor')
    pub=node.create_publisher(Twist,'/cmd_vel_in',10)
    scans=[];diagnostics=[];safe=[];faults=Counter()
    def scan(msg):
        vals=list(msg.ranges)
        finite=[v for v in vals if math.isfinite(v) and v>0]
        scans.append({'time':time.monotonic(),'min_m':min(finite) if finite else 0.,'samples':len(vals)})
    def diag(msg):
        try:d=json.loads(msg.data)
        except ValueError:return
        diagnostics.append(d)
        if d.get('fault'):faults[d['fault']]+=1
    def velocity(msg):safe.append([msg.linear.x,msg.linear.y,msg.angular.z])
    subscriptions=[node.create_subscription(LaserScan,'/scan',scan,qos_profile_sensor_data),
                   node.create_subscription(String,'/igor/diagnostics',diag,10),
                   node.create_subscription(Twist,'/igor/cmd_vel_safe',velocity,10)]
    def executable(package,name):return str(Path(get_package_prefix(package))/'lib'/package/name)
    processes=[];files=[];report={'motion_requested':args.run,'preflight_pass':False}
    def start(name,command):
        stream=(args.output_dir/(name+'.log')).open('x');files.append(stream)
        process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append(process);return process
    def interrupted(signum,frame):raise KeyboardInterrupt
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,interrupted)
    try:
        lidar=start('lidar',[executable('rplidar_ros','rplidar_node'),'--ros-args','-p','serial_port:=/dev/lidar','-p','serial_baudrate:=115200','-p','angle_compensate:=true','-p','frame_id:=laser'])
        controller=start('controller',[executable('igor_controller','controller_node'),'--ros-args',
            '-p','algorithm:=cl_drl_cbf','-p','use_fpga:=true','-p','use_mock_serial:=false',
            '-p','fpga_port:=/dev/ttyTHS1','-p','fpga_baudrate:=921600','-p','fpga_timeout:=0.02',
            '-p','mcu_port:=/dev/ttyACM0','-p','sensor_freshness_timeout_ms:=150.0'])
        end=time.monotonic()+10
        while time.monotonic()<end:
            pub.publish(Twist());rclpy.spin_once(node,timeout_sec=.03)
            if any(p.poll() is not None for p in processes):break
        healthy=[d for d in diagnostics if d.get('safety_permit') is True and d.get('mock') is False and d.get('heading',{}).get('calibrated') is True]
        report.update(scans=len(scans),healthy_diagnostics=len(healthy),faults=dict(faults),
            minimum_scan_m=min((s['min_m'] for s in scans[-10:]),default=0),
            all_preflight_commands_zero=all(not any(v) for v in safe),sensor_lease_ms=150.)
        report['preflight_pass']=(len(scans)>=10 and len(healthy)>=5 and all(p.poll() is None for p in processes)
            and report['all_preflight_commands_zero'] and report['minimum_scan_m']>.45)
        print('PREFLIGHT',json.dumps(report),flush=True)
        if not report['preflight_pass']:
            for name in ('lidar','controller'):
                print(name+' log tail:\n'+'\n'.join((args.output_dir/(name+'.log')).read_text().splitlines()[-15:]),flush=True)
            return 1
        if not args.run:return 0
        capture=args.output_dir/'route.jsonl'
        route=start('route',[executable('igor_controller','timed_rectangle'),'--ros-args','-p','armed:=true',
            '-p','output:='+str(capture.resolve())])
        deadline=time.monotonic()+190
        last_line=None
        while route.poll() is None and time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.1)
            if lidar.poll() is not None or controller.poll() is not None:
                raise RuntimeError('Hardware node exited')
            if capture.exists():
                lines=capture.read_text().splitlines()
                if lines:
                    latest=json.loads(lines[-1]);state=(latest['stage'],latest['done'],latest['fault'])
                    if state!=last_line:
                        print('ROUTE',state,flush=True);last_line=state
        if route.poll() is None:raise RuntimeError('Total route deadline exceeded')
        lines=capture.read_text().splitlines() if capture.exists() else []
        final=json.loads(lines[-1]) if lines else {}
        report['route_final']=final
        print('ROUTE RESULT',json.dumps(final),flush=True)
        return 0 if final.get('done') and not final.get('fault') else 1
    except KeyboardInterrupt:
        report['interrupted']=True;return 130
    finally:
        # Stop the route publisher first, then send zeros before controller shutdown.
        if len(processes)>2 and processes[-1].poll() is None:
            os.killpg(processes[-1].pid,signal.SIGINT)
            try:processes[-1].wait(timeout=2)
            except subprocess.TimeoutExpired:processes[-1].terminate()
        for _ in range(5):pub.publish(Twist());rclpy.spin_once(node,timeout_sec=.03)
        for p in reversed(processes):
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGINT)
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=3)
        for stream in files:stream.close()
        # Independent final zero packet, after the controller releases the port.
        from test_jetauto_wheels import packet
        import serial
        try:
            with serial.Serial('/dev/ttyACM0',1000000,timeout=.1,write_timeout=.2,exclusive=True) as link:
                for _ in range(3):
                    raw=packet([0.]*4)
                    if link.write(raw)!=len(raw):raise RuntimeError('Short final STOP')
                    link.flush();time.sleep(.02)
            report['final_stop_sent']=True
        except Exception as exc:report['final_stop_error']=str(exc)
        (args.output_dir/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        node.destroy_node();rclpy.shutdown()

if __name__=='__main__':raise SystemExit(main())
