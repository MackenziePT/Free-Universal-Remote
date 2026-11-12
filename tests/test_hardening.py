"""Regression tests: privilege grants, limits, filesystem boundaries and process output."""
import json
import os
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from remote_core import (Config, PolicyError, grant_allowed, list_directory,
                         load_config, read_text, write_text, run_limited_process)


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'allowed'
        self.root.mkdir()
        self.cfg = Config(allowed_roots=(self.root,),
                          backup_root=self.base / 'backups',
                          grants_path=self.base / 'grants.json')

    def test_exact_directory_limit_does_not_claim_truncation(self):
        (self.root / 'only.txt').write_text('ok')
        self.assertFalse(list_directory(self.cfg, str(self.root), 1)['truncated'])
        (self.root / 'second.txt').write_text('ok')
        self.assertTrue(list_directory(self.cfg, str(self.root), 1)['truncated'])

    def test_true_permission_still_requires_fresh_local_grant(self):
        cfg = replace(self.cfg, enable_writes=True)
        with self.assertRaises(PolicyError):
            write_text(cfg, str(self.root / 'example.txt'), 'secret')

    def test_short_lived_grant_allows_only_requested_capability(self):
        expiry = time.time() + 60
        self.cfg.grants_path.write_text(json.dumps({'expires_at': expiry, 'capabilities': ['writes']}))
        self.assertTrue(grant_allowed(self.cfg, 'writes'))
        self.assertFalse(grant_allowed(self.cfg, 'shell'))
        cfg = replace(self.cfg, enable_writes=True)
        result = write_text(cfg, str(self.root / 'example.txt'), 'ok')
        self.assertEqual(Path(result['written']).read_text(), 'ok')

    def test_expired_or_invalid_grants_fail_closed(self):
        for value in [
            {'expires_at': time.time() - 1, 'capabilities': ['writes']},
            {'expires_at': time.time() + 50, 'capabilities': 'writes'},
            {'expires_at': float('nan'), 'capabilities': ['writes']},
            {'expires_at': time.time() + 86400, 'capabilities': ['writes']},
        ]:
            self.cfg.grants_path.write_text(json.dumps(value))
            self.assertFalse(grant_allowed(self.cfg, 'writes'), value)

    def test_backup_directory_cannot_be_inside_allowed_root(self):
        config = self.base / 'config.json'
        config.write_text(json.dumps({'allowed_roots': [str(self.root)],
                                      'backup_root': str(self.root / 'backups')}))
        with self.assertRaises(PolicyError):
            load_config(config)

    def test_grants_directory_cannot_be_inside_allowed_root(self):
        config = self.base / 'config.json'
        config.write_text(json.dumps({'allowed_roots': [str(self.root)],
                                      'grants_path': str(self.root / 'grants.json')}))
        with self.assertRaises(PolicyError):
            load_config(config)

    def test_symlink_target_cannot_be_written_even_inside_allowed_root(self):
        cfg = replace(self.cfg, enable_writes=True)
        self.cfg.grants_path.write_text(json.dumps({'expires_at': time.time() + 60, 'capabilities': ['writes']}))
        target = self.root / 'real.txt'
        target.write_text('original')
        link = self.root / 'link.txt'
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(PolicyError):
            write_text(cfg, str(link), 'modified')
        self.assertEqual(target.read_text(), 'original')

    def test_command_output_is_bounded(self):
        # Cross-platform command runner; no shell involved.
        result = run_limited_process([sys.executable, '-c', 'print("a" * 2000000)'],
                                     timeout=10, stdout_limit=1024, stderr_limit=1024)
        self.assertEqual(result['exit_code'], 0)
        self.assertLessEqual(len(result['stdout'].encode()), 1024)
        self.assertTrue(result['stdout_truncated'])

    def test_command_timeout_terminates_process(self):
        result = run_limited_process([sys.executable, '-c', 'import time; time.sleep(10)'],
                                     timeout=1, stdout_limit=1024, stderr_limit=1024)
        self.assertTrue(result['timed_out'])


if __name__ == '__main__':
    unittest.main()
