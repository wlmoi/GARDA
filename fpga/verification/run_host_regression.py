#!/usr/bin/env python3
"""Exercise the packaged host integration; the reference ./src stays untouched."""
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace
from typing import Any, List, Tuple
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TREE = ROOT / 'software_integration/src'
SOURCE = SOURCE_TREE / 'igor_controller/igor_controller'
spec = importlib.util.spec_from_file_location('tested_fpga_bridge', SOURCE / 'fpga_bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
spec = importlib.util.spec_from_file_location('tested_mcu_driver', SOURCE / 'mcu_driver.py')
mcu_driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcu_driver)
spec = importlib.util.spec_from_file_location('tested_lidar_subsampler', SOURCE_TREE / 'igor_navigation/igor_navigation/drivers/lidar_subsampler.py')
lidar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lidar)


def response(values=(128, -256, 0), header=bytes([0x5a, 0xa5, 2, 6])):
    body = header + struct.pack('<3h', *values)
    return body + bytes([bridge.checksum_crc8(body[2:])])


class SerialFixture:
    def __init__(self, packet=None):
        self.packet = response() if packet is None else packet
        self.writes = []
    def reset_input_buffer(self):
        pass
    def write(self, data):
        self.writes.append(data)
        return len(data)
    def read(self, size):
        return self.packet[:size]


def hardware_fixture(packet=None):
    b = bridge.FPGABridge(mock=True)
    b.mock = False
    b.ser = SerialFixture(packet)
    return b


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.obs = np.zeros(74)
        self.obs[:64] = 1
    def test_source_packet_and_integer_actions(self):
        b = hardware_fixture()
        np.testing.assert_array_equal(b.infer(self.obs), [0.5, -1, 0])
        packet = b.ser.writes[0]
        self.assertEqual(len(packet), 153)
        self.assertEqual(packet[:4], bytes([0x5a, 0xa5, 1, 148]))
        self.assertEqual(struct.unpack('<74h', packet[4:-1]), (256,)*64 + (0,)*10)
        self.assertEqual(packet[-1], bridge.checksum_crc8(packet[2:-1]))
        self.assertTrue(b.last_exchange_ok)
    def test_no_automatic_mock_if_serial_missing(self):
        with patch.object(bridge, 'serial', None):
            with self.assertRaises(bridge.FPGACommunicationError):
                bridge.FPGABridge(mock=False)
    def test_no_automatic_mock_if_port_missing(self):
        with patch.object(bridge, 'serial', SimpleNamespace(Serial=lambda **kw: (_ for _ in ()).throw(OSError('missing port')))):
            with self.assertRaises(bridge.FPGACommunicationError):
                bridge.FPGABridge(mock=False)
    def test_each_bad_response_is_an_error(self):
        packets = [b'', response()[:10], b'\x00'+response()[1:],
                   response(header=bytes([0x5a,0xa5,0x7f,6])),
                   response(header=bytes([0x5a,0xa5,2,5])),
                   response()[:-1]+bytes([response()[-1]^1]),
                   response((257,0,0)),response((-257,0,0))]
        for packet in packets:
            with self.subTest(packet=packet.hex()):
                b = hardware_fixture(packet)
                with self.assertRaises(bridge.FPGACommunicationError):
                    b.infer(self.obs)
                self.assertFalse(b.last_exchange_ok)
    def test_input_shape_nan_infinity_and_domain(self):
        invalid = [np.zeros(73),np.zeros((74,1))]
        for index,value in [(0,-0.1),(0,1.1),(64,1.1),(73,-1.1),(1,float('nan')),(65,float('inf'))]:
            obs = self.obs.copy(); obs[index]=value; invalid.append(obs)
        for obs in invalid:
            with self.subTest(shape=obs.shape):
                b = hardware_fixture()
                with self.assertRaises(bridge.FPGACommunicationError): b.infer(obs)
                self.assertEqual(b.ser.writes,[])
    def test_short_write_and_serial_exception(self):
        for writer in [lambda data: len(data)-1,lambda data: (_ for _ in ()).throw(OSError('unplugged'))]:
            b=hardware_fixture(); b.ser.write=writer
            with self.assertRaises(bridge.FPGACommunicationError): b.infer(self.obs)
    def test_quantization_ties_even_and_negative(self):
        b=hardware_fixture(); self.obs[64:68]=[0.5/256,1.5/256,-0.5/256,-1.5/256]
        b.infer(self.obs)
        self.assertEqual(struct.unpack('<74h',b.ser.writes[0][4:-1])[64:68],(0,2,0,-2))
    def test_failed_exchange_latches_against_late_valid_response(self):
        b=hardware_fixture(b'')
        with self.assertRaises(bridge.FPGACommunicationError): b.infer(self.obs)
        b.ser.packet=response()
        with self.assertRaises(bridge.FPGACommunicationError): b.infer(self.obs)
        self.assertEqual(len(b.ser.writes),1,'A late reply must not cause an implicit retry')
    def test_total_deadline_rejects_slow_write_and_slow_read(self):
        for clock_values in ([10.,10.021],[10.,10.001,10.021]):
            b=hardware_fixture()
            with patch.object(bridge.time,'monotonic',side_effect=clock_values):
                with self.assertRaises(bridge.FPGACommunicationError): b.infer(self.obs)
            self.assertFalse(b.last_exchange_ok)


class MCUTests(unittest.TestCase):
    def test_no_automatic_mock_if_serial_missing_or_port_unavailable(self):
        for provider in (None,SimpleNamespace(Serial=lambda **kw: (_ for _ in ()).throw(OSError('missing port')))):
            with patch.object(mcu_driver,'serial',provider):
                with self.assertRaises(RuntimeError): mcu_driver.STM32Driver(mock=False)
    def test_short_motor_write_is_not_success(self):
        driver=mcu_driver.STM32Driver(mock=True)
        driver.mock=False
        driver.ser=SimpleNamespace(is_open=True,write=lambda data:len(data)-1)
        self.assertFalse(driver.send_motor_speeds(0.,0.,0.,0.))
    def test_explicit_mock_imu_timestamp_is_monotonic(self):
        driver=mcu_driver.STM32Driver(mock=True)
        with patch.object(mcu_driver.time,'monotonic',return_value=1234.5):
            self.assertEqual(driver.get_latest_imu()[2],1234.5)


class Publisher:
    def __init__(self): self.messages=[]
    def publish(self,msg): self.messages.append(msg)
class Twist:
    def __init__(self):
        self.linear=SimpleNamespace(x=0.,y=0.,z=0.)
        self.angular=SimpleNamespace(x=0.,y=0.,z=0.)
class String:
    data=''
class Float32:
    data=0.


# Compile the actual controller methods with ROS message fixtures. This checks
# production control flow without pretending a ROS installation or robot exists.
tree=ast.parse((SOURCE/'controller_node.py').read_text(encoding='utf-8'))
klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='IgorControllerNode')
methods=[n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name in {'_control_loop','_stop_for_fault','_scan_callback','_cmd_vel_callback'}]
context=dict(np=np,math=math,time=time,json=json,Twist=Twist,String=String,Float32=Float32,
             LaserScan=SimpleNamespace,FPGACommunicationError=bridge.FPGACommunicationError)
exec(compile(ast.Module(body=methods,type_ignores=[]),str(SOURCE/'controller_node.py'),'exec'),context)
cbf_path=SOURCE_TREE/'igor_navigation/igor_navigation/controllers/cbf_safety_filter.py'
cbf_class=next(n for n in ast.parse(cbf_path.read_text(encoding='utf-8')).body if isinstance(n,ast.ClassDef))
cbf_method=next(n for n in cbf_class.body if isinstance(n,ast.FunctionDef) and n.name=='filter_cbf')
cbf_context=dict(np=np,Tuple=Tuple,List=List,Any=Any)
exec(compile(ast.Module(body=[cbf_method],type_ignores=[]),str(cbf_path),'exec'),cbf_context)


class ControllerTests(unittest.TestCase):
    def fixture(self):
        calls=[]
        instant=time.monotonic()
        n=SimpleNamespace(use_fpga=True,use_mock_serial=False,algorithm='cl_drl',
            control_rate_hz=50,last_cmd_time=instant,last_scan_time=instant,
            cmd_linear_x=.3,cmd_linear_y=0.,cmd_angular_z=0.,latest_ranges=np.ones(360),
            scan_angle_min=0.,scan_angle_end=2*np.pi,scan_error=None,
            lidar_subsampler=lidar.LidarSubsampler(),
            mcu=SimpleNamespace(send_motor_speeds=lambda *a:(calls.append(a) or True),
                get_latest_imu=lambda:((0,0,1),(0,0,0),instant)),
            heading_engine=SimpleNamespace(update_imu=lambda *a,**k:None,
                update_command=lambda *a,**k:None,get_heading_difference=lambda:0.,
                get_normalized_heading_error=lambda:0.,get_diagnostics=lambda:{}),
            kinematics=SimpleNamespace(wheelbase=.216,track_width=.195,wheel_diameter=.0965,max_rps=5.),
            cpu_controller=None,fpga=SimpleNamespace(infer=lambda obs:np.zeros(3)),
            pub_safe_twist=Publisher(),pub_diag=Publisher(),pub_heading=Publisher())
        n._stop_for_fault=lambda reason: context['_stop_for_fault'](n,reason)
        return n,calls
    def assert_stop(self,node,calls,reason):
        context['_control_loop'](node)
        self.assertEqual(calls,[(0.,0.,0.,0.)])
        d=json.loads(node.pub_diag.messages[-1].data)
        self.assertFalse(d['safety_permit'])
        self.assertIn(reason,d['fault'])
        self.assertEqual(d['safe'],[0,0,0])
        self.assertEqual(node.pub_safe_twist.messages[-1].linear.x,0)
    def test_transport_failure_stops_original_nonzero_command(self):
        n,c=self.fixture()
        n.fpga=SimpleNamespace(infer=lambda obs: (_ for _ in ()).throw(bridge.FPGACommunicationError('CRC')))
        self.assert_stop(n,c,'FPGA_TRANSPORT')
    def test_command_watchdog_stops_without_inference(self):
        n,c=self.fixture(); n.last_cmd_time-=1
        self.assert_stop(n,c,'COMMAND_STALE')
    def test_missing_and_frozen_lidar_stop(self):
        for age in (None,time.monotonic()-1):
            n,c=self.fixture(); n.last_scan_time=age
            self.assert_stop(n,c,'SCAN_MISSING_OR_STALE')
    def test_invalid_command_stops(self):
        for value in (float('nan'),float('inf'),.61,-.61):
            n,c=self.fixture(); n.cmd_linear_x=value
            self.assert_stop(n,c,'COMMAND_INVALID')
    def test_nonfinite_sensor_stops(self):
        for value in (float('nan'),float('inf'),-float('inf')):
            n,c=self.fixture(); n.mcu.get_latest_imu=lambda:((value,0,1),(0,0,0),time.monotonic())
            self.assert_stop(n,c,'OBSERVATION_NONFINITE')
    def test_missing_stale_and_future_imu_stop(self):
        for stamp in (0.,time.monotonic()-1,time.monotonic()+1,float('nan')):
            n,c=self.fixture(); n.mcu.get_latest_imu=lambda:((0,0,1),(0,0,0),stamp)
            self.assert_stop(n,c,'IMU_MISSING_OR_STALE')
    def test_valid_zero_residual_preserves_valid_operator_command(self):
        n,c=self.fixture(); n.latest_ranges=np.full(360,3.5)
        context['_control_loop'](n)
        self.assertEqual(len(c),1)
        self.assertGreater(c[0][0],0)
        self.assertAlmostEqual(n.pub_safe_twist.messages[-1].linear.x,.3,places=6)
    def test_zero_operator_command_cannot_become_policy_motion(self):
        n,c=self.fixture(); n.cmd_linear_x=0.; n.fpga.infer=lambda obs:np.ones(3)
        context['_control_loop'](n)
        self.assertEqual(c,[(0.,0.,0.,0.)])
    def test_real_cbf_no_longer_bypasses_critical_distance_stop(self):
        n,c=self.fixture(); n.algorithm='cl_drl_cbf'; n.latest_ranges=np.full(360,.15)
        cbf=SimpleNamespace(robot_radius=.22,safe_margin=.06,gamma=3.5,min_cmd_vx=-.15,max_cmd_vy=.5)
        cbf.filter_cbf=lambda **kw:cbf_context['filter_cbf'](cbf,**kw)
        n.cpu_controller=cbf
        context['_control_loop'](n)
        self.assertEqual(c,[(0.,0.,0.,0.)])
    def test_final_envelope_and_all_axis_limits_after_filter(self):
        for candidate,expected in [((10.,10.,10.),(.375,.5,2.)),((-10.,-10.,-10.),(-.15,-.5,-2.))]:
            n,c=self.fixture(); n.algorithm='cl_drl_cbf'; n.latest_ranges=np.full(360,.8)
            n.cpu_controller=SimpleNamespace(filter_cbf=lambda **kw:(*candidate,False))
            context['_control_loop'](n)
            twist=n.pub_safe_twist.messages[-1]
            np.testing.assert_allclose([twist.linear.x,twist.linear.y,twist.angular.z],expected,rtol=1e-6)
    def test_nonfinite_filter_output_stops(self):
        n,c=self.fixture(); n.algorithm='cl_drl_cbf'
        n.cpu_controller=SimpleNamespace(filter_cbf=lambda **kw:(float('nan'),0.,0.,False))
        self.assert_stop(n,c,'CONTROLLER_OUTPUT_INVALID')
    def scan_message(self,ranges,angle_min=0.):
        return SimpleNamespace(ranges=ranges,angle_min=angle_min,angle_increment=2*np.pi/360)
    def test_invalid_scan_does_not_refresh_lease_or_become_clear(self):
        for ranges in ([],[1.]*2,[float('nan')]*360,[-float('inf')]*360,[0.]*360,[-1.]*360):
            n,c=self.fixture()
            context['_scan_callback'](n,self.scan_message(ranges))
            self.assertIsNone(n.last_scan_time)
            self.assert_stop(n,c,'SCAN_INVALID')
    def test_scan_metadata_and_positive_infinity_no_return(self):
        n,c=self.fixture(); ranges=np.full(360,float('inf'))
        ranges[170:191]=.15
        context['_scan_callback'](n,self.scan_message(ranges,-np.pi))
        self.assertIsNotNone(n.last_scan_time)
        self.assertAlmostEqual(n.scan_angle_min,-np.pi)
        context['_control_loop'](n)
        self.assertEqual(c,[(0.,0.,0.,0.)],'Obstacle at angle zero must remain in the frontal sector')
    def test_incomplete_fov_scan_is_invalid(self):
        n,c=self.fixture(); msg=self.scan_message([1.]*360); msg.angle_increment=np.pi/360
        context['_scan_callback'](n,msg)
        self.assert_stop(n,c,'SCAN_INVALID')
    def test_command_expires_during_compute(self):
        n,c=self.fixture(); clock=SimpleNamespace(value=1000.)
        n.last_cmd_time=999.51; n.last_scan_time=1000.
        n.mcu.get_latest_imu=lambda:((0,0,1),(0,0,0),1000.)
        def inference(obs): clock.value=1000.02; return np.zeros(3)
        n.fpga.infer=inference
        with patch.object(time,'monotonic',side_effect=lambda:clock.value):
            self.assert_stop(n,c,'COMMAND_STALE_AFTER_COMPUTE')
    def test_scan_expires_during_compute(self):
        n,c=self.fixture(); clock=SimpleNamespace(value=1000.)
        n.last_cmd_time=1000.; n.last_scan_time=999.51
        n.mcu.get_latest_imu=lambda:((0,0,1),(0,0,0),1000.)
        def inference(obs): clock.value=1000.02; return np.zeros(3)
        n.fpga.infer=inference
        with patch.object(time,'monotonic',side_effect=lambda:clock.value):
            self.assert_stop(n,c,'SENSOR_STALE_AFTER_COMPUTE')
    def test_wall_clock_jump_does_not_extend_motor_leases(self):
        n,c=self.fixture(); n.latest_ranges=np.full(360,3.5)
        with patch.object(time,'time',return_value=-1000000.): context['_control_loop'](n)
        self.assertGreater(c[0][0],0)
        n,c=self.fixture(); n.last_cmd_time-=1
        with patch.object(time,'time',return_value=-1000000.): self.assert_stop(n,c,'COMMAND_STALE')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    output=ROOT/'evidence/current_host'
    output.mkdir(parents=True,exist_ok=True)
    tested=[SOURCE/'fpga_bridge.py',SOURCE/'controller_node.py',SOURCE/'mcu_driver.py',cbf_path,
            SOURCE_TREE/'igor_navigation/igor_navigation/drivers/lidar_subsampler.py',Path(__file__).resolve()]
    (output/'results.json').write_text(json.dumps({'scope':'software fixtures; no physical hardware',
        'sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in tested},
        'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'success':result.wasSuccessful()},indent=2)+'\n',encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
