#!/usr/bin/env python3
"""Satu perintah di Jetson: siapkan IP, bootstrap HPS melalui USB console,
SSH/deploy gateway, lalu validasi Ethernet. Biarkan terminal terbuka.
Default hanya menguji jaringan; --hardware menguji inferensi FPGA asli.
"""
import argparse
import getpass
import ipaddress
import json
import os
import platform
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
ASSETS=['src/igor_controller/igor_controller/ethernet_protocol.py',
        'src/igor_pipeline/hps_de10/de10_udp_gateway.py']

class ConnectionError(RuntimeError):pass

def run(command,**kwargs):
    return subprocess.run(command,check=True,**kwargs)

def choose_interface(links,requested=None):
    names=[item['ifname'] for item in links]
    if requested:
        if requested not in names:raise ConnectionError(f'Interface {requested} tidak ditemukan')
        return requested
    if 'enP8p1s0' in names:return 'enP8p1s0'
    candidates=[item['ifname'] for item in links if item.get('link_type')=='ether'
                and re.match(r'^(eth\d|en)',item['ifname'])]
    if len(candidates)!=1:raise ConnectionError(f'Pilih --interface dari {names}')
    return candidates[0]

def carrier(interface):
    try:return (Path('/sys/class/net')/interface/'carrier').read_text().strip()=='1'
    except OSError:return False

def ssh_ready(host,source_ip,timeout=1):
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as link:
            link.settimeout(timeout)
            link.bind((source_ip,0))
            link.connect((host,22))
        return True
    except OSError:return False

def discover_peer(interface,source_ip):
    """Only inspect existing IPv4 neighbors on this wired /24, never Wi-Fi or a subnet sweep."""
    result=subprocess.run(['ip','-j','neigh','show','dev',interface],capture_output=True,text=True)
    if result.returncode:return []
    try:neighbors=json.loads(result.stdout)
    except ValueError:return []
    network=ipaddress.IPv4Network(source_ip+'/24',strict=False)
    candidates=[]
    for item in neighbors:
        try:address=ipaddress.IPv4Address(item.get('dst',''))
        except ValueError:continue
        states=item.get('state',[])
        if isinstance(states,str):states=[states]
        if address not in network or str(address)==source_ip or not item.get('lladdr') or any(s in ('FAILED','INCOMPLETE') for s in states):continue
        if str(address) not in candidates:candidates.append(str(address))
    return [address for address in candidates[:8] if ssh_ready(address,source_ip)]

def choose_console(requested=None):
    if requested:return requested
    try:from serial.tools import list_ports
    except ImportError:raise ConnectionError('USB console perlu pyserial: python3 -m pip install --user pyserial')
    ports=list(list_ports.comports())
    # DE10 built-in console FT232R. Do not probe arbitrary STM32/robot ports.
    candidates=[p.device for p in ports if (p.vid,p.pid)==(0x0403,0x6001)]
    if len(candidates)!=1:
        inventory=', '.join(f'{p.device} ({p.description})' for p in ports) or '(tidak ada)'
        raise ConnectionError('Console DE10 belum unik/terpasang. Hubungkan USB-UART console, '
            f'lalu pilih --console /dev/ttyUSBx. Terdeteksi: {inventory}')
    return candidates[0]

def usb_inventory(root=Path('/sys/bus/usb/devices')):
    devices=[]
    for entry in root.glob('*'):
        try:
            vid=int((entry/'idVendor').read_text().strip(),16)
            pid=int((entry/'idProduct').read_text().strip(),16)
        except (OSError,ValueError):continue
        if vid==0x1d6b:continue # Linux root hubs are not a DE10 console.
        try:product=(entry/'product').read_text().strip()
        except OSError:product=''
        devices.append({'vid':vid,'pid':pid,'product':product})
    return devices

def ensure_console(requested=None):
    try:return choose_console(requested)
    except ConnectionError as initial:
        devices=usb_inventory()
        ftdi=[d for d in devices if (d['vid'],d['pid'])==(0x0403,0x6001)]
        inventory=', '.join(f"{d['vid']:04x}:{d['pid']:04x} {d['product']}" for d in devices[:8]) or '(tidak ada perangkat USB eksternal)'
        print(f'Inventaris USB Jetson: {inventory}',flush=True)
        if not ftdi:
            blaster=any(d['vid']==0x09fb for d in devices)
            detail=' USB-Blaster terlihat, tetapi itu hanya JTAG.' if blaster else ''
            raise ConnectionError('Chip USB console FT232R (0403:6001) belum terlihat oleh Jetson.'+detail+
                ' Hubungkan konektor USB-UART console DE10 langsung ke port USB HOST Jetson dengan kabel DATA. '
                'Kabel yang hanya masuk ke PC tidak membuat ttyUSB di Jetson. '+str(initial)) from initial
        if len(ftdi)!=1:raise ConnectionError('Beberapa FT232R terlihat; pilih --console setelah port ttyUSB muncul. '+str(initial)) from initial
        if not shutil.which('modprobe'):raise ConnectionError('FT232R terdeteksi tetapi modprobe tidak tersedia untuk memuat driver ftdi_sio') from initial
        print('FT232R terdeteksi. Memuat driver console ftdi_sio...',flush=True)
        prefix=[] if os.geteuid()==0 else ['sudo']
        try:run(prefix+['modprobe','ftdi_sio'])
        except subprocess.CalledProcessError as exc:
            raise ConnectionError('Driver ftdi_sio gagal dimuat. Periksa dukungan modul pada kernel Jetson; tidak membuat ttyUSB palsu.') from exc
        if shutil.which('udevadm'):
            try:subprocess.run(['udevadm','settle','--timeout=5'],timeout=6,check=False)
            except subprocess.TimeoutExpired:pass
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            try:return choose_console()
            except ConnectionError:time.sleep(.2)
        raise ConnectionError('FT232R terlihat dan driver sudah diminta, tetapi ttyUSB belum muncul. Periksa error USB/binding pada sudo dmesg; tidak memilih ttyTHS/ttyS bawaan Jetson.')

def is_de10(identity):
    lower=identity.lower()
    return bool(re.search(r'(?m)^armv7l\s*$',identity)) and any(
        word in lower for word in ('de10','socfpga','cyclone')) and 'tegra' not in lower

def is_jetson():
    try:compatible=Path('/proc/device-tree/compatible').read_bytes().lower()
    except OSError:compatible=b''
    return b'nvidia,tegra' in compatible or 'tegra' in platform.release().lower()

class Console:
    def __init__(self,device,user):
        import serial
        self.user=user
        self.serial=serial.Serial(device,115200,timeout=.1,write_timeout=2,exclusive=True,
                                  xonxoff=False,rtscts=False,dsrdtr=False)
    def write(self,value):self.serial.write(value.encode()+b'\r')
    def read(self):
        text=self.serial.read(max(1,min(self.serial.in_waiting,4096))).decode(errors='replace')
        return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text).replace('\r','')
    def login(self):
        print('Membuka console HPS 115200. Tunggu Linux boot; credential tidak disimpan.',flush=True)
        self.write('');text='';attempts=0;deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            text+=self.read()
            if re.search(r'(?im)(?:^|\n)[^\n]*login:\s*$',text):
                attempts+=1
                if attempts>2:raise ConnectionError('Login HPS gagal; periksa --user dan password HPS')
                self.write(self.user);text=''
            elif re.search(r'(?im)password:\s*$',text):
                self.write(getpass.getpass(f'Password Linux HPS ({self.user}): '));text=''
            elif re.search(r'(?m)(?:^|\n)[^\n]*[#$]\s*$',text):return
        raise ConnectionError('Tidak ada shell Linux HPS. Periksa microSD/boot DE10, kabel console, dan port yang dipilih.')
    def command(self,command,timeout=15,privileged=False):
        marker='IGOR_'+uuid.uuid4().hex
        if privileged:
            command=f'if [ "$(id -u)" = 0 ]; then sh -c {shlex.quote(command)}; else sudo -p {shlex.quote(marker+": ")} sh -c {shlex.quote(command)}; fi'
        wrapped=f"printf '\\n{marker}_START\\n'; ( {command} ); igor_rc=$?; printf '\\n{marker}_END:%s\\n' \"$igor_rc\""
        self.write(wrapped);text='';deadline=time.monotonic()+timeout;prompts=0;seen=0
        while time.monotonic()<deadline:
            text+=self.read()
            start=re.search(r'(?m)^'+marker+r'_START\s*\n',text)
            if not start:continue
            output=text[start.end():]
            end=re.search(r'(?m)^'+marker+r'_END:(\d+)\s*$',output)
            if end:
                if int(end[1]):raise ConnectionError(f'Perintah HPS gagal (exit {end[1]}): {command}\n{output[:end.start()]}')
                return output[:end.start()].strip()
            count=output.count(marker+': ')
            if count>seen:
                seen=count;prompts+=1
                if prompts>2:raise ConnectionError('sudo HPS gagal')
                self.write(getpass.getpass('Password sudo HPS: '))
        raise ConnectionError('Timeout console HPS saat menjalankan konfigurasi')
    def close(self):self.serial.close()

def configure_hps(console,args):
    identity=console.command("uname -m; uname -r; cat /proc/device-tree/compatible 2>/dev/null | tr '\\000' ' '; printf '\\n'")
    if not is_de10(identity):raise ConnectionError(f'Console bukan HPS DE10 yang dikenali; tidak mengubah IP. Identitas: {identity}')
    print('Identitas HPS ARMv7/socfpga terverifikasi.',flush=True)
    if args.hps_interface:
        interface=args.hps_interface
    else:
        names=console.command("for p in /sys/class/net/*; do [ -d \"$p/device\" ] && [ ! -d \"$p/wireless\" ] && basename \"$p\"; done; true").split()
        if 'eth0' in names:interface='eth0'
        elif len(names)==1:interface=names[0]
        else:raise ConnectionError(f'Pilih --hps-interface; kandidat HPS: {names}')
    q=shlex.quote(interface)
    console.command(f'ip link set dev {q} up && ip address replace {args.hps_ip}/24 dev {q}',privileged=True)
    console.command('if command -v systemctl >/dev/null; then systemctl start ssh.service || systemctl start sshd.service || systemctl start dropbear.service; '
                    'elif command -v service >/dev/null; then service ssh start || service sshd start || service dropbear start; '
                    'else printf "Tidak ada service manager SSH\\n"; exit 1; fi',timeout=30,privileged=True)
    print(f'IP HPS {args.hps_ip}/24 aktif; layanan SSH diminta berjalan.',flush=True)

def remote_serial_command(serial_path):
    if serial_path:return shlex.quote(serial_path)
    # Executed on HPS, not on Jetson. Ambiguous adapter selection fails closed.
    code="from serial.tools import list_ports; p=[x.device for x in list_ports.comports() if x.vid is not None]; assert len(p)==1, 'Pilih --fpga-serial; adapter HPS tidak unik: '+repr(p); print(p[0])"
    return '"$(python3 -c '+shlex.quote(code)+')"'

def remote_directory(path):
    if path=='~':return '"$HOME"'
    if path.startswith('~/'):return '"$HOME"/'+shlex.quote(path[2:])
    return shlex.quote(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface',help='Default: enP8p1s0 jika tersedia, atau satu interface Ethernet')
    parser.add_argument('--console',help='USB-UART console DE10 di Jetson; baud console selalu 115200')
    parser.add_argument('--hps-interface',help='Default: eth0 jika tersedia pada HPS')
    parser.add_argument('--user',default='fpga',help='Akun Linux HPS yang benar; bukan akun Jetson')
    parser.add_argument('--jetson-ip',default='192.168.50.1')
    parser.add_argument('--hps-ip',default='192.168.50.2')
    parser.add_argument('--remote-dir',default='igor_ws',help='Folder repo relatif HOME akun HPS, atau path absolut')
    parser.add_argument('--hardware',action='store_true',help='Validasi FPGA asli; default NETWORK ONLY')
    parser.add_argument('--fpga-serial',help='Adapter USB-UART LOKAL HPS; berbeda dari --console di Jetson')
    parser.add_argument('--baud',type=int,choices=(9600,921600),default=9600)
    parser.add_argument('--iter',type=int,default=10)
    parser.add_argument('--bootstrap-console',action='store_true',help='Konfigurasi HPS lewat console meskipun carrier sudah aktif')
    parser.add_argument('--check-only',action='store_true',help='Hanya inventaris Jetson; tidak mengubah IP atau membuka console')
    args=parser.parse_args()
    if not sys.platform.startswith('linux'):parser.error('Jalankan script ini pada Linux Jetson')
    try:
        for value in (args.jetson_ip,args.hps_ip):ipaddress.IPv4Address(value)
        if args.jetson_ip==args.hps_ip or ipaddress.IPv4Network(args.jetson_ip+'/24',strict=False)!=ipaddress.IPv4Network(args.hps_ip+'/24',strict=False):
            raise ValueError('Pilih dua alamat berbeda pada subnet /24 yang sama')
        if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_-]*',args.user):raise ValueError('Nama user HPS tidak valid')
        for name in (args.interface,args.hps_interface):
            if name and not re.fullmatch(r'[a-zA-Z0-9_.:-]+',name):raise ValueError('Nama interface tidak valid')
        if not args.remote_dir or '\n' in args.remote_dir or '\x00' in args.remote_dir:raise ValueError('Folder HPS tidak valid')
        if args.iter<=0:raise ValueError('--iter harus positif')
        if not shutil.which('ip'):raise ConnectionError('iproute2 belum tersedia')
        links=json.loads(run(['ip','-j','link'],capture_output=True,text=True).stdout)
        interface=choose_interface(links,args.interface)
        print(f'Jetson Ethernet: {interface}; carrier={int(carrier(interface))}',flush=True)
        if args.check_only:
            print(run(['ip','-br','address','show',interface],capture_output=True,text=True).stdout)
            print('CHECK ONLY: tidak ada perubahan konfigurasi.')
            return 0
        if not is_jetson():raise ConnectionError('Jalankan konfigurasi ini di Jetson, bukan HPS DE10/PC. --check-only tetap dapat dipakai untuk inventaris.')
        for name in ASSETS+['src/igor_pipeline/scripts/ethernet_test.py','src/igor_pipeline/scripts/uart_q88_vectors.json']:
            if not (ROOT/name).is_file():raise ConnectionError(f'File belum tersedia: {ROOT/name}; pasang paket Ethernet terbaru')
        if not shutil.which('ssh'):raise ConnectionError('Install OpenSSH client pada Jetson')
        info=json.loads(run(['ip','-j','address','show','dev',interface],capture_output=True,text=True).stdout)[0]
        has_ip=any(x.get('local')==args.jetson_ip and x.get('prefixlen')==24 for x in info.get('addr_info',[]))
        if 'UP' not in info.get('flags',[]) or not has_ip:
            prefix=[] if os.geteuid()==0 else ['sudo']
            run(prefix+['ip','link','set','dev',interface,'up'])
            run(prefix+['ip','address','replace',args.jetson_ip+'/24','dev',interface])
        # Bootstrap only when needed or explicitly requested. Never send shell
        # commands to the GPIO inference UART or an unidentified Jetson shell.
        reachable=False
        if carrier(interface):
            reachable=ssh_ready(args.hps_ip,args.jetson_ip,2)
            if not reachable and not args.bootstrap_console:
                print(f'Link Ethernet aktif, tetapi SSH {args.hps_ip}:22 belum dapat diakses. Memeriksa neighbor kabel, bukan Wi-Fi...',flush=True)
                peers=discover_peer(interface,args.jetson_ip)
                if len(peers)==1:
                    args.hps_ip=peers[0];reachable=True
                    print(f'Kandidat SSH kabel: {args.hps_ip}; identitas HPS akan diverifikasi setelah login.',flush=True)
                elif peers:
                    raise ConnectionError(f'Beberapa kandidat SSH kabel: {peers}. Pilih --hps-ip dan --jetson-ip yang sesuai; tidak memilih perangkat secara acak.')
        if args.bootstrap_console or not reachable:
            try:device=ensure_console(args.console)
            except ConnectionError as exc:
                if carrier(interface):
                    raise ConnectionError(f'Ethernet SUDAH link (carrier=1), tetapi SSH HPS belum terjangkau dan IP HPS belum dapat diverifikasi. '
                        f'Penyebab dapat berupa IP berbeda, SSH belum aktif, atau Linux belum boot. {exc}. '
                        'Hubungkan port USB-UART CONSOLE DE10 ke Jetson (bukan USB-Blaster), lalu periksa lsusb dan sudo dmesg -w saat mencolok kabel. '
                        'Carrier=1 tidak berarti Linux/SSH sudah siap.') from exc
                raise
            print(f'Console yang dipilih: {device}',flush=True)
            console=Console(device,args.user)
            try:console.login();configure_hps(console,args)
            finally:console.close()
        deadline=time.monotonic()+10
        while not carrier(interface) and time.monotonic()<deadline:time.sleep(.2)
        if not carrier(interface):raise ConnectionError('Carrier masih 0: periksa kabel RJ45, LED link, dan boot/driver Ethernet HPS. IP tidak dapat memperbaiki link fisik.')
        ping=subprocess.run(['ping','-I',interface,'-c','2','-W','2',args.hps_ip])
        if ping.returncode:print('Ping belum berhasil; melanjutkan verifikasi SSH/UDP karena ICMP bisa diblokir.',flush=True)
        target=f'{args.user}@{args.hps_ip}'
        with tempfile.TemporaryDirectory(prefix='igor-ssh-') as tmp:
            control=str(Path(tmp)/'control')
            base=['ssh','-b',args.jetson_ip,'-S',control,'-o','ConnectTimeout=5','-o','ConnectionAttempts=1','-o','StrictHostKeyChecking=ask']
            gateway=None
            logfile=ROOT/('igor_connect_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.log')
            stream=None
            try:
                print('Login SSH HPS. Periksa fingerprint host; password diminta oleh SSH, tidak disimpan script.',flush=True)
                run(base+['-M','-o','ControlPersist=60','-fN',target])
                identity=run(base+[target,"uname -m; uname -r; cat /proc/device-tree/compatible 2>/dev/null | tr '\\000' ' '; printf '\\n'"],capture_output=True,text=True).stdout
                if not is_de10(identity):raise ConnectionError('SSH tidak menunjuk HPS DE10 ARMv7; deployment dibatalkan')
                code="import sys; assert sys.version_info >= (3,8), 'HPS memerlukan Python 3.8+'; print(sys.version)"
                run(base+[target,'python3 -c '+shlex.quote(code)])
                archive=Path(tmp)/'gateway.tar'
                with tarfile.open(archive,'w') as tar:
                    for name in ASSETS:tar.add(ROOT/name,arcname=name,recursive=False)
                directory=remote_directory(args.remote_dir)
                with archive.open('rb') as payload:
                    run(base+[target,f'mkdir -p -- {directory} && tar -xf - -C {directory}'],stdin=payload)
                extra=f'--backend uart --baud {args.baud} --timeout 0.5 --serial {remote_serial_command(args.fpga_serial)}' if args.hardware else '--backend mock'
                command=f'cd {directory} && exec python3 -u src/igor_pipeline/hps_de10/de10_udp_gateway.py --bind {args.hps_ip} --port 8080 --allow-client {args.jetson_ip} {extra}'
                stream=logfile.open('x',encoding='utf-8')
                gateway=subprocess.Popen(base+['-tt',target,command],stdout=stream,stderr=subprocess.STDOUT)
                print(f'Menjalankan gateway HPS; log: {logfile}',flush=True)
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    if gateway.poll() is not None:raise ConnectionError(f'Gateway berhenti. Periksa {logfile}; mungkin port 8080 sudah dipakai atau pyserial/adapter belum siap')
                    if 'RX=492 TX=50' in logfile.read_text(errors='replace'):break
                    time.sleep(.1)
                else:raise ConnectionError(f'Gateway belum siap; periksa {logfile}')
                test=[sys.executable,str(ROOT/'src/igor_pipeline/scripts/ethernet_test.py'),
                      '--host',args.hps_ip,'--iter',str(args.iter),'--timeout','1']
                if not args.hardware:test.append('--network-only')
                run(test)
                print('TERHUBUNG: '+('FPGA Q8.8 tervalidasi.' if args.hardware else 'NETWORK ONLY; belum membuktikan inferensi FPGA.'),flush=True)
                print('Biarkan terminal terbuka. Ctrl+C menghentikan gateway sesi ini. IP sementara tetap terpasang.',flush=True)
                while gateway.poll() is None:time.sleep(.5)
                raise ConnectionError(f'Gateway sesi berakhir; lihat {logfile}')
            finally:
                if gateway and gateway.poll() is None:
                    gateway.terminate()
                    try:gateway.wait(timeout=5)
                    except subprocess.TimeoutExpired:gateway.kill();gateway.wait()
                subprocess.run(base+['-O','exit',target],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if stream:stream.close()
    except KeyboardInterrupt:
        print('\nSesi dihentikan.');return 130
    except (ConnectionError,OSError,ValueError,ImportError,subprocess.CalledProcessError) as exc:
        print(f'BELUM TERHUBUNG: {exc}',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
