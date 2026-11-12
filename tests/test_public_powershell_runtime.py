"""Public PowerShell capability remains user-scoped and explicitly initiated."""
from __future__ import annotations
from pathlib import Path
import os
import subprocess
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

class PortableShellTests(unittest.TestCase):
    def test_resolver_uses_public_product_directory_not_developer_instance(self):
        text=(ROOT/"scripts"/"Resolve-PowerShell.ps1").read_text(encoding="utf-8")
        self.assertIn(r"UniversalRemote\runtime\powershell",text)
        self.assertNotIn(r"HarmonyRemoteMCP\runtime\powershell",text)
        self.assertIn("[switch]$PreferLatest",text)

    def test_wrapper_explicitly_requests_latest_signed_runtime(self):
        text=(ROOT/"scripts"/"Prepare-PowerShell.ps1").read_text(encoding="utf-8")
        self.assertIn("Resolve-UniversalPowerShell -PreferLatest",text)

    def test_bundled_gui_has_local_ps7_prepare_action(self):
        import universal_remote_ui as ui
        self.assertTrue(callable(ui.install_private_powershell))
        self.assertTrue(callable(ui.get_private_powershell_setup_path))

    def test_core_prefers_public_private_runtime(self):
        from tempfile import TemporaryDirectory
        import remote_core
        with TemporaryDirectory() as temporary:
            folder=Path(temporary)/"UniversalRemote"/"runtime"/"powershell"/"7.7.0-x64"
            folder.mkdir(parents=True)
            exe=folder/"pwsh.exe"
            exe.write_bytes(b"test only")
            with patch.dict(os.environ,{"LOCALAPPDATA":temporary}), \
                 patch("remote_core.shutil.which",return_value=None), \
                 patch("remote_core.run_limited_process",return_value={"exit_code":0}) as mocked:
                remote_core._powershell("Get-Date",5)
                self.assertEqual(mocked.call_args.args[0][0],str(exe))

if __name__=="__main__":unittest.main()
