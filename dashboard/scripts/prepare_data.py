"""Export canonical repository RTL and deterministic downloadable project bundles."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, zipfile
ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
DIST = ROOT / 'dist'
EXCLUDED = {'db', 'incremental_db', '__pycache__', 'sim_build', '.venv', '.git'}
def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in ('absolute_path', 'repository')}
    if isinstance(value, list): return [clean(v) for v in value]
    return value
def write_bundle(destination, entries):
    """Stable timestamps and sorted names keep release hashes reproducible."""
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, source in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
def collect(root, prefix):
    return {prefix + path.relative_to(root).as_posix(): path for path in root.rglob('*')
            if path.is_file() and not EXCLUDED.intersection(path.relative_to(root).parts)
            and path.suffix not in {'.pyc', '.vcd', '.fst', '.out'}}
subprocess.run([sys.executable, str(ROOT / 'scripts/build_catalog.py')], check=True)
catalog_path = DIST / 'data/rtl-catalog.json'
catalog = clean(json.loads(catalog_path.read_text(encoding='utf-8')))
for module in catalog['modules'] + catalog['asic_modules']:
    source = REPO / module['file']
    payload = source.read_bytes().replace(b'\r\n', b'\n')
    module['sha256'] = hashlib.sha256(payload).hexdigest()
    destination = DIST / 'source' / module['file']
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
catalog['source_hash_normalization'] = 'CRLF to LF for Verilog source'
catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for asset in ('dm-sans-400.woff2', 'montserrat-700.woff2', 'DM_SANS_OFL.txt', 'MONTSERRAT_OFL.txt'):
    if not (DIST / 'assets' / asset).is_file():
        raise FileNotFoundError(f'Missing vendored font or license: {asset}')
downloads = DIST / 'downloads'
downloads.mkdir(exist_ok=True)
ready = REPO / 'ImplementationReadyQuartus/IGOR_DE10_NANO'
write_bundle(downloads / 'IGOR_DE10_NANO_READY.zip', collect(ready, 'IGOR_DE10_NANO/'))
shutil.copyfile(ready / 'quartus/output_files/igor.sof', downloads / 'igor.sof')
entries = {}
for name in ('garda_neural_logic_top.v', 'garda_parameter_logic.v', 'garda_neural_datapath_logic.v', 'garda_activation_logic.v'):
    entries['src/' + name] = REPO / 'src' / name
for part in ('test', 'reference_model', 'assets', 'scripts', 'asic/neural_logic'):
    entries.update(collect(REPO / part, part + '/'))
for name in ('evidence/neural_logic_activity.json', 'info.yaml', 'docs/info.md', 'requirements.txt', 'requirements-layout.txt',
             'requirements-asic.txt', 'librelane_plugin_neural_sram.py', 'LICENSE',
             '.github/workflows/gds.yaml', '.github/workflows/docs.yaml',
             'dashboard/scripts/build_pages.py'):
    source = REPO / name
    if source.is_file(): entries[name] = source
evidence = REPO / 'evidence/tinytapeout/current'
if evidence.is_dir():
    entries.update({name: path for name, path in collect(evidence, 'evidence/tinytapeout/current/').items()
                    if path.stat().st_size < 10_000_000})
write_bundle(downloads / 'TINYTAPEOUT_SOURCE.zip', entries)
subprocess.run([sys.executable, str(ROOT / 'scripts/update_evidence.py')], check=True)
print('Prepared', len(catalog['modules']), 'FPGA modules and', len(catalog['asic_modules']),
      'ASIC modules from canonical repository source')

