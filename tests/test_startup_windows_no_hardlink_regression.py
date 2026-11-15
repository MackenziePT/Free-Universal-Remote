"""A Windows first-run config must not rely on NTFS hardlink privileges."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from public_paths import write_initial_config

@unittest.skipUnless(os.name == "nt", "Windows-only no-hardlink regression")
class WindowsFirstRunTests(unittest.TestCase):
    def test_first_run_succeeds_when_ntfs_hardlinks_are_denied(self):
        with tempfile.TemporaryDirectory(prefix="urm-hardlink-denied-") as raw:
            root = Path(raw)
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root)}):
                with patch("public_paths.os.link", side_effect=PermissionError(5, "hardlink denied")):
                    created = write_initial_config(root / "approved")
                self.assertTrue(created.is_file())
                record = json.loads(created.read_text(encoding="utf-8"))
                self.assertTrue(all(not record["enable_"+n] for n in ("writes","shell","screen","input")))
                self.assertEqual(len(record["allowed_roots"]), 1)
