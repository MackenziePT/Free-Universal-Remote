import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from dataclasses import replace

from remote_core import Config, PolicyError, list_directory, load_config, read_text, safe_path, write_text, file_info, powershell, diagnostic


class CorePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "allowed"
        self.root.mkdir()
        self.other = base / "other"
        self.other.mkdir()
        self.cfg = Config(allowed_roots=(self.root.resolve(),), backup_root=(base / "backups"), grants_path=(base / "grants.json"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_write_is_disabled(self):
        with self.assertRaises(PolicyError):
            write_text(self.cfg, str(self.root / "a.txt"), "hello")

    def test_reject_relative_and_parent_traversal(self):
        for p in ("a.txt", str(self.root / ".." / "other" / "a.txt")):
            with self.assertRaises(PolicyError):
                safe_path(p, self.cfg)

    def test_symlink_escape_read(self):
        destination = self.other / "secret.txt"
        destination.write_text("dont read")
        link = self.root / "link"
        try:
            link.symlink_to(destination)
        except OSError:
            self.skipTest("Unable to create symbolic links")
        with self.assertRaises(PolicyError):
            read_text(self.cfg, str(link))

    def test_backup_on_overwrite_and_atomic_save(self):
        allowed = replace(self.cfg, enable_writes=True)
        self.cfg.grants_path.write_text(json.dumps({"expires_at": time.time()+60, "capabilities": ["writes"]}))
        path = self.root / "project.txt"
        path.write_text("old text", encoding="utf-8")
        result = write_text(allowed, str(path), "new text", expected_sha256=file_info(allowed, str(path))["sha256"])
        self.assertEqual(path.read_text(encoding="utf-8"), "new text")
        self.assertEqual(Path(result["backup"]).read_text(encoding="utf-8"), "old text")
        self.assertEqual(len(list(self.root.glob(".harmony-*"))), 0)

    def test_refuse_oversized_write_without_damage(self):
        allowed = replace(self.cfg, enable_writes=True, max_write_bytes=8)
        path = self.root / "project.txt"
        path.write_text("unchanged")
        with self.assertRaises(PolicyError):
            write_text(allowed, str(path), "oversized content")
        self.assertEqual(path.read_text(), "unchanged")

    def test_arbitrary_powershell_requires_opt_in(self):
        with self.assertRaises(PolicyError):
            powershell(self.cfg, 'Get-Process')

    def test_diagnostic_name_is_allowlisted(self):
        with self.assertRaises(PolicyError):
            diagnostic(self.cfg, 'not_a_command')

    def test_read_size_limit(self):
        path = self.root / "log.txt"
        path.write_text("abcdefgh")
        r = read_text(self.cfg, str(path), offset=2, max_bytes=3)
        self.assertEqual(r["text"], "cde")
        self.assertTrue(r["truncated"])

    def test_directory_listing_limit(self):
        for i in range(4):
            (self.root / f"{i}.txt").write_text("x")
        r = list_directory(self.cfg, str(self.root), limit=2)
        self.assertEqual(len(r["entries"]), 2)

    def test_load_config_policy_disabled(self):
        file = self.root / "config.json"
        file.write_text(json.dumps({"allowed_roots":[str(self.root)], "enable_shell": False}))
        cfg = load_config(file)
        self.assertFalse(cfg.enable_shell)

    def test_reject_volume_root(self):
        file = self.root / "config.json"
        file.write_text(json.dumps({"allowed_roots": [str(Path(self.root.anchor))]}))
        with self.assertRaises(PolicyError):
            load_config(file)


if __name__ == "__main__":
    unittest.main()
