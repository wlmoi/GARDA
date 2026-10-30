"""Bind an RTL regression claim to the exact four source files it measured."""
from pathlib import Path
import hashlib
import json

SOURCES = (
    'src/garda_neural_logic_top.v',
    'src/garda_parameter_logic.v',
    'src/garda_neural_datapath_logic.v',
    'src/garda_activation_logic.v',
)


def source_digest(repo):
    return hashlib.sha256(b''.join(
        (Path(repo) / name).read_bytes().replace(b'\r\n', b'\n')
        for name in SOURCES)).hexdigest()


def current_evidence(repo):
    repo = Path(repo)
    artifact = repo / 'evidence/neural_logic_activity.json'
    result = {
        'status': 'rerun_required',
        'source_match': False,
        'source_files': list(SOURCES),
        'source_hash_normalization': 'concatenate source_files in order; CRLF to LF',
        'result': 'Perlu uji ulang',
        'summary': 'Bukti RTL aktif belum tersedia untuk source ini.',
        'activity_summary': '',
        'artifact': 'neural-logic-activity.json',
    }
    try:
        raw = json.loads(artifact.read_text(encoding='utf-8'))
        result['current_source_sha256'] = source_digest(repo)
        result['measured_source_sha256'] = raw.get('source_sha256', {}).get('current')
        result['source_match'] = result['current_source_sha256'] == result['measured_source_sha256']
        if raw.get('status') != 'PASS' or not result['source_match']:
            result['summary'] = 'Source berubah atau regresi belum lulus. Jalankan ulang verifikasi RTL.'
            return result
        result.update({
            'status': 'pass',
            'result': f"PASS / {raw['outputs_checked_per_revision']} cocok",
            'vectors': raw['vectors_per_revision'],
            'outputs_checked': raw['outputs_checked_per_revision'],
            'model_words': raw['model_words'],
            'latency_cycles': raw['latency_cycles_after'],
            'summary': (f"{raw['vectors_per_revision']} vektor · {raw['outputs_checked_per_revision']} keluaran cocok · "
                        f"{raw['model_words']:,} kata · {raw['latency_cycles_after']:,} clock.").replace(',', '.'),
            'activity_summary': (f"Transisi operand MAC turun {raw['combined_bit_transition_reduction_percent']:.2f}% "
                                 'pada vektor uji. Ini indikator aktivitas RTL, bukan pengukuran daya.').replace('.', ',', 1),
            'physical_power_measured': raw.get('physical_power_measured', False),
        })
    except (OSError, ValueError, KeyError, TypeError):
        return result
    return result
