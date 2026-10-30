"""Synthetic inputs, real Parallel8 FPGA outputs, independent integer oracle.

Only writes local evidence. Never sends commands to STM or a motor controller.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import random
import shutil
import struct
import subprocess
import time
from pathlib import Path
import serial
from usb_serial_roles import fpga_port

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'experiments/parallel8'
SOF=ROOT/'bitstreams/garda_src_policy_parallel8.sof'
EXPECTED_SOF='cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def signed(word):return word-65536 if word&32768 else word

def load_model():
    source=ROOT.parent/'src/garda_navigation/garda_navigation/weights/model_weights.json'
    model=json.loads(source.read_text());q={}
    for layer in (1,2,3):
        for kind in ('w','b'):
            name=f'{kind}{layer}';value=model[name]
            flat=[x for row in value for x in row] if kind=='w' else value
            q[name]=[min(32767,max(-32768,round(float(x)*256))) for x in flat]
            supplied=source.parent/f'hardware/layer{layer}_{kind}.mem'
            assert q[name]==[signed(int(x,16)) for x in supplied.read_text().split()],f'Source export mismatch: {name}'
    return source,q

def oracle(observation,q):
    values=list(observation)
    for layer,rows in [(1,128),(2,64),(3,3)]:
        inputs=len(values);outputs=[]
        for neuron in range(rows):
            accumulator=q[f'b{layer}'][neuron]*256
            for k,value in enumerate(values):accumulator+=value*q[f'w{layer}'][neuron*inputs+k]
            assert -(1<<39)<=accumulator<(1<<39),'Accumulator overflows signed 40 bits'
            shifted=accumulator//256 # Signed arithmetic floor, including negatives.
            outputs.append(min(256,max(-256,shifted)) if layer==3 else min(32767,max(0,shifted)))
        values=outputs
    return values

def identity(q):
    assert sha(SOF)==EXPECTED_SOF,'Unexpected SOF; stopped before serial writes'
    acceptance=json.loads((BASE/'artifacts/acceptance.json').read_text())
    hashes={}
    for name in ['garda_src_policy_core.v','garda_src_policy_de10_nano.v','garda_src_policy.sdc','pin_assignment.tcl']+[f'bank{i}.mem' for i in range(8)]:
        path=BASE/name;key=str(path.relative_to(ROOT)).replace('\\','/')
        expected=acceptance['sha256'].get(key)
        assert expected and sha(path)==expected,f'Accepted source mismatch: {key}'
        hashes[key]=expected
    for lane in range(8):
        expected=[]
        for group in range(16):expected+=q['w1'][(group*8+lane)*74:(group*8+lane+1)*74]
        expected += [q['b1'][group*8+lane] for group in range(16)]
        for group in range(8):expected+=q['w2'][(group*8+lane)*128:(group*8+lane+1)*128]
        expected += [q['b2'][group*8+lane] for group in range(8)]
        expected += q['w3'][lane*64:(lane+1)*64] if lane<3 else [0]*64
        expected += [q['b3'][lane] if lane<3 else 0]
        expected += [0]*(4096-len(expected))
        actual=[signed(int(x,16)) for x in (BASE/f'bank{lane}.mem').read_text().split()]
        assert actual==expected,f'Bank{lane} layout/weights mismatch'
    return {'sof_sha256':EXPECTED_SOF,'source_sha256':hashes,'bank_words_verified':8*4096,
            'architecture':[74,128,64,3],'parallel_mac_lanes':8,'clock_hz':50000000,
            'core_cycles_from_prior_RTL_acceptance':acceptance['cycles'],
            'timing_scope':'UART response has no cycle field; this run measures host RTT, not internal core cycles.',
            'settings_scope':'Known SOF and exact accepted core/banks/top/SDC/pins checked; no claim that unrelated current GUI project settings or full release checks were rerun.'}

def vectors():
    baseline=[205]*64+[0]*10
    cases=[('zero',[0]*74),('baseline',baseline),('clear_front',[256]*64+[0]*10),
           ('all_upper',[256]*74),('signed_lower',[256]*64+[-256]*10),
           ('tail_upper',[0]*64+[256]*10),('tail_lower',[0]*64+[-256]*10),
           ('alternating_bounds',[256 if i%2 else 0 for i in range(64)]+[-256 if i%2 else 256 for i in range(10)])]
    for scale,label in [(256,'full_scale'),(1,'one_lsb')]:
        for i in range(74):
            obs=[0]*74;obs[i]=scale;cases.append((f'{label}_input_{i}_positive',obs))
        for i in range(64,74):
            obs=[0]*74;obs[i]=-scale;cases.append((f'{label}_input_{i}_negative',obs))
    rng=random.Random(0x1A0A74128)
    for i in range(64):cases.append((f'random_{i:02d}',[rng.randrange(257) for _ in range(64)]+[rng.randrange(-256,257) for _ in range(10)]))
    for i in range(16):cases.append((f'repeat_{i:02d}',list(cases[(i%4)][1])))
    assert len(cases)==256
    return cases

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='auto');parser.add_argument('--program',action='store_true')
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--rtl-sim',action='store_true',help='Run the exact Parallel8 Verilog on 256 vectors; no serial port is opened')
    args=parser.parse_args()
    source,q=load_model();design=identity(q)
    cases=vectors();predictions=[oracle(obs,q) for _,obs in cases]
    existing=load_module('independent_existing_oracle',ROOT/'verification/src_policy/run.py')
    assert all(expected==existing.golden(obs,q)[2] for (_,obs),expected in zip(cases,predictions))
    reference=load_module('uart_protocol_reference',ROOT.parent/'src/garda_pipeline/scripts/uart_test.py')
    assert oracle([205]*64+[0]*10,q)==[-46,60,34]
    if args.self_test:
        print('PASS: source JSON quantization, six hardware exports, eight bank layouts, accepted source/SOF hashes, 256-vector oracle cross-check');return 0
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory=ROOT/'evidence/mock_inference'/stamp;directory.mkdir(parents=True)
    design.update(model_json_sha256=sha(source),script_sha256=sha(Path(__file__)),port=args.port,baud=921600)
    (directory/'design_identity.json').write_text(json.dumps(design,indent=2)+'\n')
    if args.rtl_sim:
        for lane in range(8):shutil.copyfile(BASE/f'bank{lane}.mem',directory/f'bank{lane}.mem')
        (directory/'observations.hex').write_text(''.join(f'{x&65535:04x}\n' for _,obs in cases for x in obs))
        (directory/'expected.hex').write_text(''.join(f'{x&65535:04x}\n' for values in predictions for x in values))
        compile_run=subprocess.run([r'C:\iverilog\bin\iverilog.exe','-g2012','-s','tb_mock_parallel8','-o',str(directory/'rtl.vvp'),str(ROOT/'verification/tb_mock_parallel8.sv'),str(BASE/'garda_src_policy_core.v')],cwd=directory,capture_output=True,text=True)
        (directory/'rtl_compile.log').write_text(compile_run.stdout+compile_run.stderr)
        compile_run.check_returncode()
        run=subprocess.run([r'C:\iverilog\bin\vvp.exe',str(directory/'rtl.vvp')],cwd=directory,capture_output=True,text=True,timeout=180)
        (directory/'rtl_simulation.log').write_text(run.stdout+run.stderr);print(run.stdout,flush=True)
        passed=run.returncode==0 and 'PASS: 256 synthetic vectors' in run.stdout
        (directory/'summary.json').write_text(json.dumps({'passed':passed,'scope':'Verilog simulation, not physical hardware','vectors':256,'exact_output_checks':768,'core_cycles_each':6916,'clock_hz':50000000,'max_abs_error_lsb':0 if passed else None},indent=2)+'\n')
        print(f'Evidence: {directory}',flush=True);return 0 if passed else 1
    args.port=fpga_port(args.port)
    if args.program:
        result=subprocess.run([r'D:\Quartus-Program\quartus\bin64\quartus_pgm.exe','-c','1','-m','JTAG','garda_src_policy_parallel8.cdf'],cwd=ROOT/'bitstreams',capture_output=True,text=True)
        (directory/'programming.log').write_text(result.stdout+result.stderr)
        assert result.returncode==0 and 'Configuration succeeded' in result.stdout,'Programming failed'
        assert sha(SOF)==EXPECTED_SOF
        print('PASS: known Parallel8 SOF programmed on physical board',flush=True)
    records=[];rtts=[]
    def transaction(port,name,obs,expected,kind='valid'):
        record={'name':name,'kind':kind,'observation_q88':obs,'expected_q88':expected,'tx_hex':reference.build_sensor_packet_q88(obs).hex(' ')}
        try:
            response,elapsed=reference.exchange_q88(port,obs,1)
            actual=response['q8_8_results'];errors=[a-b for a,b in zip(actual,expected)]
            record.update(actual_q88=actual,error_lsb=errors,rx_hex=response['rx_hex'],rtt_us=elapsed,passed=actual==expected,crc_valid=True)
            rtts.append(elapsed)
        except (ValueError,OSError,serial.SerialException) as exc:record.update(passed=False,error=str(exc))
        records.append(record);log.write(json.dumps(record)+'\n');log.flush()
        if not record['passed']:print('FAIL:',name,record,flush=True)
    with (directory/'transactions.jsonl').open('w') as log:
        with serial.Serial(args.port,921600,timeout=.02,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False) as port:
            transaction(port,'baseline_link_preflight',[205]*64+[0]*10,[-46,60,34],'preflight')
            if not records[-1]['passed']:
                (directory/'summary.json').write_text(json.dumps({'passed':False,'status':'blocked_by_failed_baseline_link','numeric_vectors_planned':256,'numeric_vectors_completed':0,'preflight':records[-1]},indent=2)+'\n')
                print(f'STOP: baseline link failed; no numeric batch performed. Evidence: {directory}',flush=True)
                return 1
            consecutive_failures=0
            for i,((name,obs),expected) in enumerate(zip(cases,predictions)):
                transaction(port,name,obs,expected)
                consecutive_failures=0 if records[-1]['passed'] else consecutive_failures+1
                if consecutive_failures>=3:
                    (directory/'summary.json').write_text(json.dumps({'passed':False,'status':'stopped_after_three_consecutive_failures','numeric_vectors_planned':256,'numeric_vectors_completed':i+1},indent=2)+'\n')
                    print(f'STOP: three consecutive failures. Evidence: {directory}',flush=True)
                    return 1
                if i%32==31:print(f'Numeric cases: {i+1}/256; passed={sum(r["passed"] for r in records)}',flush=True)
            default=[205]*64+[0]*10;good=reference.build_sensor_packet_q88(default)
            negative=list(default);negative[0]=-1
            over=list(default);over[64]=257
            def raw_frame(obs):
                body=bytes([1,148])+struct.pack('<74h',*obs)
                return b'\x5a\xa5'+body+bytes([reference.crc8_maxim(body)])
            invalid=[('bad_crc',good[:-1]+bytes([good[-1]^1])),('negative_lidar',raw_frame(negative)),('tail_above_one',raw_frame(over)),('truncated_frame',good[:10])]
            for name,packet in invalid:
                port.reset_input_buffer();port.write(packet);port.flush()
                data=bytearray();deadline=time.monotonic()+.3
                while time.monotonic()<deadline:data.extend(port.read(min(max(port.in_waiting,1),4096)))
                record={'name':name,'kind':'invalid','tx_hex':packet.hex(' '),'rx_hex':data.hex(' '),'passed':len(data)==0,'assertion':'No response to rejected/incomplete request within 300 ms; internal fault code not observable over this response protocol.'}
                records.append(record);log.write(json.dumps(record)+'\n');log.flush()
                print(f'Rejection {name}: {"PASS" if record["passed"] else "FAIL"}',flush=True)
                transaction(port,'recovery_after_'+name,default,[-46,60,34],'recovery')
    numeric=[r for r in records if r['kind']!='invalid'];rejected=[r for r in records if r['kind']=='invalid']
    summary={'passed':all(r['passed'] for r in records),'main_numeric_vectors':256,'numeric_transactions':len(numeric),'numeric_passed':sum(r['passed'] for r in numeric),'output_words_checked':3*len(numeric),'mismatches':sum(not r['passed'] for r in numeric),'invalid_tests':len(rejected),'invalid_passed':sum(r['passed'] for r in rejected),'distinct_expected_outputs':len(set(map(tuple,predictions))),'max_abs_error_lsb':max((abs(x) for r in numeric for x in r.get('error_lsb',[])),default=None),'host_mean_rtt_us':sum(rtts)/len(rtts) if rtts else None,'host_max_rtt_us':max(rtts,default=None),'scope':'Synthetic observations applied to physical FPGA; exact quantized integer equivalence on tested cases. Not exhaustive proof, not FP32 equivalence, not motor/system validation; host RTT includes USB/UART/OS.'}
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True);print(f'Evidence: {directory}',flush=True)
    return 0 if summary['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
