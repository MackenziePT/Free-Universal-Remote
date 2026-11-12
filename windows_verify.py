"""Non-administrative Windows acceptance checks using disposable temporary files.

No permanent settings, firewall, router, startup entry or user projects are changed.
This does not validate the OpenAI-hosted tunnel or the ChatGPT account connection.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from remote_core import (Config, PolicyError, diagnostic, file_info, read_text,
                         safe_path, write_text, _is_link_or_junction,
                         search_files, read_binary, execute_once, operation_status)


@unittest.skipUnless(os.name == "nt", "Windows NTFS/PowerShell integration requires Windows")
class WindowsAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="harmony-acceptance-")
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.allowed = base / "allowed"
        self.allowed.mkdir()
        grant = base / "grants.json"
        grant.write_text(json.dumps({"expires_at": time.time() + 60,
                                     "capabilities": ["writes"]}), encoding="utf-8")
        self.policy = Config(allowed_roots=(self.allowed.resolve(),),
                             grants_path=grant, backup_root=base / "backups",
                             enable_writes=True)

    def test_unicode_and_approved_root(self):
        src = self.allowed / "língua-😀.txt"
        src.write_text("Harmony · português · 🌿", encoding="utf-8")
        result = read_text(self.policy, str(src), max_bytes=64)
        self.assertEqual(result["text"], "Harmony · português · 🌿")
        with self.assertRaises(PolicyError):
            safe_path(str(src.parent.parent / "grants.json"), self.policy)

    def test_write_backups_and_atomic_creation_on_scratch_only(self):
        created = self.allowed / "temporary.txt"
        first = write_text(self.policy, str(created), "first")
        self.assertEqual(first["sha256"], hashlib.sha256(b"first").hexdigest())
        digest = file_info(self.policy, str(created))["sha256"]
        second = write_text(self.policy, str(created), "second", expected_sha256=digest)
        self.assertEqual(created.read_text(encoding="utf-8"), "second")
        self.assertEqual(Path(second["backup"]).read_text(encoding="utf-8"), "first")

    def test_ntfs_reparse_alias_block(self):
        real = self.allowed / "actual"
        real.mkdir()
        alias = self.allowed / "alias"
        try:
            alias.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not available for this Windows account")
        self.assertTrue(_is_link_or_junction(alias))
        with self.assertRaises(PolicyError):
            safe_path(str(alias / "any.txt"), self.policy)

    def test_bounded_file_search_and_binary_transfer(self):
        folder = self.allowed / "test_data"
        folder.mkdir()
        blob = folder / "payload.bin"
        blob.write_bytes(bytes(range(128)))
        matches = search_files(self.policy, str(self.allowed), "*.bin")
        self.assertEqual(len(matches["matches"]), 1)
        import base64
        chunk = read_binary(self.policy, str(blob), 9, 15)
        self.assertEqual(base64.b64decode(chunk["base64"]), bytes(range(9, 24)))

    def test_operation_journal_rejects_repeated_privileged_action(self):
        identifier = str(uuid.uuid4())
        counter = self.allowed / 'counter.txt'
        def perform():
            counter.write_text('executed once', encoding='utf-8')
            return 'ok'
        self.assertEqual(execute_once(self.policy, identifier, 'scratch', 'test', perform), 'ok')
        with self.assertRaises(PolicyError):
            execute_once(self.policy, identifier, 'scratch', 'test', perform)
        self.assertEqual(counter.read_text(encoding='utf-8'), 'executed once')
        self.assertEqual(operation_status(self.policy, identifier)['state'], 'completed')

    def test_virtual_desktop_bounds_from_win32(self):
        from desktop_unicode import virtual_screen_bounds, validate_click_coordinates
        left, top, right, bottom = virtual_screen_bounds()
        self.assertGreater(right, left)
        self.assertGreater(bottom, top)
        self.assertEqual(validate_click_coordinates(left, top, (left, top, right, bottom)), (left, top))

    def test_readonly_powershell_computer_diagnostic(self):
        outcome = diagnostic(self.policy, "computer")
        self.assertFalse(outcome["timed_out"])
        self.assertEqual(outcome["exit_code"], 0, outcome["stderr"][-600:])
        self.assertIn("Manufacturer", outcome["stdout"])


if __name__ == "__main__":
    if os.name != "nt":
        print("NOT VERIFIED: Windows acceptance requires a real Windows host.", file=sys.stderr)
        sys.exit(2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WindowsAcceptanceTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
