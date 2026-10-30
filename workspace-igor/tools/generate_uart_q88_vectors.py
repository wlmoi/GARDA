"""Generate portable integer-only UART test cases from the accepted model."""
import importlib.util
import hashlib
import json
from pathlib import Path
import random
import struct

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'src/igor_pipeline/scripts'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def main():
    uart=load('uart',SCRIPTS/'uart_test.py')
    reference=load('reference',ROOT/'fpga/verification/src_policy/run.py')
    model_path=ROOT/'src/igor_navigation/igor_navigation/weights/model_weights.json'
    model=json.loads(model_path.read_text())
    q={k:[min(32767,max(-32768,round(float(v)*256))) for v in reference.flatten(model[k])]
       for k in ('w1','b1','w2','b2','w3','b3')}
    cases=[('default_205', [205]*64+[0]*10),('zeros',[0]*74),
           ('lidar_max',[256]*64+[0]*10),('tail_min',[128]*64+[-256]*10),
           ('tail_max',[128]*64+[256]*10),
           ('alternating',[0,256]*32+[-256,256]*5),
           ('ramp',[i*256//63 for i in range(64)]+list(range(-5,5)))]
    rng=random.Random(9600)
    for n in range(9):
        cases.append((f'random_{n:02d}',[rng.randint(0,256) for _ in range(64)]+
                      [rng.randint(-256,256) for _ in range(10)]))
    data={'schema':1,'format':'Q8.8','fractional_bits':8,'input_count':74,
          'output_count':3,'model_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),
          'scope':'Independent integer model oracle; not a physical hardware result','cases':[]}
    for name,obs in cases:
        _,_,expected,_=reference.golden(obs,q)
        body=bytes.fromhex('02 06')+struct.pack('<3h',*expected)
        response=bytes.fromhex('5a a5')+body+bytes([uart.crc8_maxim(body)])
        data['cases'].append({'name':name,'observation_q88':obs,'expected_q88':expected,
                              'tx_hex':uart.build_sensor_packet_q88(obs).hex(' '),
                              'rx_hex':response.hex(' ')})
    path=SCRIPTS/'uart_q88_vectors.json'
    path.write_text(json.dumps(data,indent=2)+'\n')
    print(f'Generated {len(cases)} integer-only Q8.8 cases: {path}')

if __name__=='__main__':main()
