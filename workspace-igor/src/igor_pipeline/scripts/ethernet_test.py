#!/usr/bin/env python3
"""Verify Jetson-HPS UDP identity, CRC32 and exact Q8.8 outputs; mock is test-only."""
import argparse
from contextlib import nullcontext
import json
import math
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'igor_controller/igor_controller'))
from ethernet_protocol import UDPLink,ProtocolError,parse_response,STATUS_TEST_ONLY

VECTORS=Path(__file__).with_name('uart_q88_vectors.json')

def load_cases(path):
    data=json.loads(Path(path).read_text())
    if data.get('format')!='Q8.8' or not data.get('cases'):raise ValueError('Invalid Q8.8 oracle')
    return data

def check_log(path,vectors):
    data=load_cases(vectors);oracle={c['name']:c for c in data['cases']}
    count=0;seen=set();requested=None
    with Path(path).open() as stream:
        for line in stream:
            count+=1
            record=json.loads(line);response=parse_response(bytes.fromhex(record['rx_udp_hex']))
            if requested is None:requested=record['requested']
            if record['requested']!=requested or record['transaction_index']!=count-1:
                raise ProtocolError('Capture transaction order/count metadata mismatch')
            if record.get('passed') is not True or response['status_code']!=0:raise ProtocolError('Failed/non-hardware capture')
            key=(response['frame_id'],response['timestamp_ns'])
            if key in seen:raise ProtocolError('Duplicate response')
            seen.add(key)
            case=oracle[record['case']]
            if record['model_sha256']!=data['model_sha256'] or record['expected_q88']!=case['expected_q88']:
                raise ProtocolError('Capture model/expected metadata differs from oracle')
            if record['observation_q88']!=case['observation_q88'] or response['q8_8_results']!=case['expected_q88']:
                raise ProtocolError('Captured output differs from model oracle')
            if response['frame_id']!=record['frame_id'] or response['timestamp_ns']!=record['timestamp_ns']:
                raise ProtocolError('Captured transaction identity differs')
    if not count or count!=requested:raise ProtocolError('Empty or incomplete capture')
    print(f'PASS log: {count} CRC-valid hardware-status Q8.8 results')
    return True

def run(host,port=8080,iterations=50,timeout=1.,vectors=VECTORS,all_cases=False,network_only=False,output=None):
    data=load_cases(vectors);cases=data['cases'] if all_cases else data['cases'][:1]
    link=UDPLink(f'udp://{host}:{port}',timeout)
    latencies=[];passed=0;attempted=0
    try:
        with (Path(output).open('x',encoding='utf-8') if output else nullcontext(None)) as log:
            for n in range(iterations):
                case=cases[n%len(cases)];attempted+=1;start=time.perf_counter()
                record={'case':case['name'],'observation_q88':case['observation_q88'],
                        'requested':iterations,'transaction_index':n,
                        'model_sha256':data['model_sha256'],'expected_q88':case['expected_q88'],
                        'network_only':network_only}
                try:
                    actual=link.infer_q88(case['observation_q88'],allow_test=network_only)
                    response=link.last_response
                    ok=(response['status_code']==STATUS_TEST_ONLY if network_only else actual==case['expected_q88'])
                    elapsed=(time.perf_counter()-start)*1000
                    record.update(response,passed=ok,rx_udp_hex=link.last_raw_response.hex(' '),rtt_ms=elapsed)
                    if network_only:
                        print(f'NETWORK_ONLY {"PASS" if ok else "FAIL"} status={response["status_code"]}; '
                              f'no FPGA inference; RTT={elapsed:.3f} ms')
                    else:
                        print(f'FPGA {"PASS" if ok else "FAIL"} {case["name"]}: '
                              f'Q8.8={actual} expected={case["expected_q88"]} RTT={elapsed:.3f} ms')
                    passed+=int(ok);latencies.append(elapsed)
                except (OSError,ProtocolError) as exc:
                    record.update(passed=False,error=str(exc))
                    print(f'FAIL: {exc}')
                    ok=False
                if log:log.write(json.dumps(record)+'\n');log.flush()
                if not ok:break
    finally:link.close()
    print(f'Requested={iterations} Attempted={attempted} Passed={passed}; mode={"NETWORK TEST ONLY" if network_only else "FPGA VALIDATION"}')
    if latencies:print(f'Mean RTT={statistics.mean(latencies):.3f} ms; max={max(latencies):.3f} ms')
    return passed==iterations

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='192.168.50.2')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--iter',type=int,default=50)
    parser.add_argument('--timeout',type=float,default=1.)
    parser.add_argument('--vectors',type=Path,default=VECTORS)
    parser.add_argument('--all-cases',action='store_true')
    parser.add_argument('--network-only',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--check-log',type=Path)
    args=parser.parse_args()
    if args.iter<=0 or not 1<=args.port<=65535 or not math.isfinite(args.timeout) or args.timeout<=0:parser.error('Invalid count, port, or timeout')
    try:
        if args.check_log:return 0 if check_log(args.check_log,args.vectors) else 1
        return 0 if run(args.host,args.port,args.iter,args.timeout,args.vectors,args.all_cases,args.network_only,args.output) else 1
    except (OSError,ValueError,ProtocolError,KeyError,TypeError) as exc:
        print(f'FAIL: {exc}',file=sys.stderr);return 1
    except KeyboardInterrupt:return 130

if __name__=='__main__':raise SystemExit(main())
