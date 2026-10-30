"""Send synthetic observations through COM12; read fresh physical FPGA results over JTAG."""
import ctypes as C
import datetime,json,re,time,subprocess,argparse,shutil
from pathlib import Path
import serial
import verify_mock_inference as model
from usb_serial_roles import fpga_port
ROOT=model.ROOT
class Jtag:
 def __init__(self):
  self.lib=C.CDLL(r'D:\Quartus-Program\quartus\bin64\jtag_atlantic.dll')
  def bind(name,result,args):
   f=getattr(self.lib,name);f.restype=result;f.argtypes=args;return f
  self.open=bind('?jtagatlantic_open@@YAPEAUJTAGATLANTIC@@PEBDHH0@Z',C.c_void_p,[C.c_char_p,C.c_int,C.c_int,C.c_char_p])
  self.close=bind('?jtagatlantic_close@@YAXPEAUJTAGATLANTIC@@@Z',None,[C.c_void_p])
  self.read=bind('?jtagatlantic_read@@YAHPEAUJTAGATLANTIC@@PEADI@Z',C.c_int,[C.c_void_p,C.c_void_p,C.c_uint])
  self.write=bind('?jtagatlantic_write@@YAHPEAUJTAGATLANTIC@@PEBDI@Z',C.c_int,[C.c_void_p,C.c_char_p,C.c_uint])
  self.flush=bind('?jtagatlantic_flush@@YAHPEAUJTAGATLANTIC@@@Z',C.c_int,[C.c_void_p])
  self.h=self.open(b'DE-SoC [USB-1]',2,0,b'IGOR numeric validation')
  if not self.h:raise RuntimeError('Close other JTAG terminals; board monitor unavailable')
 def query(self,command=b'q'):
  assert self.write(self.h,command,1)==1;self.flush(self.h)
  data=bytearray();buffer=C.create_string_buffer(4096);deadline=time.monotonic()+3
  while time.monotonic()<deadline:
   n=self.read(self.h,buffer,len(buffer))
   if n<0:raise RuntimeError('JTAG disconnected')
   data.extend(buffer.raw[:n])
   if b'\r\n> ' in data:break
   time.sleep(.005)
  text=data.decode('ascii',errors='replace')
  if 'JP1 pins 1/2' not in text:raise RuntimeError('Wrong monitor image or incomplete JTAG report: '+text)
  values={k:int(v,16) for k,v in re.findall(r'\b(accepted|rejected|error|cycles|seq|a0|a1|a2)=([0-9A-F]+)',text)}
  if len(values)!=8 or 'mode=I stop=0' not in text:raise RuntimeError('Monitor not in safe inference test mode: '+text)
  values['raw']=text;return values

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',default='auto');parser.add_argument('--program',action='store_true');args=parser.parse_args()
 args.port=fpga_port(args.port)
 _,q=model.load_model();identity=model.identity(q)
 project=ROOT/'experiments/jp1_1_2_monitor'
 assert model.sha(project/'igor_src_policy_core.v')==model.sha(model.BASE/'igor_src_policy_core.v')
 for lane in range(8):assert model.sha(project/f'bank{lane}.mem')==model.sha(model.BASE/f'bank{lane}.mem')
 if args.program:
  subprocess.run([shutil.which('pwsh') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/program_uart_monitor.ps1'),'-Header','JP1_1_2'],check=True)
 image=ROOT/'bitstreams/igor_parallel8_jp1_1_2_monitor.sof'
 receipts=sorted((ROOT/'evidence/jp1_1_2_monitor').glob('*/image_receipt.json'))
 receipt=json.loads(receipts[-1].read_text(encoding='utf-8-sig'))
 assert model.sha(image)==receipt['sha256'],'Monitor image receipt mismatch'
 out=ROOT/'evidence/mock_board_jtag'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');out.mkdir(parents=True)
 identity.update(active_observer_sof_sha256=model.sha(image),active_receipt=receipt,transport='COM12 input, JTAG output; UART return path not validated')
 (out/'identity.json').write_text(json.dumps(identity,indent=2))
 ref=model.load_module('uart_reference',ROOT.parent/'src/igor_pipeline/scripts/uart_test.py')
 j=Jtag();records=[]
 try:
  before=j.query(b'i')
  with serial.Serial(args.port,921600,timeout=.02,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False) as port,(out/'transactions.jsonl').open('w') as log:
   for i,(name,obs) in enumerate(model.vectors()):
    expected=model.oracle(obs,q);port.write(ref.build_sensor_packet_q88(obs));port.flush();deadline=time.monotonic()+2
    while True:
     after=j.query()
     if after['seq']!=before['seq'] or time.monotonic()>deadline:break
    actual=[after[f'a{k}'] if after[f'a{k}']<32768 else after[f'a{k}']-65536 for k in range(3)]
    passed=(after['seq']==((before['seq']+1)&0xffffffff) and after['accepted']==before['accepted']+1 and after['cycles']==6916 and actual==expected)
    r=dict(name=name,observation_q88=obs,expected_q88=expected,actual_q88=actual,before=before,after=after,passed=passed);records.append(r);log.write(json.dumps(r)+'\n');log.flush()
    if not passed:raise RuntimeError('Fresh numerical comparison failed: '+json.dumps(r))
    before=after
    if i%32==31:print(f'Physical FPGA: {i+1}/256 vectors PASS',flush=True)
 finally:
  j.close(j.h)
  passed=len(records)==256 and all(r['passed'] for r in records)
  summary=dict(passed=passed,vectors_completed=len(records),output_words_checked=3*len(records),max_abs_error_lsb=max((abs(a-b) for r in records for a,b in zip(r['actual_q88'],r['expected_q88'])),default=None),cycles_each=6916,core_latency_us=138.32,scope='Real board: observations via COM12, results via JTAG latch with fresh sequence; not a UART return-link test')
  (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2));print('Evidence:',out,flush=True)
 return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())

