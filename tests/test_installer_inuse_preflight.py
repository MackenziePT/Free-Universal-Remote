"""Installer updates must fail before writing when Universal Remote still runs."""
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "packaging" / "UniversalRemote-Preview.iss"


class InstallerInUseGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SOURCE.read_text(encoding="utf-8-sig")

    def test_preflight_blocks_running_processes_before_installation(self):
        self.assertIn("function PrepareToInstall(var NeedsRestart: Boolean): String;", self.script)
        self.assertIn("Win32_Process", self.script)
        self.assertIn("CreateOleObject('WbemScripting.SWbemLocator')", self.script)
        self.assertIn("SetOfProcesses.Count > 0", self.script)
        for exe in ("UniversalRemote-Preview.exe",
                    "UniversalRemoteAgent-Preview.exe",
                    "UniversalRemoteBridge-Preview.exe",
                    "UniversalRemoteTunnel-Preview.exe",
                    "UniversalRemoteUpdater-Preview.exe"):
            with self.subTest(exe=exe):
                self.assertIn('Name="' + exe + '"', self.script)

    def test_user_facing_english_and_portuguese_messages(self):
        self.assertIn("portuguese.URProcessesMustClose=", self.script)
        self.assertIn("english.URProcessesMustClose=", self.script)
        self.assertIn("portuguese.URProcessCheckFailed=", self.script)
        self.assertIn("english.URProcessCheckFailed=", self.script)

    def test_no_forced_close_or_unexpected_reboot(self):
        self.assertIn("CloseApplications=yes", self.script)
        self.assertIn("RestartApplications=no", self.script)
        self.assertNotIn("CloseApplications=force", self.script)
        self.assertNotIn("restartreplace", self.script)


if __name__ == "__main__":
    unittest.main()
