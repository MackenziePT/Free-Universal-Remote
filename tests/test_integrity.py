"""Behavioral regressions for safe overwrites and deterministic fingerprints."""
import hashlib
import json
import os
import tempfile
import time
import unittest
from dataclasses import replace
from unittest.mock import patch
from pathlib import Path
from remote_core import Config, PolicyError, file_info, write_text


class FileIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / 'approved'
        self.root.mkdir()
        grant = base / 'grants.json'
        grant.write_text(json.dumps({'expires_at': time.time() + 120, 'capabilities':['writes']}))
        self.cfg = Config(allowed_roots=(self.root.resolve(),), backup_root=base/'backups',
                          grants_path=grant, enable_writes=True)

    def test_existing_file_requires_fingerprint(self):
        path = self.root/'doc.txt'
        path.write_text('first')
        with self.assertRaisesRegex(PolicyError, 'expected_sha256'):
            write_text(self.cfg, str(path), 'second')
        self.assertEqual(path.read_text(), 'first')

    def test_stale_fingerprint_rejected_without_backup_or_mutation(self):
        path = self.root/'doc.txt'
        path.write_text('third')
        with self.assertRaises(PolicyError):
            write_text(self.cfg, str(path), 'fourth', expected_sha256='0' * 64)
        self.assertEqual(path.read_text(), 'third')
        self.assertFalse(self.cfg.backup_root.exists())

    def test_fingerprint_allows_overwrite_with_backup(self):
        path = self.root/'doc.txt'
        path.write_text('old')
        fp = file_info(self.cfg, str(path))['sha256']
        saved = write_text(self.cfg, str(path), 'new', expected_sha256=fp)
        self.assertEqual(path.read_text(), 'new')
        self.assertEqual(Path(saved['backup']).read_text(), 'old')

    def test_new_file_creation_rejects_stale_expectation(self):
        with self.assertRaises(PolicyError):
            write_text(self.cfg, str(self.root/'new.txt'), 'hello', expected_sha256='0'*64)

    def test_new_file_race_does_not_overwrite_concurrent_writer(self):
        target = self.root / 'created-by-other.txt'
        real_link = os.link
        def simultaneous_write(source, destination, *args, **kwargs):
            Path(destination).write_text('concurrent owner', encoding='utf-8')
            return real_link(source, destination, *args, **kwargs)
        with patch('remote_core.os.link', side_effect=simultaneous_write):
            with self.assertRaises(PolicyError):
                write_text(self.cfg, str(target), 'ours')
        self.assertEqual(target.read_text(), 'concurrent owner')

    def test_existing_hardlink_rejected(self):
        original = self.root/'data.txt'
        original.write_text('original')
        linked = self.root/'linked.txt'
        try:
            os.link(original, linked)
        except (OSError, NotImplementedError):
            self.skipTest('hardlinks not available')
        with self.assertRaises(PolicyError):
            write_text(self.cfg, str(linked), 'new', expected_sha256=hashlib.sha256(b'original').hexdigest())
        self.assertEqual(original.read_text(), 'original')

    def test_file_info_does_not_leak_hash_of_large_file(self):
        self.cfg = replace(self.cfg, max_write_bytes=4)
        path = self.root/'large.txt'
        path.write_text('larger')
        self.assertIsNone(file_info(self.cfg, str(path))['sha256'])

if __name__ == '__main__':
    unittest.main()
