#!/usr/bin/env python3
"""Freeze verified FPGA sources/reports/images, or check that none have drifted."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'evidence/current_release/manifest.json'

def sha(path):
    with path.open('rb') as stream:
        return sha_stream(stream)

def sha_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()

def local(name):
    path = (ROOT / name.replace('\\', '/')).resolve()
    if not path.is_relative_to(ROOT):
        raise RuntimeError(f'Path escapes FPGA package: {name}')
    return path

def metadata(path):
    return {'sha256': sha(path), 'bytes': path.stat().st_size}

def check_mapping(mapping):
    problems = []
    for name, entry in mapping.items():
        path = local(name)
        expected = entry if isinstance(entry, str) else entry['sha256']
        if not path.is_file() or sha(path) != expected:
            problems.append(name)
    if problems:
        raise RuntimeError('Changed or missing recorded files: ' + ', '.join(problems[:12]))

def verify_build(name):
    path = ROOT / 'evidence/current_builds' / (name + '.json')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('status') != 'PASS' or not record.get('source_unchanged'):
        raise RuntimeError(f'{name}: build has not passed with unchanged inputs')
    check_mapping(record['source_sha256'])
    check_mapping(record['report_sha256'])
    check_mapping({record['log']: record['log_sha256'], record['sof']: record['sof_sha256']})
    if not record.get('slacks_ns') or min(record['slacks_ns'].values()) < 0:
        raise RuntimeError(f'{name}: timing checks did not pass')
    return record

def verify_software_model():
    relative = Path('igor_navigation/igor_navigation/weights/model_weights.json')
    original = json.loads((ROOT.parent / 'src' / relative).read_text(encoding='utf-8'))
    deployed = json.loads((ROOT / 'software_integration/src' / relative).read_text(encoding='utf-8'))
    if any(original[key] != deployed[key] for key in ('w1','b1','w2','b2','w3','b3')):
        raise RuntimeError('Integrated host model differs from the source model verified against RTL')

def write_build_status(records):
    lines = ['# Status build dan handoff DE10-Nano', '',
             'Dihasilkan dari receipt kompilasi dengan input tidak berubah. Target kedua project: '
             '**5CSEBA6U23I7, Quartus Prime Standard 25.1, clock 50 MHz**.', '',
             '| Project | ALM | Register | M10K | DSP | Setup terburuk | Hold terburuk | Pin | Warning |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name, record in records.items():
        project = local(record['sof']).parent.parent
        summary = (project / 'output_files' / (record['revision'] + '.fit.summary')).read_text(encoding='utf-8')
        def value(label):
            return re.search(r'^' + re.escape(label) + r'\s*:\s*(.*)$', summary, re.M).group(1).strip().split(' /')[0]
        slacks = record['slacks_ns']
        setup = min(v for k,v in slacks.items() if 'Setup' in k)
        hold = min(v for k,v in slacks.items() if 'Hold' in k)
        log = local(record['log']).read_text(encoding='utf-8')
        warning = re.search(r'Full Compilation was successful\. 0 errors, (\d+) warnings', log)
        lines.append(f"| {name} | {value('Logic utilization (in ALMs)')} | {value('Total registers')} | "
                     f"{value('Total RAM Blocks')} | {value('Total DSP Blocks')} | +{setup:.3f} ns | +{hold:.3f} ns | "
                     f"{len(record['pin_assignments'])} | {warning.group(1) if warning else 'lihat log'} |")
    lines += ['', 'Seluruh corner setup/hold/recovery/removal/minimum-pulse-width yang dilaporkan nonnegatif. '
              'Pin locations, standar I/O 3,3 V, output drive 16 mA dan slew 1 tercantum eksplisit pada pinplan; '
              'laporan fitted `.pin` dan I/O memuat hasil penempatan aktual.', '',
              '## Identitas build', '']
    for name, record in records.items():
        finished = datetime.fromisoformat(record['finished_utc']).astimezone(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S WIB')
        lines += [f"- **{name}** selesai {finished}; receipt [JSON](evidence/current_builds/{name}.json).",
                  f"  SOF SHA256: `{record['sof_sha256']}`."]
    lines += ['', '## Warning yang direview', '',
              'Tiga warning policy berasal dari port tulis internal ROM (`data_a`, `waddr_a`, `we_a`) '
              'yang tidak memiliki driver karena memori digunakan read-only. Model parameter diinisialisasi '
              'dari MEM, dibandingkan dengan source, dan diuji melalui oracle integer. Ini bukan warning '
              'bahwa bobot aktif tidak terisi.', '',
              'Planner juga mencatat RAM read-during-write pass-through logic dan dua input SW0/SW1 '
              'yang tidak mempengaruhi output. Referensi lengkap adalah warning pada `compile_current.log` '
              'dan `igor.map.rpt`. Tidak ada warning missing drive/slew sesudah pinplan eksplisit. '
              'Tidak ada critical warning atau timing gagal pada flow kompilasi rilis yang diterima. '
              'Pernyataan ini tidak mencakup Power Analyzer; analisis power terpisah mempunyai '
              'Critical Warning HPS dan confidence Low yang dijelaskan pada '
              '[METRICS_AND_POWER.md](docs/METRICS_AND_POWER.md).', '',
              '## Pemeriksaan paket', '',
              '```powershell', 'python scripts/freeze_release.py --check', '```', '',
              'Manifest [current_release/manifest.json](evidence/current_release/manifest.json) mengikat '
              'source, pinplan, model, hasil pengujian, laporan dan kedua SOF. Handoff image dan checksum '
              'ada di [bitstreams/](bitstreams/). Ubah source, bobot, QSF/SDC/pinplan berarti receipt '
              'lama tidak berlaku dan harus dibangun ulang.', '',
              '## Status perangkat fisik', '',
              'Status konfigurasi fisik terbaru dicatat per percobaan pada '
              '[evidence/current_programming/](evidence/current_programming/), dengan project, SHA256 SOF, '
              'chain, log Quartus dan field `hardware_programmed`. Programming SRAM yang sukses '
              'tidak otomatis membuktikan fungsi UART, motor/robot, daya atau latensi fisik. '
              'Lihat [BOARD_PROGRAMMING.md](docs/BOARD_PROGRAMMING.md), '
              '[GPIO_AND_HPS.md](docs/GPIO_AND_HPS.md), dan '
              '[FINAL_ACCEPTANCE.md](docs/FINAL_ACCEPTANCE.md) untuk prosedur dan pekerjaan tersisa.', '']
    (ROOT / 'BUILD_STATUS.md').write_text('\n'.join(lines), encoding='utf-8')

def check():
    doc = json.loads(MANIFEST.read_text(encoding='utf-8'))
    check_mapping(doc['files'])
    for name in ('source_policy', 'planner'):
        verify_build(name)
        sof = local(doc['projects'][name]['sof'])
        if sha(sof) != sha(local(doc['projects'][name]['handoff_sof'])):
            raise RuntimeError('Handoff image differs from compiled image')
    verify_software_model()
    if 'source_policy_parallel8' in doc['projects']:
        check_parallel8()
        item=doc['projects']['source_policy_parallel8']
        if sha(local(item['sof'])) != sha(local(item['handoff_sof'])):
            raise RuntimeError('Parallel8 handoff differs from accepted SOF')
    # Pure software references are read-only external inputs, not release writes.
    for name, expected in doc.get('reference_sha256', {}).items():
        path = (ROOT.parent / name.replace('\\', '/')).resolve()
        if not path.is_relative_to(ROOT.parent / 'src') or not path.is_file() or sha(path) != expected:
            raise RuntimeError(f'Original software model reference changed: {name}')
    print(f"PASS release integrity: {len(doc['files'])} files; FPGA source-bound SOFs, timing and pins verified. Imported ASIC sign-off is assessed separately.")

def check_parallel8():
    path=ROOT/'experiments/parallel8/artifacts/acceptance.json'
    record=json.loads(path.read_text(encoding='utf-8'))
    if record['status']!='PASS' or record['latency_ms']>=0.16 or min(record['timing_slack_ns'].values())<0:
        raise RuntimeError('Parallel8 candidate has not passed latency/timing acceptance')
    check_mapping(record['sha256'])
    check_mapping({'experiments/parallel8/output_files/igor_src_policy.sof':record['sof_sha256']})
    return record

def freeze():
    records = {name: verify_build(name) for name in ('source_policy', 'planner')}
    verify_software_model()
    write_build_status(records)
    subprocess.run([sys.executable, str(ROOT / 'verification/audit_acceptance.py')], cwd=ROOT, check=True)
    audit = json.loads((ROOT / 'evidence/current_acceptance/audit.json').read_text(encoding='utf-8'))
    if audit['status'] != 'PASS':
        raise RuntimeError('Source/evidence acceptance has not passed')
    bitstreams = ROOT / 'bitstreams'
    bitstreams.mkdir(exist_ok=True)
    projects = {}
    for name, record in records.items():
        target = bitstreams / ('igor_src_policy.sof' if name == 'source_policy' else 'igor_planner.sof')
        shutil.copyfile(local(record['sof']), target)
        projects[name] = {'sof': record['sof'], 'handoff_sof': target.relative_to(ROOT).as_posix(),
                          'sha256': sha(target), 'build_receipt': f'evidence/current_builds/{name}.json',
                          'minimum_slack_ns': min(record['slacks_ns'].values()),
                          'assigned_pins': len(record['pin_assignments']),
                          'device': '5CSEBA6U23I7', 'clock_hz': 50000000}
    parallel_receipt=ROOT/'experiments/parallel8/artifacts/acceptance.json'
    if parallel_receipt.exists():
        fast=check_parallel8()
        source=ROOT/'experiments/parallel8/output_files/igor_src_policy.sof'
        target=bitstreams/'igor_src_policy_parallel8.sof'
        shutil.copyfile(source,target)
        projects['source_policy_parallel8']={'sof':source.relative_to(ROOT).as_posix(),
            'handoff_sof':target.relative_to(ROOT).as_posix(),'sha256':sha(target),
            'build_receipt':parallel_receipt.relative_to(ROOT).as_posix(),
            'minimum_slack_ns':min(fast['timing_slack_ns'].values()),
            'assigned_pins':len(fast['pins']),'device':'5CSEBA6U23I7','clock_hz':50000000}
    (bitstreams / 'SHA256SUMS.txt').write_text(''.join(f"{sha(path)}  {path.name}\n" for path in sorted(bitstreams.glob('*.sof'))), encoding='ascii')
    waveform_roots = [ROOT / 'evidence/current_safety', ROOT / 'evidence/current_board_wrapper',
                      ROOT / 'verification/src_policy/artifacts']
    for folder in waveform_roots:
        for path in folder.glob('*.vcd'):
            archive = path.with_suffix('.vcd.gz')
            if archive.is_file():
                try:
                    with gzip.open(archive, 'rb') as existing:
                        if sha_stream(existing) == sha(path):
                            continue
                except (OSError, EOFError):
                    pass
            with path.open('rb') as source, (path.with_suffix('.vcd.gz')).open('wb') as output:
                with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0, compresslevel=6) as compressed:
                    shutil.copyfileobj(source, compressed)
    tracked = set()
    source_trees = ['rtl', 'assets', 'reference_model', 'verification', 'scripts', 'ci', 'src', 'test', 'robot/jetauto',
                    'software_integration/src', 'fpga_de10_nano/src_policy', 'fpga_de10_nano/quartus']
    source_extensions = {'.v','.sv','.vh','.svh','.vhd','.py','.ps1','.mem','.mif','.hex','.h','.cpp','.sby','.json','.yaml','.yml','.qpf','.qsf','.sdc','.tcl','.gtkw'}
    for tree in source_trees:
        for path in (ROOT / tree).rglob('*'):
            if not path.is_file() or any(part in {'db','incremental_db','__pycache__','build','sim_build','output_files','artifacts','evaluations','logs'} for part in path.relative_to(ROOT).parts):
                continue
            if path.suffix in source_extensions:
                tracked.add(path)
    for folder in [ROOT / 'evidence/current_safety', ROOT / 'evidence/current_board_wrapper',
                   ROOT / 'evidence/current_host', ROOT / 'evidence/current_lidar',
                   ROOT / 'evidence/current_checks', ROOT / 'evidence/current_builds',
                   ROOT / 'evidence/current_acceptance', ROOT / 'evidence/current_programming',
                   ROOT / 'evidence/current_metrics',
                   ROOT / 'evidence/chip_highlights',
                   ROOT / 'evidence/bennaya_answers',
                   ROOT / 'verification/src_policy/artifacts']:
        if folder.exists():
            tracked.update(p for p in folder.rglob('*') if p.is_file() and p.suffix in {'.json','.csv','.log','.hex','.gtkw','.gz','.rpt','.summary','.png','.cdf'})
    # Native GTKWave captures plus checkpoint/build identity and capture scripts.
    visual = ROOT / 'evidence/visual_review'
    if visual.exists():
        tracked.update(p for p in visual.rglob('*') if p.is_file() and
                       p.suffix in {'.png','.html','.json','.log','.tcl','.gtkw'})
    for record in records.values():
        tracked.update(local(name) for name in record['source_sha256'])
        tracked.update(local(name) for name in record['report_sha256'])
        tracked.add(local(record['log']))
    tracked.update(path for path in bitstreams.iterdir() if path.is_file() and path.suffix in {'.sof','.txt','.md','.bat','.cdf'})
    tracked.update(ROOT.glob('*.md'))
    tracked.update(ROOT.glob('*.bat'))
    tracked.update(ROOT.glob('requirements*.txt'))
    tracked.update((ROOT / 'docs').glob('*.md'))
    tracked.update((ROOT / 'software_integration').glob('*.md'))
    tracked.update((ROOT / 'scripts').glob('*.ps1'))
    if parallel_receipt.exists():
        tracked.add(parallel_receipt)
        tracked.update(local(name) for name in fast['sha256'])
        tracked.add(ROOT/'experiments/parallel8/output_files/igor_src_policy.sof')
    external_evidence={}
    for receipt in sorted((ROOT/'evidence/asic_import').glob('*/manifest.json')):
        imported=json.loads(receipt.read_text(encoding='utf-8'))
        for name,expected in imported.items():
            path=(receipt.parent/name).resolve()
            if not path.is_relative_to(receipt.parent.resolve()) or not path.is_file() or sha(path)!=expected:
                raise RuntimeError('Imported evidence changed: '+name)
            tracked.add(path)
        tracked.add(receipt)
        external_evidence[receipt.parent.name]={'manifest':receipt.relative_to(ROOT).as_posix(),
            'kind':'User-supplied evidence import, not a new ASIC sign-off run'}
    provenance = json.loads((ROOT / 'verification/src_policy/artifacts/model_provenance.json').read_text(encoding='utf-8'))
    references = {name.replace('\\', '/'): value for name, value in provenance['sha256'].items()
                  if name.replace('\\', '/').startswith('src/')}
    doc = {'schema': 1, 'generated_utc': datetime.now(timezone.utc).isoformat(),
           'scope': 'FPGA simulation/build/handoff and user-supplied ASIC evidence; no physical FPGA/robot acceptance or new ASIC sign-off',
           'external_evidence':external_evidence,
           'hardware_tests_executed': False, 'projects': projects,
           'reference_sha256': references,
           'files': {path.relative_to(ROOT).as_posix(): metadata(path) for path in sorted(tracked)}}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    print(f'FROZEN {len(tracked)} files: {MANIFEST}')
    check()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check existing release without regenerating any evidence')
    args = parser.parse_args()
    check() if args.check else freeze()
