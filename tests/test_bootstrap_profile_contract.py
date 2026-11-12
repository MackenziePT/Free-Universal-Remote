"""Prevent repeated key prompts and unsafe profile conflicts during restarts."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]

class BootstrapProfileContracts(unittest.TestCase):
    def test_profiles_are_discovered_without_console_input(self):
        s = (ROOT/'scripts'/'Bootstrap.ps1').read_text(encoding='utf-8')
        self.assertIn('Get-UniversalExistingTunnelId', s)
        self.assertIn('harmony-remote.yaml', s)
        self.assertIn('$EffectiveTunnelId', s)

    def test_existing_credential_not_reentered_when_id_supplied(self):
        s = (ROOT/'scripts'/'Bootstrap.ps1').read_text(encoding='utf-8')
        self.assertNotIn('if ($TunnelId -or -not (Test-Path -LiteralPath $Secret', s)
        self.assertIn('if (-not $SecretExists)', s)

    def test_release_installer_checks_manifest_before_staging(self):
        s = (ROOT/'scripts'/'Install.ps1').read_text(encoding='utf-8')
        self.assertIn('verify_release.py', s)
        self.assertLess(s.index('verify_release.py'), s.index('New-Item -ItemType Directory -Force -Path $Stage'))
