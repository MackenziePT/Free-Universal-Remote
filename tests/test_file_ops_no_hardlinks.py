"""Windows approved-file operations must work without os.link privileges."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from remote_core import Config
from native_files import copy_file, move_file

@unittest.skipUnless(os.name == "nt", "Windows NTFS behavior")
class FileOperationsWithoutHardlinks(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="urm-exclusive-")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.cfg = Config(allowed_roots=(self.root.resolve(),),
                          enable_writes=True,
                          backup_root=self.root/"backups",
                          grants_path=self.root/"grants.json")
        import json
        import time
        (self.root/"grants.json").write_text(json.dumps({
            "expires_at": int(time.time())+120,
            "capabilities": ["writes"]
        }), encoding="utf-8")

    def test_copy_does_not_use_hardlinks(self):
        original = self.root / "origin.txt"
        new = self.root / "copy.txt"
        original.write_text("content", encoding="utf-8")
        with patch("native_files.os.link", side_effect=PermissionError(5, "NTFS hardlink blocked")):
            copy_file(self.cfg, str(original), str(new))
        self.assertEqual(new.read_text(encoding="utf-8"), "content")

    def test_move_does_not_use_hardlinks(self):
        original = self.root / "origin.txt"
        new = self.root / "new.txt"
        original.write_text("content", encoding="utf-8")
        with patch("native_files.os.link", side_effect=PermissionError(5, "NTFS hardlink blocked")):
            move_file(self.cfg, str(original), str(new))
        self.assertFalse(original.exists())
        self.assertEqual(new.read_text(encoding="utf-8"), "content")
