"""Cross-platform checks for packaging and installer invariants.

This is a source-contract check, NOT proof the PowerShell scripts run on Windows.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReleaseContractTests(unittest.TestCase):
    def test_staged_install_and_restoration_routes(self):
        script = (ROOT/'scripts'/'Install.ps1').read_text(encoding='utf-8')
        for required in ('app.stage.', 'app.previous.', 'smoke_test.py', 'Move-AtomicDirectory',
                         'Prepare-Stage.ps1', 'desktop_unicode.py', 'operation_journal.py'):
            self.assertIn(required, script)
        self.assertLess(script.index("'smoke_test.py'"), script.index("Move-AtomicDirectory -From $Stage -To $Destination"))

    def test_rc47_installer_copies_consent_controls_and_release_evidence(self):
        script = (ROOT/'scripts'/'Install.ps1').read_text(encoding='utf-8')
        for name in ('AUTORIZAR-MCP-60MIN.cmd', 'REVOGAR-MCP.cmd',
                     'RC4_7_VERIFICATION.md'):
            self.assertIn("'"+name+"'", script)
        self.assertTrue((ROOT/'AUTORIZAR-MCP-60MIN.cmd').is_file())
        self.assertTrue((ROOT/'REVOGAR-MCP.cmd').is_file())

    def test_rc48_release_installs_listener_ownership_regressions(self):
        install = (ROOT/'scripts'/'Install.ps1').read_text(encoding='utf-8')
        self.assertIn("'RC4_8_VERIFICATION.md'", install)
        self.assertTrue((ROOT/'tests'/'Test-LiveListenerOwnership.ps1').is_file())
        self.assertTrue((ROOT/'tests'/'Test-ListenerOwnership.ps1').is_file())
        test_tunnel = (ROOT/'scripts'/'Test-Tunnel.ps1').read_text(encoding='utf-8')
        self.assertIn('Assert-OwnedHealthListener -Owner $LiveOwner', test_tunnel)
        live_suite = (ROOT/'scripts'/'Verify-LiveTunnel.ps1').read_text(encoding='utf-8')
        self.assertIn('Test-LiveListenerOwnership.ps1', live_suite)

    def test_autostart_uses_process_scoped_policy_not_system_registry_change(self):
        script = (ROOT/'scripts'/'Enable-Startup.ps1').read_text(encoding='utf-8')
        self.assertIn('-ExecutionPolicy Bypass', script)
        self.assertNotIn('Set-ExecutionPolicy', script)

    def test_release_has_stop_revoke_uninstall_and_windows_acceptance(self):
        for name in ('Stop-Tunnel.ps1','Revoke-Session.ps1','Uninstall.ps1','Verify-Windows.ps1'):
            self.assertTrue((ROOT/'scripts'/name).exists(),name)
        self.assertIn('ShouldProcess', (ROOT/'scripts'/'Uninstall.ps1').read_text())

if __name__=='__main__': unittest.main()
