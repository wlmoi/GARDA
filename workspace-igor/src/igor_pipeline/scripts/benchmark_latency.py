#!/usr/bin/env python3
"""Validated Protocol V2 benchmark. Positional host/port remain compatible."""
import argparse
from ethernet_test import run

def run_benchmark(target_host='127.0.0.1',target_port=8080,num_packets=50):
    return run(target_host,target_port,num_packets)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('host',nargs='?',default='127.0.0.1')
    p.add_argument('port',nargs='?',type=int,default=8080)
    p.add_argument('--iter',type=int,default=50)
    a=p.parse_args()
    if a.iter<=0 or not 1<=a.port<=65535:p.error('Invalid packet count or port')
    raise SystemExit(0 if run_benchmark(a.host,a.port,a.iter) else 1)
