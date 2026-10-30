"""Check GARDA's public page, executable assets and catalog without credentials."""
from __future__ import annotations
import argparse
import json
import time
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def fetch(base: str, path: str) -> bytes:
    error = None
    for attempt in range(3):
        try:
            request = Request(urljoin(base.rstrip('/') + '/', path), headers={
                'User-Agent': 'GARDA-website-health/1.0', 'Cache-Control': 'no-cache'})
            with urlopen(request, timeout=25) as response:
                if response.status != 200:
                    raise RuntimeError(f'{path}: HTTP {response.status}')
                return response.read()
        except Exception as caught:
            error = caught
            if attempt < 2:
                time.sleep(2)
    raise RuntimeError(f'{path}: {error}')


def check(base: str) -> dict:
    page = fetch(base, '').decode('utf-8')
    for marker in ('GARDA', 'id="scene"', 'id="clock-explorer"', 'clock-explorer.js'):
        if marker not in page:
            raise RuntimeError(f'Page missing {marker}; login/error page or incomplete deployment')
    assets = {
        'app.js': b'rtl-catalog.json', 'scene.js': b'GardaScene',
        'clock-explorer.js': b'6916', 'gate-model.js': b'evaluateGate',
        'style.css': b'@font-face',
    }
    for path, marker in assets.items():
        if marker not in fetch(base, path):
            raise RuntimeError(f'{path}: unexpected response or asset missing')
    catalog = json.loads(fetch(base, 'data/rtl-catalog.json'))
    if len(catalog.get('modules', [])) != 20 or len(catalog.get('asic_modules', [])) != 4:
        raise RuntimeError('Catalog missing expected FPGA/ASIC modules')
    report = json.loads(fetch(base, 'data/tinytapeout-report.json'))
    if not isinstance(report.get('checks'), list):
        raise RuntimeError('Evidence status unavailable')
    return {'status': 'PASS', 'url': base, 'static_assets': len(assets),
            'fpga_modules': 20, 'asic_modules': 4,
            'scope': 'HTTP assets and catalog availability; physical chip signoff is separate'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='https://garda-chip-explorer.vercel.app')
    args = parser.parse_args()
    print(json.dumps(check(args.base_url), indent=2))
