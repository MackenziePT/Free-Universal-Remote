"""Guard Windows PowerShell 5.1 against a PSModulePath containing PS7 modules."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]

class SecurityModulePreloadContracts(unittest.TestCase):
    def test_preload_is_shared_and_version_pinned_for_windows_ps_51(self):
        helper = (ROOT/'scripts'/'PowerShell-Security.ps1').read_text(encoding='utf8')
        self.assertIn("Microsoft.PowerShell.Security -RequiredVersion 3.0.0.0", helper)
        self.assertIn('ConvertTo-SecureString', helper)
        self.assertIn("PSEdition -eq 'Desktop'", helper)

    def test_each_credential_entry_point_preloads_security_module(self):
        for name in ('Initialize-Tunnel.ps1', 'Test-Tunnel.ps1', 'Start-Tunnel.ps1'):
            with self.subTest(script=name):
                source = (ROOT/'scripts'/name).read_text(encoding='utf8')
                self.assertIn("'PowerShell-Security.ps1'", source)
