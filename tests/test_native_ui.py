"""Local UI policy helpers, no real user grants or window automation."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from remote_core import Config


class UIPolicyTests(unittest.TestCase):
    def test_confirmed_local_grant_and_immediate_revoke_on_disposable_state(self):
        import universal_remote_ui as ui
        with tempfile.TemporaryDirectory(prefix="urm-ui-policy-") as root:
            state = Path(root)
            cfg = Config(allowed_roots=(state,), enable_writes=True,
                         enable_shell=True, enable_screen=True, enable_input=True,
                         grants_path=state / "grants.json")
            with patch.object(ui, "STATE", state):
                scopes, expiry = ui.grant_local(cfg, ["writes", "shell"], 15)
                self.assertEqual(scopes, ["shell", "writes"])
                self.assertGreater(expiry, 0)
                data = json.loads((state / "grants.json").read_text())
                self.assertEqual(data["capabilities"], ["shell", "writes"])
                ui.revoke_local()
                self.assertFalse((state / "grants.json").exists())

    def test_ui_rejects_unconfigured_privilege_and_arbitrary_duration(self):
        import universal_remote_ui as ui
        with tempfile.TemporaryDirectory(prefix="urm-ui-policy-") as root:
            state = Path(root)
            cfg = Config(allowed_roots=(state,), enable_writes=True,
                         grants_path=state / "grants.json")
            with patch.object(ui, "STATE", state):
                with self.assertRaises(ValueError):
                    ui.grant_local(cfg, ["shell"], 15)
                with self.assertRaises(ValueError):
                    ui.grant_local(cfg, ["writes"], 999999)
                self.assertFalse((state / "grants.json").exists())

    def test_launch_module_is_import_safe_without_creating_tk_window(self):
        import universal_remote_ui as ui
        self.assertTrue(callable(ui.main))
        self.assertEqual(ui.PRODUCT_VERSION, "1.0.0-rc5.1-dev")


if __name__ == "__main__":
    unittest.main()
