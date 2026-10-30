import ast
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
path=load('rectangle_path','src/igor_controller/igor_controller/rectangle_path.py')
wheels=load('test_jetauto_wheels','tools/test_jetauto_wheels.py')

class RectangleTests(unittest.TestCase):
    def test_measured_motion_first_five_then_four_with_four_left_turns(self):
        route=path.RectanglePath()
        # Start rotated and translated; the route is relative to measured start.
        x,y,yaw=2.,-3.,.7
        now=0.;corners=[];previous=route.phase
        for _ in range(12000):
            vx,wz=route.update(x,y,yaw,now)
            self.assertNotEqual(route.phase,'FAULT',route.fault)
            if route.phase=='TURN_LEFT':
                self.assertGreaterEqual(wz,0)
            if route.phase=='TURN_LEFT' and previous!='TURN_LEFT':
                corners.append((x,y))
            previous=route.phase
            if route.phase=='DONE':break
            x+=vx*math.cos(yaw)*.05;y+=vx*math.sin(yaw)*.05;yaw+=wz*.05;now+=.05
        self.assertEqual(route.phase,'DONE')
        self.assertEqual(len(corners),4)
        local=[]
        for px,py in corners:
            dx,dy=px-2,py+3
            local.append((math.cos(.7)*dx+math.sin(.7)*dy,-math.sin(.7)*dx+math.cos(.7)*dy))
        for actual,expected in zip(local,[(5,0),(5,4),(0,4),(0,0)]):
            self.assertLess(math.dist(actual,expected),.18)
        self.assertLess(abs(path.wrap(yaw-.7)),.05)

    def test_frozen_pose_times_out_and_never_claims_distance(self):
        route=path.RectanglePath();route.update(0,0,0,0)
        self.assertEqual(route.update(0,0,0,100),(0.,0.))
        self.assertEqual(route.fault,'SEGMENT_TIMEOUT')

    def test_nonfinite_and_path_deviation_latch_zero(self):
        for pose in [(math.nan,0,0),(0,.4,0)]:
            route=path.RectanglePath();route.update(0,0,0,0)
            self.assertEqual(route.update(*pose,1),(0.,0.))
            self.assertEqual(route.phase,'FAULT')
            self.assertEqual(route.update(0,0,0,2),(0.,0.))

    def test_no_right_corner_to_correct_large_overshoot(self):
        route=path.RectanglePath();route.update(0,0,0,0);route.update(5,0,0,25)
        self.assertEqual(route.update(5,0,math.pi/2+.2,26),(0.,0.))
        self.assertEqual(route.fault,'LEFT_TURN_DEVIATION')

    def test_invalid_dimensions_and_speed(self):
        for args in [(0,4,.2,.3),(5,math.inf,.2,.3),(5,4,1,.3)]:
            with self.assertRaises(ValueError):path.RectanglePath(*args)

    def test_wheel_frame_matches_wire_contract(self):
        packet=wheels.packet([.5,0,0,0])
        self.assertEqual(len(packet),27)
        self.assertEqual(packet[:6],bytes.fromhex('aa 55 03 16 01 04'))
        self.assertEqual(packet[-1],wheels.crc8(packet[2:-1]))
        with self.assertRaises(ValueError):wheels.packet([math.nan,0,0,0])

class ActiveControllerGuards(unittest.TestCase):
    def control(self):
        tree=ast.parse((ROOT/'src/igor_controller/igor_controller/controller_node.py').read_text())
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='IgorControllerNode')
        method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_control_loop')
        context={'np':np,'time':SimpleNamespace(monotonic=lambda:10.),'math':math}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'active_controller','exec'),context)
        return context['_control_loop']

    def test_active_source_stale_or_missing_scan_stops_before_inference(self):
        for scan,t in [(None,0),(np.ones(360),9.)]:
            reasons=[]
            node=SimpleNamespace(control_rate_hz=50.,last_cmd_time=10.,use_mock_serial=False,
                latest_ranges=scan,last_scan_time=t,freshness_timeout_sec=.025,
                _stop_for_fault=reasons.append)
            self.control()(node)
            self.assertEqual(reasons,['SCAN_MISSING_OR_STALE'])

    def test_active_source_expired_command_stops(self):
        reasons=[]
        node=SimpleNamespace(control_rate_hz=50.,last_cmd_time=9.,_stop_for_fault=reasons.append)
        self.control()(node)
        self.assertEqual(reasons,['COMMAND_STALE'])


class TimedRectangleTests(unittest.TestCase):
    def test_blind_route_integrates_commands_in_correct_order(self):
        timed=load('timed_rectangle','src/igor_controller/igor_controller/timed_rectangle_path.py')
        route=timed.TimedRectanglePath()
        self.assertEqual([target for kind,target in route.stages if kind=='DRIVE'],[5.,4.,5.,4.])
        safe_vx=safe_wz=0.
        completed=[];last=0
        for _ in range(6000):
            vx,wz=route.update(.05,safe_vx,0.,safe_wz)
            self.assertIsNone(route.fault)
            self.assertGreaterEqual(wz,0)
            if route.index!=last:
                completed.append(last);last=route.index
                safe_vx=safe_wz=0.
            else:safe_vx,safe_wz=vx,wz
            if route.done:break
        self.assertTrue(route.done)
        self.assertEqual(completed,list(range(8)))

    def test_stopped_controller_does_not_accumulate_distance(self):
        timed=load('timed_rectangle2','src/igor_controller/igor_controller/timed_rectangle_path.py')
        route=timed.TimedRectanglePath()
        for _ in range(100):route.update(.05,0.,0.,0.)
        self.assertEqual(route.progress,0.)
        route.update(.5,0.,0.,0.)
        self.assertEqual(route.fault,'BAD_SAMPLE_OR_SCHEDULING_GAP')

class ScanMetadataTests(unittest.TestCase):
    def callback(self):
        tree=ast.parse((ROOT/'src/igor_controller/igor_controller/controller_node.py').read_text())
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='IgorControllerNode')
        method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_scan_callback')
        context={'np':np,'math':math,'LaserScan':object,'time':SimpleNamespace(monotonic=lambda:10.)}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'scan_callback','exec'),context)
        return context['_scan_callback']

    def test_actual_slamtec_359_degree_scan_accepted(self):
        node=SimpleNamespace(get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=1000000000)))
        message=SimpleNamespace(ranges=[1.]*1080,angle_min=-3.1241390705,angle_increment=.0058069801889,
            header=SimpleNamespace(stamp=SimpleNamespace(sec=1,nanosec=0)))
        self.callback()(node,message)
        self.assertEqual(node.last_scan_time,10.)
        message.ranges[0]=math.nan
        self.callback()(node,message)
        self.assertIsNone(node.latest_ranges)
        self.assertEqual(node.last_scan_time,0.)

class ActiveMCUTests(unittest.TestCase):
    def test_missing_physical_serial_does_not_mock(self):
        from unittest.mock import patch
        module=load('active_mcu','src/igor_controller/igor_controller/mcu_driver.py')
        with patch.object(module,'serial',None):
            with self.assertRaises(RuntimeError):module.STM32Driver(mock=False)

    def test_short_motor_write_is_failure_and_nan_not_sent(self):
        module=load('active_mcu2','src/igor_controller/igor_controller/mcu_driver.py')
        mcu=module.STM32Driver(mock=True)
        mcu.mock=False;mcu.ser=SimpleNamespace(is_open=True,write=lambda data:len(data)-1)
        self.assertFalse(mcu.send_motor_speeds(.1,0,0,0))
        self.assertFalse(mcu.send_motor_speeds(math.nan,0,0,0))

if __name__=='__main__':unittest.main()
