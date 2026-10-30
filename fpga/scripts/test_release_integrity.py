"""Regression for directory symlinks across Git's Linux/Windows checkouts."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from release_integrity import read_symlink_payload


class ReleaseIntegrityTests(unittest.TestCase):
    def test_materialized_git_symlink_preserves_exact_target_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / 'latest'
            target = b'run_20261008_160243'
            stub.write_bytes(target)
            self.assertEqual(read_symlink_payload(stub), target)
            original = hashlib.sha256(read_symlink_payload(stub)).digest()
            stub.write_bytes(b'run_other')
            self.assertNotEqual(hashlib.sha256(read_symlink_payload(stub)).digest(), original)

    def test_native_directory_link_matches_windows_git_stub(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            referent = root / 'run_20261008_160243'
            referent.mkdir()
            native = root / 'native'
            try:
                native.symlink_to(referent.name, target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f'Native symlinks unavailable: {error}')
            stub = root / 'windows'
            stub.write_bytes(referent.name.encode('utf-8'))
            self.assertTrue(native.is_dir())
            self.assertFalse(native.is_file())
            self.assertEqual(read_symlink_payload(native), read_symlink_payload(stub))
            # Changes inside the referent belong to its own file hashes.
            (referent / 'data').write_bytes(b'changed data')
            self.assertEqual(read_symlink_payload(native), read_symlink_payload(stub))
            # Dangling links still have a deterministic payload to verify.
            (referent / 'data').unlink()
            referent.rmdir()
            self.assertFalse(native.exists())
            self.assertTrue(native.is_symlink())
            self.assertEqual(read_symlink_payload(native), read_symlink_payload(stub))


if __name__ == '__main__':
    unittest.main()
