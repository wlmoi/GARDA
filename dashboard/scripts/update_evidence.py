"""Generate presentation status directly from recorded verification evidence."""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'dist/data'
raw = json.loads((ROOT.parent / 'evidence/tinytapeout/current/verification.json').read_text(encoding='utf-8'))
def check(key, label, details=None):
    section = raw.get(key, {})
    status = section.get('status', 'NOT_RUN')
    result = details if status == 'PASS' and details else {
        'PASS': 'PASS', 'RUNNING': 'Berjalan', 'NOT_RUN': 'Belum signoff',
        'FAIL': 'Perlu perbaikan', 'PENDING': 'Menunggu'
    }.get(status, status)
    return {'label': label, 'status': 'pass' if status == 'PASS' else status.lower(), 'result': result}
functional = all(raw.get(key, {}).get('status') == 'PASS' for key in ('rtl', 'generic', 'cocotb'))
summary = 'Bukti historis IHP berasal dari revisi sebelum perubahan nama GARDA; bukan hasil verifikasi SKY130 atau GDS baru. Model tetap 6.020 kata diuji melalui RTL dan antarmuka pin TinyTapeout. '
if raw.get('mapped', {}).get('status') == 'PASS':
    summary += 'Netlist sel IHP juga lolos simulasi fungsional tanpa SDF. '
if raw.get('global_routing', {}).get('status') == 'PASS':
    summary += 'Global routing telah lolos tanpa overflow. '
if raw.get('detailed_routing', {}).get('status') == 'PASS':
    summary += 'Detailed routing selesai sesuai laporan. '
summary += 'DRC, LVS dan timing signoff dinilai terpisah sesuai bukti yang tersedia.'
report = {
    'schema': 'garda-dashboard-evidence-1',
    'checked_date': raw.get('generated_date', 'Lihat laporan'),
    'functional_pass': functional,
    'top': raw['top'],
    'summary': summary,
    'checks': [
        check('rtl', 'RTL / 100 vektor, 400 keluaran', 'PASS / 400 cocok'),
        check('generic', 'Netlist sintesis generik', 'PASS'),
        check('cocotb', 'Cocotb / antarmuka pin', 'PASS / 2 test'),
        check('mapped', 'Netlist sel IHP / tanpa SDF'),
        check('global_routing', 'Global routing / overflow', 'PASS / 0'),
        check('detailed_routing', 'Detailed routing'),
        check('physical_signoff', 'DRC, LVS, timing signoff')
    ],
    'raw_report': 'tinytapeout-raw.json',
    'qualification': raw['scope']
}
DATA.mkdir(exist_ok=True)
(DATA / 'tinytapeout-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(DATA / 'tinytapeout-raw.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'functional_pass': functional, 'checks': [(entry['label'], entry['result']) for entry in report['checks']]}))

