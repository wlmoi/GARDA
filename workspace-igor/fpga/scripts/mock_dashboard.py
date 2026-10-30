"""Local-only IGOR test dashboard. Fixed commands, one job, no motor commands."""
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import webbrowser

FPGA = Path(__file__).resolve().parents[1]
TOKEN = secrets.token_urlsafe(24)
LOCK = threading.Lock()
STATE = {'running': False, 'test': None, 'lines': [], 'exit_code': None, 'started': None}
TESTS = {
    'cargo': ('AI surge · cargo', 'MOCK_AI_SURGE_CARGO.bat', ['mock_ai_surge_cargo.py', '--hardware']),
    'worker': ('Worker + liquid proxy', 'MOCK_WORKER_LIQUID.bat', ['mock_worker_and_corrupt_frames.py', '--hardware']),
    'numeric': ('FPGA numerical + CRC', 'verify_mock_inference.py', ['verify_mock_inference.py']),
    'jtag': ('Program + JTAG verification', 'TEST_MOCK_INFERENCE_COM12.bat', ['verify_board_jtag.py', '--port', 'auto', '--program']),
}


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_job(key):
    directory = FPGA / 'evidence/dashboard' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory.mkdir(parents=True)
    command = [sys.executable, '-u', str(FPGA / 'scripts' / TESTS[key][2][0]), *TESTS[key][2][1:]]
    code = 1
    try:
        with (directory / 'terminal.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=FPGA.parent, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8', errors='replace',
                                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            process.stdin.close()
            timer = threading.Timer(240, process.kill)
            timer.start()
            try:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    with LOCK:
                        STATE['lines'].append(line.rstrip())
                        STATE['lines'] = STATE['lines'][-2500:]
                code = process.wait()
            finally:
                timer.cancel()
    except Exception as exc:
        with LOCK:
            STATE['lines'].append(str(exc))
    finally:
        result = dict(test=key, command=command, exit_code=code, passed=code == 0, finished=stamp())
        (directory / 'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        with LOCK:
            STATE.update(running=False, exit_code=code, evidence=str(directory.relative_to(FPGA)))


def history():
    results = []
    for group in ['mock_ai_surge_cargo', 'mock_disturbances', 'mock_inference', 'dashboard']:
        for directory in sorted((FPGA / 'evidence' / group).glob('*'), reverse=True)[:12]:
            if not directory.is_dir():
                continue
            summary = directory / 'summary.json'
            try:
                data = json.loads(summary.read_text(encoding='utf-8-sig')) if summary.exists() else {}
            except (ValueError, OSError):
                data = {}
            results.append(dict(group=group, session=directory.name, summary=data,
                                files=[str(p.relative_to(FPGA)).replace('\\', '/') for p in directory.iterdir()
                                       if p.is_file() and p.suffix in {'.json', '.jsonl', '.csv', '.log', '.md'}]))
    return sorted(results, key=lambda x: x['session'], reverse=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, value, kind='application/json', status=200):
        data = value.encode('utf-8') if isinstance(value, str) else json.dumps(value).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', kind + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            return self.send((FPGA / 'docs/mock_dashboard.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN), 'text/html')
        if parsed.path == '/api/state':
            from serial.tools import list_ports
            ports = [dict(port=p.device, description=p.description, fpga=(p.vid, p.pid) == (0x067b, 0x2303)) for p in list_ports.comports()]
            with LOCK:
                snapshot = {**STATE, 'lines': list(STATE['lines'])}
            return self.send(dict(state=snapshot, ports=ports, history=history()))
        if parsed.path == '/api/file':
            requested = parse_qs(parsed.query).get('path', [''])[0]
            path = (FPGA / requested).resolve()
            if not path.is_relative_to((FPGA / 'evidence').resolve()) or not path.is_file() or path.suffix not in {'.json', '.jsonl', '.csv', '.log', '.md'}:
                return self.send({'error': 'Unknown evidence'}, status=404)
            return self.send(path.read_text(encoding='utf-8-sig', errors='replace')[:2_000_000], 'text/plain')
        return self.send({'error': 'Not found'}, status=404)

    def do_POST(self):
        if self.headers.get('X-IGOR-Token') != TOKEN:
            return self.send({'error': 'Invalid local token'}, status=403)
        try:
            data = json.loads(self.rfile.read(min(int(self.headers.get('Content-Length', 0)), 2048)))
            key = data.get('test')
        except (ValueError, TypeError):
            return self.send({'error': 'Invalid request'}, status=400)
        if self.path != '/api/run' or key not in TESTS:
            return self.send({'error': 'Unknown test'}, status=400)
        with LOCK:
            if STATE['running']:
                return self.send({'error': 'A test already owns the UART. Wait for completion.'}, status=409)
            STATE.update(running=True, test=key, lines=[], exit_code=None, started=stamp())
        threading.Thread(target=run_job, args=(key,), daemon=True).start()
        return self.send({'started': key})


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    url = 'http://127.0.0.1:' + str(server.server_port)
    print('IGOR dashboard: ' + url, flush=True)
    print('Close this terminal to stop the dashboard. Close other serial terminals before testing.', flush=True)
    if '--no-browser' not in sys.argv:
        webbrowser.open(url)
    server.serve_forever()
