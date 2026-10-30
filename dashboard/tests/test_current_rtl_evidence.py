"""The dashboard must never call stale RTL activity evidence a fresh pass."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from current_rtl_evidence import SOURCES, current_evidence, source_digest


class CurrentRTLEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        for index, relative in enumerate(SOURCES):
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f'module m{index};\nendmodule\n'.encode())
        self.artifact = self.repo / 'evidence/neural_logic_activity.json'
        self.artifact.parent.mkdir()
        self.proof = {
            'status': 'PASS', 'source_sha256': {'current': source_digest(self.repo)},
            'vectors_per_revision': 100, 'outputs_checked_per_revision': 400,
            'model_words': 6020, 'latency_cycles_after': 3080,
            'combined_bit_transition_reduction_percent': 14.3495,
            'physical_power_measured': False,
        }
        self.save()

    def save(self):
        self.artifact.write_text(json.dumps(self.proof), encoding='utf-8')

    def test_matching_source_is_a_pass(self):
        result = current_evidence(self.repo)
        self.assertEqual(result['status'], 'pass')
        self.assertTrue(result['source_match'])
        self.assertIn('400 cocok', result['result'])
        self.assertIn('14,35%', result['activity_summary'])
        self.assertFalse(result['physical_power_measured'])

    def test_changed_source_requires_rerun(self):
        (self.repo / SOURCES[2]).write_text('module changed; endmodule', encoding='utf-8')
        result = current_evidence(self.repo)
        self.assertEqual(result['status'], 'rerun_required')
        self.assertNotIn('PASS', result['result'])
        self.assertEqual(result['activity_summary'], '')

    def test_line_endings_do_not_invalidate_equivalent_source(self):
        for relative in SOURCES:
            path = self.repo / relative
            path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        self.assertEqual(current_evidence(self.repo)['status'], 'pass')

    def test_failed_run_with_matching_source_is_not_a_pass(self):
        self.proof['status'] = 'FAIL'
        self.save()
        self.assertEqual(current_evidence(self.repo)['status'], 'rerun_required')

    def test_missing_evidence_is_not_a_pass(self):
        self.artifact.unlink()
        self.assertEqual(current_evidence(self.repo)['status'], 'rerun_required')


if __name__ == '__main__':
    unittest.main()
