#!/usr/bin/env python3
"""Validate FPGA outputs against portable integer Q8.8 oracle cases; never mock success."""
import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import sys

import serial
import uart_test as uart
from uart_validate_q88 import DEFAULT_VECTORS, load_vectors


def run(port,baud,repeat,timeout,vectors,output):
    data=load_vectors(vectors)
    total=0; passed=0
    with ExitStack() as stack:
        log=stack.enter_context(Path(output).open('x',encoding='utf-8'))
        options={'exclusive':True} if sys.platform.startswith('linux') else {}
        link=stack.enter_context(serial.Serial(port,baud,timeout=.02,write_timeout=timeout,
            bytesize=8,parity='N',stopbits=1,xonxoff=False,rtscts=False,dsrdtr=False,**options))
        for n in range(repeat):
            for case in data['cases']:
                record={'frame_id':total,'case':case['name'],'repeat':n,'format':'Q8.8',
                        'baud':baud,'model_sha256':data['model_sha256'],
                        'observation_q88':case['observation_q88'],'expected_q88':case['expected_q88']}
                total+=1
                try:
                    response,elapsed=uart.exchange_q88(link,case['observation_q88'],timeout)
                    ok=response['q8_8_results']==case['expected_q88']
                    record.update(actual_q88=response['q8_8_results'],rx_hex=response['rx_hex'],
                                  rtt_us=elapsed,passed=ok)
                    passed+=int(ok)
                    print(f'{"PASS" if ok else "MISMATCH"} {case["name"]}: '
                          f'{uart.format_q88(response["q8_8_results"])}; expected={case["expected_q88"]}')
                except (ValueError,serial.SerialException) as exc:
                    record.update(passed=False,error=str(exc))
                    print(f'FAIL {case["name"]}: {exc}')
                log.write(json.dumps(record)+'\n');log.flush()
    print(f'Q8.8 hardware: {passed}/{total} PASS; report: {output}')
    return passed==total


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='/dev/ttyTHS1')
    parser.add_argument('--baud',type=int,choices=(9600,921600),default=9600)
    parser.add_argument('--repeat',type=int,default=1)
    parser.add_argument('--timeout',type=float,default=1)
    parser.add_argument('--vectors',type=Path,default=DEFAULT_VECTORS)
    parser.add_argument('--output',type=Path,required=True,help='New JSONL path')
    args=parser.parse_args()
    if args.repeat<=0 or not math.isfinite(args.timeout) or args.timeout<=0:
        parser.error('--repeat and --timeout must be positive')
    try:
        return 0 if run(args.port,args.baud,args.repeat,args.timeout,args.vectors,args.output) else 1
    except (OSError,ValueError,serial.SerialException,KeyError,TypeError) as exc:
        print(f'FAIL: {exc}',file=sys.stderr);return 1
    except KeyboardInterrupt:
        print('Interrupted; partial capture retained',file=sys.stderr);return 130

if __name__=='__main__':raise SystemExit(main())
