"""Contract for Windows-only local tunnel doctor (static, not a Windows run)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TunnelDiagnosticTests(unittest.TestCase):
    def test_tunnel_doctor_is_available_without_exposing_runtime_key(self):
        script = ROOT/'scripts'/'Test-Tunnel.ps1'
        self.assertTrue(script.is_file())
        code = script.read_text(encoding='utf-8')
        self.assertIn(". (Join-Path $PSScriptRoot 'Secret-Storage.ps1')", code)
        self.assertIn('Read-UniversalStoredSecret -Path $Secret', code)
        reader = (ROOT/'scripts'/'Secret-Storage.ps1').read_text(encoding='utf-8')
        self.assertIn('ConvertTo-SecureString -String $Cipher', reader)
        self.assertIn('Invalid DPAPI ciphertext format', reader)
        self.assertIn('doctor --profile-file $ProfileFile --explain',code)
        self.assertIn(".config\\tunnel-client\\harmony-remote.yaml",code)
        self.assertIn('ZeroFreeBSTR',code)
        self.assertIn('Remove-Item Env:\\CONTROL_PLANE_API_KEY',code)
        self.assertIn('if ($LASTEXITCODE -ne 0)',code)
        self.assertNotIn('Write-Host $env:CONTROL_PLANE_API_KEY',code)

if __name__ == '__main__':unittest.main()
