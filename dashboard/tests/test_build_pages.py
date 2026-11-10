"""Physical artifacts must match active RTL and pass integrity checks."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('build_pages', Path(__file__).parents[1] / 'scripts' / 'build_pages.py')
PAGES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PAGES)


class PhysicalArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for name in ('tinytapeout.oas', 'tinytapeout.gds'):
            (self.folder / name).write_bytes(b'test artifact integrity payload')
        self.manifest = {
            'schema_version': 1, 'kind': 'garda-physical-viewer',
            'top_module': 'tt_um_wlmoi_garda_neural_logic',
            'checks': {'gds': 'success', 'precheck': 'success', 'gl_test': 'success'},
            'source_sha256': PAGES.source_hashes(),
            'files': {name: PAGES.digest(self.folder / name)
                      for name in ('tinytapeout.oas', 'tinytapeout.gds')},
        }
        self.save()

    def save(self):
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_matching_artifact_is_accepted(self):
        self.assertEqual(PAGES.matching_artifact(self.folder), self.manifest)

    def test_stale_rtl_is_rejected(self):
        self.manifest['source_sha256']['info.yaml'] = 'different revision'
        self.save()
        with self.assertRaisesRegex(ValueError, 'different RTL'):
            PAGES.matching_artifact(self.folder)

    def test_failed_gate_level_check_is_rejected(self):
        self.manifest['checks']['gl_test'] = 'failure'
        self.save()
        with self.assertRaisesRegex(ValueError, 'every required check'):
            PAGES.matching_artifact(self.folder)

    def test_corrupt_layout_is_rejected(self):
        (self.folder / 'tinytapeout.oas').write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            PAGES.matching_artifact(self.folder)

    def test_unsafe_path_is_rejected(self):
        self.manifest['files']['../outside'] = 'bad'
        self.save()
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            PAGES.matching_artifact(self.folder)


if __name__ == '__main__':
    unittest.main()
