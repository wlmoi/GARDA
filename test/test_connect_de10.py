"""Connection automation tests with simulated console/processes; no hardware claim."""
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('connect_de10',ROOT/'tools/connect_de10.py')
connect=importlib.util.module_from_spec(spec);spec.loader.exec_module(connect)

class SerialFixture:
    def __init__(self,chunks):self.chunks=list(chunks);self.writes=[]
    @property
    def in_waiting(self):return len(self.chunks[0]) if self.chunks else 0
    def read(self,size):return self.chunks.pop(0).encode() if self.chunks else b''
    def write(self,value):self.writes.append(value);return len(value)

class ConnectTests(unittest.TestCase):
    def test_jetson_interface_and_ambiguity(self):
        links=[{'ifname':'wlP1p1s0','link_type':'ether'},{'ifname':'enP8p1s0','link_type':'ether'}]
        self.assertEqual(connect.choose_interface(links),'enP8p1s0')
        self.assertEqual(connect.choose_interface([{'ifname':'eth0','link_type':'ether'}]),'eth0')
        with self.assertRaises(connect.ConnectionError):connect.choose_interface([{'ifname':'eth0','link_type':'ether'},{'ifname':'eno1','link_type':'ether'}])
        with self.assertRaises(connect.ConnectionError):connect.choose_interface(links,'missing')

    def test_reject_jetson_identity(self):
        self.assertFalse(connect.is_de10('aarch64\n5.15.148-tegra\nnvidia,orin'))
        self.assertFalse(connect.is_de10('armv7l\n5.15\nraspberrypi'))
        self.assertTrue(connect.is_de10('armv7l\n5.15-socfpga\nterasic,de10-nano'))

    def test_neighbor_discovery_uses_only_wired_subnet_and_valid_entries(self):
        neighbors=[{'dst':'192.168.50.2','lladdr':'aa','state':['STALE']},
                   {'dst':'172.16.17.203','lladdr':'bb','state':['REACHABLE']},
                   {'dst':'192.168.50.3','lladdr':'cc','state':['FAILED']},
                   {'dst':'192.168.50.4','state':['INCOMPLETE']},
                   {'dst':'fe80::1','lladdr':'dd','state':['REACHABLE']},
                   {'dst':'192.168.50.1','lladdr':'ee','state':['REACHABLE']}]
        result=SimpleNamespace(returncode=0,stdout=json.dumps(neighbors))
        with patch.object(connect.subprocess,'run',return_value=result) as runner, \
             patch.object(connect,'ssh_ready',return_value=True) as probe:
            self.assertEqual(connect.discover_peer('enP8p1s0','192.168.50.1'),['192.168.50.2'])
            self.assertEqual(runner.call_args.args[0],['ip','-j','neigh','show','dev','enP8p1s0'])
            probe.assert_called_once_with('192.168.50.2','192.168.50.1')

    def test_ssh_probe_binds_jetson_wired_address(self):
        link=Mock();context=Mock();context.__enter__=Mock(return_value=link);context.__exit__=Mock(return_value=False)
        with patch.object(connect.socket,'socket',return_value=context):
            self.assertTrue(connect.ssh_ready('192.168.50.2','192.168.50.1'))
            link.bind.assert_called_once_with(('192.168.50.1',0))
            link.connect.assert_called_once_with(('192.168.50.2',22))
            link.connect.side_effect=OSError('unreachable')
            self.assertFalse(connect.ssh_ready('192.168.50.2','192.168.50.1'))

    def test_console_autodetection_does_not_probe_robot_ports(self):
        ftdi=SimpleNamespace(device='/dev/ttyUSB0',vid=0x0403,pid=0x6001,description='FT232R')
        stm=SimpleNamespace(device='/dev/ttyACM0',vid=0x0483,pid=0x5740,description='STM32')
        with patch('serial.tools.list_ports.comports',return_value=[stm]):
            with self.assertRaises(connect.ConnectionError):connect.choose_console()
        with patch('serial.tools.list_ports.comports',return_value=[stm,ftdi]):
            self.assertEqual(connect.choose_console(),'/dev/ttyUSB0')
        with patch('serial.tools.list_ports.comports',return_value=[ftdi,ftdi]):
            with self.assertRaises(connect.ConnectionError):connect.choose_console()

    def test_usb_absent_does_not_load_random_drivers(self):
        with patch.object(connect,'choose_console',side_effect=connect.ConnectionError('tidak ada tty')), \
             patch.object(connect,'usb_inventory',return_value=[{'vid':0x09fb,'pid':0x6010,'product':'USB-Blaster'}]), \
             patch.object(connect,'run') as runner,patch('builtins.print'):
            with self.assertRaisesRegex(connect.ConnectionError,'hanya JTAG'):connect.ensure_console()
            runner.assert_not_called()

    def test_enumerated_ftdi_gets_driver_then_port_is_rechecked(self):
        with patch.object(connect,'choose_console',side_effect=[connect.ConnectionError('no tty'),'/dev/ttyUSB0']), \
             patch.object(connect,'usb_inventory',return_value=[{'vid':0x0403,'pid':0x6001,'product':'FT232R'}]), \
             patch.object(connect.os,'geteuid',return_value=1000,create=True), \
             patch.object(connect.shutil,'which',side_effect=lambda name:'/sbin/modprobe' if name=='modprobe' else None), \
             patch.object(connect,'run') as runner,patch('builtins.print'):
            self.assertEqual(connect.ensure_console(),'/dev/ttyUSB0')
            runner.assert_called_once_with(['sudo','modprobe','ftdi_sio'])

    def test_usb_inventory_from_sysfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,vid,pid in [('usb1','1d6b','0002'),('1-1','0403','6001')]:
                folder=root/name;folder.mkdir()
                (folder/'idVendor').write_text(vid);(folder/'idProduct').write_text(pid)
                (folder/'product').write_text('test')
            self.assertEqual(connect.usb_inventory(root),[{'vid':0x0403,'pid':0x6001,'product':'test'}])

    def console(self,chunks):
        console=connect.Console.__new__(connect.Console);console.user='fpga';console.serial=SerialFixture(chunks)
        return console

    def test_console_command_ignores_echo_and_handles_fragments(self):
        console=self.console(["echo 'IGOR_fixed_START'; echo 'IGOR_fixed_END:0'\r\n",
                              '\nIGOR_fixed_START\r\nhello', ' world\r\nIGOR_fixed_END:0\r\n'])
        with patch.object(connect.uuid,'uuid4',return_value=SimpleNamespace(hex='fixed')):
            self.assertEqual(console.command('echo hello world'),'hello world')

    def test_console_sudo_password_is_not_a_shell_command(self):
        console=self.console(['\nIGOR_fixed_START\nIGOR_fixed: ', '\nconfigured\nIGOR_fixed_END:0\n'])
        with patch.object(connect.uuid,'uuid4',return_value=SimpleNamespace(hex='fixed')), \
             patch.object(connect.getpass,'getpass',return_value='secret'):
            output=console.command('ip link set eth0 up',privileged=True)
        self.assertEqual(console.serial.writes[-1],b'secret\r')
        self.assertNotIn('secret',console.serial.writes[0].decode())
        self.assertNotIn('secret',output)

    def test_console_failed_command_not_success(self):
        console=self.console(['\nIGOR_fixed_START\npermission denied\nIGOR_fixed_END:1\n'])
        with patch.object(connect.uuid,'uuid4',return_value=SimpleNamespace(hex='fixed')):
            with self.assertRaises(connect.ConnectionError):console.command('false')

    def test_wrong_console_never_changes_remote_ip(self):
        console=SimpleNamespace(command=Mock(return_value='aarch64\n5.15-tegra\nnvidia'))
        args=SimpleNamespace(hps_interface='eth0',hps_ip='192.168.50.2')
        with self.assertRaises(connect.ConnectionError):connect.configure_hps(console,args)
        self.assertEqual(console.command.call_count,1)

    def test_hps_setup_runs_only_after_identity_check(self):
        console=SimpleNamespace(command=Mock(side_effect=['armv7l\n5.15-socfpga\naltr,socfpga','eth0','ok','ok']))
        args=SimpleNamespace(hps_interface=None,hps_ip='192.168.50.2')
        with patch('builtins.print'):connect.configure_hps(console,args)
        commands=console.command.call_args_list
        self.assertEqual(len(commands),4)
        self.assertIn('192.168.50.2/24',commands[2].args[0])
        self.assertTrue(commands[2].kwargs['privileged'])

    def test_serial_argument_is_shell_quoted(self):
        value='/dev/serial/by-id/test; echo unsafe'
        self.assertEqual(shlex.split(connect.remote_serial_command(value)),[value])
        self.assertIn('len(p)==1',connect.remote_serial_command(None))

    def test_remote_directory_quotes_user_input(self):
        self.assertEqual(shlex.split(connect.remote_directory('some dir; echo unsafe')),['some dir; echo unsafe'])
        self.assertEqual(connect.remote_directory('~/igor_ws'),'"$HOME"/igor_ws')
        self.assertEqual(connect.remote_directory('~'),'"$HOME"')

    def test_local_machine_identity(self):
        with patch.object(connect.Path,'read_bytes',return_value=b'nvidia,tegra234'),patch.object(connect.platform,'release',return_value='generic'):
            self.assertTrue(connect.is_jetson())
        with patch.object(connect.Path,'read_bytes',side_effect=FileNotFoundError),patch.object(connect.platform,'release',return_value='5.15-socfpga'):
            self.assertFalse(connect.is_jetson())

    def test_check_only_has_no_mutations_or_console_access(self):
        links=[{'ifname':'enP8p1s0','link_type':'ether','flags':['UP']}]
        outputs=[SimpleNamespace(stdout=json.dumps(links)),SimpleNamespace(stdout='enP8p1s0 DOWN')]
        with patch('sys.argv',['connect_de10.py','--check-only']),patch.object(connect.sys,'platform','linux'), \
             patch.object(connect.shutil,'which',return_value='/usr/sbin/ip'), \
             patch.object(connect,'run',side_effect=outputs) as runner, \
             patch.object(connect,'carrier',return_value=False),patch.object(connect,'Console') as console,patch('builtins.print'):
            self.assertEqual(connect.main(),0)
            console.assert_not_called()
            self.assertEqual(runner.call_count,2)
            for call in runner.call_args_list:
                self.assertNotIn('sudo',call.args[0]);self.assertNotIn('replace',call.args[0])

    def test_standalone_script_extracts_assets_and_runs_without_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);script=folder/'de10_connect.py'
            shutil.copyfile(ROOT/'tools/de10_connect.py',script)
            for _ in range(2):
                result=subprocess.run([sys.executable,str(script),'--help'],cwd=folder,
                                      capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('--bootstrap-console',result.stdout)
            caches=list((folder/'.igor_de10_connect').iterdir())
            self.assertEqual(len(caches),1)
            for name in connect.ASSETS+['tools/connect_de10.py','src/igor_pipeline/scripts/ethernet_test.py',
                                         'src/igor_pipeline/scripts/uart_q88_vectors.json']:
                self.assertEqual((caches[0]/name).read_bytes(),(ROOT/name).read_bytes())

if __name__=='__main__':unittest.main()
