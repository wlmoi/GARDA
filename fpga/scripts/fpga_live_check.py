"""Repeat synthetic input -> real FPGA output checks and log both sides with timestamps."""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
import time

import serial
from fpga_datalogger import PassiveJtag
import verify_mock_inference as model
from usb_serial_roles import fpga_port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='auto')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--count', type=int, default=0, help='0 repeats until Ctrl+C')
    parser.add_argument('--location', default='BELUM_DIISI')
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval < .1 or args.count < 0:
        parser.error('Interval must be >=0.1 seconds and count >=0')
    root = model.ROOT
    directory = root / 'evidence/live_io' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory.mkdir(parents=True)
    connection = port = None
    done = passed = failures = consecutive_failures = uart_valid = uart_no_reply = 0
    error = None
    stopped = False
    started = time.monotonic()
    print('GARDA - LIVE INPUT / OUTPUT CHECK', flush=True)
    print(f'{args.port} input -> real FPGA -> JTAG output. Repeat timer: {args.interval}s; Ctrl+C stops.\nLog: {directory}', flush=True)
    print('Inputs are SYNTHETIC bench observations. This script does not command STM32/motors or program the board.', flush=True)
    fields = ['timestamp_utc', 'timestamp_local', 'location', 'test', 'case', 'communication', 'numeric_match',
              'uart_return', 'tx_bytes', 'seq_before', 'seq_after', 'accepted_before', 'accepted_after',
              'cycles', 'core_latency_us', 'host_transaction_ms', 'input_q88', 'expected_q88', 'output_q88',
              'error_lsb', 'stop', 'fpga_error', 'failure']
    try:
        args.port = fpga_port(args.port)
        print('Detected FPGA UART:', args.port, flush=True)
        _, q = model.load_model()
        identity = model.identity(q)
        project = root / 'experiments/jp1_1_2_monitor'
        for name in ['garda_src_policy_core.v'] + [f'bank{i}.mem' for i in range(8)]:
            if model.sha(project / name) != model.sha(model.BASE / name):
                raise RuntimeError('Observer core/bank mismatch: ' + name)
        identity.update(active_image_note='Logger queries already programmed observer; no programming is performed',
                        script_sha256=model.sha(Path(__file__)),
                        timing_scope='FPGA-reported last core cycles via JTAG; core time calculated at 50 MHz; host elapsed is separate',
                        location=args.location, port=args.port, baud=921600, interval_s=args.interval, input_source='synthetic fixed/seeded vectors',
                        output_source='actual FPGA response_valid latch, verified fresh per request')
        (directory / 'session.json').write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')
        ref = model.load_module('live_uart_reference', root.parent / 'src/garda_pipeline/scripts/uart_test.py')
        cases = model.vectors()
        connection = PassiveJtag()
        port = serial.Serial(args.port, 921600, timeout=.02, write_timeout=1, xonxoff=False, rtscts=False, dsrdtr=False)
        with (directory / 'input_output.csv').open('w', newline='', encoding='utf-8-sig') as csvfile, (directory / 'input_output.jsonl').open('w', encoding='utf-8') as jsonfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)
            writer.writeheader()
            while args.count == 0 or done < args.count:
                cycle_start = time.monotonic()
                name, obs = cases[done % len(cases)]
                now = dt.datetime.now(dt.timezone.utc)
                expected = model.oracle(obs, q)
                row = dict(timestamp_utc=now.isoformat(timespec='milliseconds'), timestamp_local=now.astimezone().isoformat(timespec='milliseconds'),
                           location=args.location, test=done + 1, case=name, communication='FAIL', numeric_match=False,
                           uart_return='NOT_CHECKED', input_q88=obs, expected_q88=expected, output_q88=None, error_lsb=None)
                raw = dict()
                print(f"\n[{row['timestamp_local']}] TEST {done + 1} | {name} | location={args.location}", flush=True)
                for offset in range(0, 74, 16):
                    print(f' INPUT_Q8.8 [{offset}:{min(offset+15,73)}] = {obs[offset:offset+16]}', flush=True)
                try:
                    before, raw['before'] = connection.snapshot()
                    if before['stop'] or before['mode'] != 'I':
                        raise RuntimeError('FPGA E-stop active or not in inference mode; input not sent')
                    packet = ref.build_sensor_packet_q88(obs)
                    port.reset_input_buffer()
                    count = port.write(packet)
                    port.flush()
                    row['tx_bytes'] = count
                    if count != len(packet):
                        raise RuntimeError('Incomplete UART write')
                    deadline = time.monotonic() + 2
                    while True:
                        after, raw['after'] = connection.snapshot()
                        if after['seq'] != before['seq'] or time.monotonic() >= deadline:
                            break
                    actual = [after[f'a{k}'] for k in range(3)]
                    fresh = after['seq'] == before['seq'] + 1 and after['accepted'] == before['accepted'] + 1
                    link_ok = fresh and not after['stop'] and after['mode'] == 'I'
                    row.update(seq_before=before['seq'], seq_after=after['seq'], accepted_before=before['accepted'], accepted_after=after['accepted'],
                               cycles=after['cycles'], core_latency_us=after['cycles'] / 50,
                               output_q88=actual if fresh else None, error_lsb=[a-b for a,b in zip(actual, expected)] if fresh else None,
                               communication='OK_UART_INPUT_JTAG_OUTPUT' if link_ok else 'FAIL', numeric_match=fresh and actual == expected,
                               stop=after['stop'], fpga_error=after['error'])
                    rx = port.read(min(port.in_waiting, 4096)) if port.in_waiting else b''
                    raw.update(tx_hex=packet.hex(' '), uart_rx_hex=rx.hex(' '))
                    row['uart_return'] = 'NO_REPLY'
                    if rx:
                        offset = rx.find(ref.RESPONSE_HEADER)
                        try:
                            reply = ref.parse_response_packet(rx[offset:offset+11]) if offset >= 0 else None
                            row['uart_return'] = 'CRC_AND_VALUE_OK' if reply and fresh and reply['q8_8_results'] == actual else 'INVALID_OR_MISMATCH'
                        except ValueError:
                            row['uart_return'] = 'INVALID_OR_MISMATCH'
                    if not link_ok:
                        row['failure'] = 'Fresh accepted result not confirmed; stale actions are not displayed as a new output'
                    elif not row['numeric_match'] or after['cycles'] != 6916:
                        row['failure'] = 'Numerical mismatch or unexpected core cycle count'
                    elif row['uart_return'] == 'INVALID_OR_MISMATCH':
                        row['failure'] = 'UART return data failed CRC/value comparison'
                except Exception as exc:
                    row['failure'] = str(exc)
                row['host_transaction_ms'] = round((time.monotonic() - cycle_start) * 1000, 3)
                ok = row['communication'] == 'OK_UART_INPUT_JTAG_OUTPUT' and row['numeric_match'] and not row.get('failure')
                done += 1
                passed += ok
                failures += not ok
                uart_valid += row['uart_return'] == 'CRC_AND_VALUE_OK'
                uart_no_reply += row['uart_return'] == 'NO_REPLY'
                consecutive_failures = 0 if ok else consecutive_failures + 1
                writer.writerow(row)
                jsonfile.write(json.dumps(dict(**row, raw=raw), ensure_ascii=False) + '\n')
                csvfile.flush()
                jsonfile.flush()
                print(f" EXPECTED = {expected}\n OUTPUT   = {row['output_q88']}\n ERROR_LSB= {row['error_lsb']}", flush=True)
                print(f" COMMUNICATION: {row['communication']} | CALCULATION: {'PASS' if ok else 'FAIL'} | UART_RETURN: {row['uart_return']}", flush=True)
                print(f" CYCLES: {row.get('cycles', 'N/A')} | CORE_US: {row.get('core_latency_us', 'N/A')} | HOST_MS: {row['host_transaction_ms']}", flush=True)
                print(f" RESULT: latched at completion; current FPGA error={row.get('fpga_error', 'N/A')} (11=expired freshness, not a current motor permit)", flush=True)
                if row.get('failure'):
                    print(' FAILURE:', row['failure'], flush=True)
                if consecutive_failures >= 3:
                    error = 'Stopped after three consecutive failures; check cables/ports/image before retrying'
                    break
                wait = max(0, args.interval - (time.monotonic() - cycle_start))
                if args.count == 0 or done < args.count:
                    print(f' Next check in {wait:.2f}s ...', flush=True)
                    time.sleep(wait)
    except KeyboardInterrupt:
        stopped = True
    except Exception as exc:
        error = str(exc)
        print('ERROR:', error, flush=True)
    finally:
        if port is not None:
            port.close()
        if connection is not None:
            connection.close(connection.h)
        summary = dict(checks=done, passed=passed, failed=failures, error=error, stopped_by_user=stopped,
                       uart_return_valid=uart_valid, uart_no_reply=uart_no_reply,
                       elapsed_s=round(time.monotonic()-started, 3), transport='UART input / JTAG output; UART return status is separate')
        (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        print('\nSUMMARY:', json.dumps(summary), '\nLOG:', directory, flush=True)
    return 1 if error or failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
