"""Regression: Windows installer must never partially move a live venv."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
class AtomicInstallerContracts(unittest.TestCase):
    def test_rename_uses_directory_move_and_retries(self):
        s=(R/'scripts'/'Install.ps1').read_text()
        self.assertIn('[IO.Directory]::Move($From, $To)',s)
        self.assertIn('for ($Attempt = 1; $Attempt -le 8; $Attempt++)',s)
        self.assertNotIn('Move-Item -LiteralPath $Stage -Destination $Destination',s)
    def test_native_powershell_utility_module_loaded_when_absent(self):
        s=(R/'scripts'/'Tunnel-Client.ps1').read_text()
        self.assertIn('Get-Command Get-FileHash',s)
        self.assertIn('Import-Module Microsoft.PowerShell.Utility -RequiredVersion 3.1.0.0',s)
