"""Generate presentation status directly from recorded verification evidence."""
from pathlib import Path
import json
from current_rtl_evidence import current_evidence
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
summary = 'Model 6.020 kata: hasil RTL dan antarmuka pin tercatat di bawah. Bukti netlist/routing IHP berasal dari build historis; signoff SKY130 dinilai terpisah.'
report = {
    'schema': 'garda-dashboard-evidence-1',
    'current_rtl': current_evidence(ROOT.parent),
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
activity = ROOT.parent / 'evidence/neural_logic_activity.json'
if activity.is_file():
    (DATA / 'neural-logic-activity.json').write_bytes(activity.read_bytes())
print(json.dumps({'current_rtl': report['current_rtl']['status'], 'functional_pass': functional, 'checks': [(entry['label'], entry['result']) for entry in report['checks']]}))

