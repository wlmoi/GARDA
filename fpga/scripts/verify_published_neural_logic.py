"""Verify Pages serves the exact neural logic layout built by this workflow run."""
from pathlib import Path
import argparse
import hashlib
import json
import time
import urllib.request
from check_neural_logic_layout import inspect_layout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    expected_hash = hashlib.sha256(args.expected.read_bytes()).hexdigest()
    downloaded = args.report.parent / 'published-neural-logic.oas'
    downloaded.parent.mkdir(parents=True, exist_ok=True)
    error = None
    for attempt in range(6):
        try:
            request = urllib.request.Request(args.url + '?sha256=' + expected_hash,
                                             headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected_hash:
                raise ValueError('Published OASIS differs from this run\'s submission')
            downloaded.write_bytes(data)
            report = inspect_layout(downloaded)
            report.update(status='PASS', url=args.url, sha256=expected_hash)
            args.report.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
            return
        except Exception as exc:
            error = exc
            if attempt < 5:
                time.sleep(10)
    raise RuntimeError(f'Published neural logic verification failed: {error}')


if __name__ == '__main__':
    main()
