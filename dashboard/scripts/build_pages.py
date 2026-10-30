"""Build one Pages site and attach only a source-matched, successful physical run.

Standard library only. A local build needs no network or credentials.
"""
from pathlib import Path
import argparse
import hashlib
import html
import io
import json
import os
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = 'garda-physical-viewer'


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward an Actions API credential to the signed blob host."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            redirected.remove_header('Authorization')
        return redirected


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(root=ROOT):
    paths = [root / 'info.yaml'] + sorted((root / 'src').rglob('*'))
    return {p.relative_to(root).as_posix(): hashlib.sha256(
        p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        for p in paths if p.is_file()}


def package(args):
    args.output.mkdir(parents=True, exist_ok=True)
    for suffix in ('oas', 'gds'):
        source = args.submission / ('tt_um_wlmoi_garda_neural_logic.' + suffix)
        if not source.is_file():
            raise ValueError('Missing actual neural logic submission: ' + str(source))
        shutil.copy2(source, args.output / ('tinytapeout.' + suffix))
    pdk = json.loads((args.submission / 'pdk.json').read_text())['PDK']
    for source in sorted(args.render.rglob('*.png')):
        shutil.copy2(source, args.output / source.name)
    manifest = {
        'schema_version': 1, 'kind': ARTIFACT, 'top_module': 'tt_um_wlmoi_garda_neural_logic',
        'pdk': pdk, 'run_id': str(args.run_id), 'commit': args.commit,
        'checks': {'gds': 'success', 'precheck': 'success', 'gl_test': 'success'},
        'source_sha256': source_hashes(),
        'files': {p.name: digest(p) for p in sorted(args.output.iterdir())
                  if p.is_file() and p.name != 'manifest.json'},
    }
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Packaged source-matched physical viewer artifact')


def api(path, binary=False):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ValueError('No Actions API token provided')
    url = 'https://api.github.com/' + path
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json', 'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'garda-pages-builder'})
    with urllib.request.build_opener(SafeRedirect()).open(req, timeout=45) as response:
        data = response.read()
    return data if binary else json.loads(data)


def matching_artifact(folder):
    path = folder / 'manifest.json'
    if not path.is_file():
        raise ValueError('Physical artifact has no manifest')
    manifest = json.loads(path.read_text())
    if manifest.get('kind') != ARTIFACT or manifest.get('schema_version') != 1:
        raise ValueError('Unknown physical artifact format')
    if manifest.get('top_module') != 'tt_um_wlmoi_garda_neural_logic':
        raise ValueError('Physical artifact targets a different top module')
    if manifest.get('source_sha256') != source_hashes():
        raise ValueError('Physical artifact belongs to different RTL/configuration')
    if manifest.get('checks') != {'gds': 'success', 'precheck': 'success', 'gl_test': 'success'}:
        raise ValueError('Physical run has not passed every required check')
    files = manifest.get('files', {})
    if not all(name in files for name in ('tinytapeout.oas', 'tinytapeout.gds')):
        raise ValueError('Physical artifact is missing actual layout files')
    for name, expected in files.items():
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('Unsafe physical artifact path')
        if not (folder / name).is_file() or digest(folder / name) != expected:
            raise ValueError('Physical artifact checksum mismatch: ' + name)
    return manifest


def download_matching(args):
    repository = args.repository
    if not repository:
        return None, 'No Actions repository specified. Dashboard and local downloads are ready.', None
    if args.run_id:
        runs = [api(f'repos/{repository}/actions/runs/{args.run_id}')]
    else:
        query = urllib.parse.urlencode({'status': 'success', 'branch': args.branch, 'per_page': 20})
        runs = api(f'repos/{repository}/actions/workflows/gds.yaml/runs?{query}')['workflow_runs']
    reasons = []
    for run in runs:
        if run.get('conclusion') != 'success':
            continue
        artifacts = api(f'repos/{repository}/actions/runs/{run["id"]}/artifacts?per_page=100')['artifacts']
        for artifact in artifacts:
            if artifact.get('name') != ARTIFACT or artifact.get('expired'):
                continue
            try:
                content = api(f'repos/{repository}/actions/artifacts/{artifact["id"]}/zip', True)
                target = Path(tempfile.mkdtemp(prefix='garda-layout-'))
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    for item in archive.infolist():
                        if item.is_dir():
                            continue
                        name = item.filename
                        if '/' in name or '\\' in name or name in ('.', '..'):
                            raise ValueError('Unexpected nested physical artifact path')
                        (target / name).write_bytes(archive.read(item))
                return matching_artifact(target), None, target
            except (ValueError, OSError, zipfile.BadZipFile) as exc:
                reasons.append(str(exc))
    return None, (reasons[-1] if reasons else 'No successful source-matched physical artifact is available yet.'), None


def layout_page(status):
    available = status['available']
    if available:
        pdk = html.escape(status['pdk'], quote=True)
        detail = f'''<p>Actual OASIS/GDSII from successful Tiny Tapeout run {html.escape(status['run_id'])}.
        Source and configuration hashes match this repository.</p>
        <p><a id="viewer" href="#">Open actual 3D layout viewer</a></p>
        <p><a href="../tinytapeout.oas">Download OASIS</a> <a href="../tinytapeout.gds">Download GDSII</a></p>
        <p><a href="manifest.json">Inspect provenance and SHA256 hashes</a></p>
        <script>document.getElementById('viewer').href='https://gds-viewer.tinytapeout.com/?pdk={pdk}&model='+encodeURIComponent(new URL('../tinytapeout.oas',location.href).href)</script>'''
        if status.get('preview'):
            detail += '<img alt="Actual physical layout render" src="' + html.escape(status['preview'], quote=True) + '">'
    else:
        detail = '<p>' + html.escape(status['reason']) + '</p><p>The interactive dashboard shows a conceptual block model. It is not an ASIC layout or physical signoff result.</p>'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>GARDA actual physical layout</title><style>body{margin:0;background:#10151d;color:#e3edf7;font:18px/1.6 system-ui}main{max-width:980px;margin:auto;padding:48px 24px}a{color:#7fe5e0;margin-right:24px}img{max-width:100%;border-radius:16px}h1{font-size:clamp(32px,5vw,56px)}</style>
    <main><a href="../">Back to GARDA RTL Explorer</a><h1>Actual Tiny Tapeout physical layout</h1>''' + detail + '</main></html>'


def build(args):
    args.output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'dashboard' / 'dist', args.output, dirs_exist_ok=True)
    # A reused local output must not retain a layout from an older RTL revision.
    for stale in ('tinytapeout.oas', 'tinytapeout.gds', 'layout/manifest.json'):
        target = args.output / stale
        if target.is_file():
            target.unlink()
    manifest = None
    reason = 'Physical flow pending. Dashboard and source downloads are available.'
    if args.artifact_dir:
        try:
            manifest = matching_artifact(args.artifact_dir)
            source = args.artifact_dir
        except (ValueError, OSError) as exc:
            reason = str(exc)
    elif args.fetch_artifact:
        try:
            manifest, reason, source = download_matching(args)
        except (ValueError, OSError) as exc:
            reason = 'Physical artifact lookup unavailable: ' + str(exc)
    status = {'available': bool(manifest), 'kind': 'actual-physical-layout' if manifest else 'pending', 'reason': reason}
    layout = args.output / 'layout'
    layout.mkdir(exist_ok=True)
    if manifest:
        status.update({key: manifest[key] for key in ('pdk', 'run_id', 'commit', 'top_module')})
        for name in manifest['files']:
            shutil.copy2(source / name, args.output / name)
        previews = [n for n in manifest['files'] if n.endswith('.png')]
        if previews:
            status['preview'] = '../' + previews[0]
        shutil.copy2(source / 'manifest.json', layout / 'manifest.json')
    (layout / 'index.html').write_text(layout_page(status), encoding='utf-8')
    (args.output / 'data' / 'physical-layout.json').write_text(json.dumps(status, indent=2) + '\n')
    (args.output / '.nojekyll').touch()
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('physical_available=' + str(bool(manifest)).lower() + '\n')
    print(json.dumps(status, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('package')
    p.add_argument('--submission', type=Path, required=True)
    p.add_argument('--render', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--commit', required=True)
    p = commands.add_parser('build')
    p.add_argument('--output', type=Path, default=ROOT / '.work' / 'pages')
    p.add_argument('--artifact-dir', type=Path)
    p.add_argument('--fetch-artifact', action='store_true')
    p.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY'))
    p.add_argument('--branch', default='main')
    p.add_argument('--run-id')
    args = parser.parse_args()
    (package if args.command == 'package' else build)(args)


if __name__ == '__main__':
    main()
