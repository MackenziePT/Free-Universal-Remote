"""Ensure audit does not silently accept altered / hidden release content."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('release_verifier', ROOT / 'tools' / 'verify_release.py')
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class ReleaseVerifierTests(unittest.TestCase):
    def test_clean_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'file.txt').write_text('hello')
            import hashlib
            digest = hashlib.sha256(b'hello').hexdigest()
            (root / 'SHA256SUMS.txt').write_text(f'{digest}  file.txt\n')
            self.assertEqual(verifier.verify_directory(root), [])

    def test_rejects_changed_and_unmanifested_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'file.txt').write_text('changed')
            (root / 'hidden.exe').write_bytes(b'sample')
            (root / 'SHA256SUMS.txt').write_text('0'*64 + '  file.txt\n')
            errors = verifier.verify_directory(root)
            self.assertTrue(any('SHA mismatch' in x for x in errors))
            self.assertTrue(any('unmanifested file' in x for x in errors))

    def test_status_preflight_never_reads_key(self):
        script = (ROOT / 'scripts' / 'Preflight-Remote.ps1').read_text()
        self.assertIn('LocalKeyFilePresent', script)
        self.assertNotIn('ConvertTo-SecureString', script)
        self.assertNotIn('CONTROL_PLANE_API_KEY', script)
