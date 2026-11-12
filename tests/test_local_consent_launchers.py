"""Verify CMD consent helpers against synthetic scripts, never the real Windows grants."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == 'nt', 'Windows cmd.exe required')
class LocalConsentLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='urm-consent-probe-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scripts = self.root / 'HarmonyRemoteMCP' / 'app' / 'scripts'
        self.scripts.mkdir(parents=True)
        self.env = os.environ.copy()
        self.env['LOCALAPPDATA'] = str(self.root)
        self.release = Path(__file__).resolve().parents[1]

    def execute(self, filename):
        result = subprocess.run(
            ['cmd.exe', '/d', '/c', str(self.release / filename)],
            input='\n', capture_output=True, text=True,
            encoding='utf-8', errors='replace', env=self.env, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / 'HarmonyRemoteMCP' / 'grants.json').exists())
        return result.stdout

    def test_authorization_launcher_forwards_four_capabilities_and_sixty_minutes(self):
        (self.scripts / 'Grant-Session.ps1').write_text(
            "param([string[]]$Capabilities,[int]$Minutes)\n"
            "Write-Output ('CAPS=' + ($Capabilities -join '|'))\n"
            "Write-Output ('MINUTES=' + $Minutes)\n", encoding='utf-8')
        output = self.execute('AUTORIZAR-MCP-60MIN.cmd')
        self.assertIn('CAPS=writes|shell|screen|input', output)
        self.assertIn('MINUTES=60', output)

    def test_revocation_launcher_calls_expected_local_script(self):
        (self.scripts / 'Revoke-Session.ps1').write_text(
            "Write-Output 'SYNTHETIC_REVOKE_CALLED'\n", encoding='utf-8')
        output = self.execute('REVOGAR-MCP.cmd')
        self.assertIn('SYNTHETIC_REVOKE_CALLED', output)


if __name__ == '__main__':
    unittest.main()
