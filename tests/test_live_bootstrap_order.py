"""Regression contracts for live tunnel bootstrap and repeated startup."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1]/"scripts"/"Bootstrap.ps1")

class LiveBootstrapOrderingTests(unittest.TestCase):
    def test_startup_validation_runs_before_launching_health_listener(self):
        code = SOURCE.read_text(encoding="utf-8")
        startup = code.index("Invoke-UniversalStep -Path (Join-Path $App 'scripts\\Enable-Startup.ps1')")
        supervisor = code.index("Start-UniversalSupervisor -Root $App -State $State")
        self.assertLess(startup, supervisor, "Enabling startup while the daemon is live makes doctor fail on port 8080")

    def test_existing_verified_daemon_is_reused_without_conflicting_doctor(self):
        code = SOURCE.read_text(encoding="utf-8")
        start = code.index("$SecretExists = Test-Path")
        end = code.index("Start-UniversalSupervisor -Root $App -State $State")
        body = code[start:end]
        self.assertIn("Get-VerifiedTunnelIdentity", body)
        self.assertIn("readyz", body)
        self.assertIn("Invoke-UniversalStep -Path (Join-Path $App 'scripts\\Test-Tunnel.ps1')", body)

if __name__ == "__main__":
    unittest.main()
