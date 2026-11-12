"""Static contract checks for Windows-only tunnel supervisor.

These do not replace an actual PowerShell + tunnel-client integration test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TunnelSupervisorContract(unittest.TestCase):
    def test_abandoned_mutex_is_recovered(self):
        script=(ROOT/'scripts'/'Start-Tunnel.ps1').read_text(encoding='utf-8')
        self.assertIn('AbandonedMutexException', script)
        self.assertIn('$Locked = $true', script)

    def test_retry_interval_is_bounded_and_increases(self):
        script=(ROOT/'scripts'/'Start-Tunnel.ps1').read_text(encoding='utf-8')
        self.assertIn('Math]::Min', script)
        self.assertIn('$RetrySeconds', script)
        self.assertIn('Start-Sleep -Seconds $RetrySeconds', script)

    def test_tunnel_credential_is_wiped_before_return(self):
        script=(ROOT/'scripts'/'Start-Tunnel.ps1').read_text(encoding='utf-8')
        self.assertIn('Remove-Item Env:\\CONTROL_PLANE_API_KEY',script)
        self.assertIn('finally',script)

if __name__=='__main__': unittest.main()
