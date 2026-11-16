"""Release-preparation contracts: no dependency on this developer PC."""
from pathlib import Path
import os
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts"

class PublicReadinessTests(unittest.TestCase):
    @unittest.skipUnless(os.name=="nt","Windows bootstrap")
    def test_modern_powershell_discovery_precedes_legacy(self):
        script=SCRIPTS/"Resolve-PowerShell.ps1"
        self.assertTrue(script.is_file(),"Need explicit PowerShell host resolver")
        host=shutil.which("powershell.exe")
        self.assertIsNotNone(host)
        invoke=f". '{str(script).replace(chr(39), chr(39)*2)}'; Resolve-UniversalPowerShell -NoDownload"
        result=subprocess.run([host,"-NoLogo","-NoProfile","-ExecutionPolicy","Bypass",
                               "-Command",invoke],capture_output=True,text=True,timeout=75)
        self.assertEqual(result.returncode,0,result.stderr)
        actual=Path(result.stdout.strip().splitlines()[-1])
        self.assertTrue(actual.exists(),result.stdout)
        # Windows 11 developer machine has PS7; installation must not choose v5.1.
        if shutil.which("pwsh.exe"):
            self.assertEqual(actual.name.casefold(),"pwsh.exe")

    def test_public_launcher_does_not_force_windows_powershell(self):
        cmd=(ROOT/"INICIAR.cmd").read_text(encoding="utf-8-sig").lower()
        self.assertIn("resolve-powershell.ps1",cmd)
        self.assertNotIn(r"system32\windowspowershell\v1.0\powershell.exe",cmd)

    def test_gui_does_not_offer_authorization_longer_than_policy_allows(self):
        import universal_remote_ui as ui
        from remote_core import Config
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            state=Path(d)
            policy=Config(allowed_roots=(state,), grants_path=state/"grants.json",
                          enable_writes=True)
            with self.assertRaises(ValueError):
                ui.grant_local(policy,["writes"],480)
        source=(ROOT/"universal_remote_ui.py").read_text(encoding="utf-8")
        self.assertNotIn('self._grant(480)',source)

    def test_mcp_shell_uses_private_pwsh_when_not_in_path(self):
        import tempfile
        from unittest.mock import patch
        import remote_core
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"UniversalRemote"/"runtime"/"powershell"/"7.6.9-x64"
            path.mkdir(parents=True)
            shell=path/"pwsh.exe"
            shell.write_bytes(b"placeholder")
            with patch.dict(os.environ,{"LOCALAPPDATA":tmp, "ProgramFiles":str(Path(tmp)/"no-global-pwsh")}), \
                 patch.object(remote_core.os,"name","nt"), \
                 patch("remote_core.shutil.which", side_effect=lambda k: None if k=="pwsh.exe" else "powershell.exe"), \
                 patch("remote_core.run_limited_process",return_value={"exit_code":0}) as run:
                remote_core._powershell("Write-Output test",5)
                self.assertEqual(run.call_args.args[0][0],str(shell))

    def test_health_check_bypasses_proxy_and_uses_loopback_only(self):
        from unittest.mock import patch
        import universal_remote_ui as ui
        with patch("universal_remote_ui.HTTPConnection") as constructor:
            connection=constructor.return_value
            answer=connection.getresponse.return_value
            answer.status=200
            answer.read.return_value=b"ready"
            self.assertTrue(ui.read_status())
            constructor.assert_called_once_with("127.0.0.1",8080,timeout=0.6)
            connection.request.assert_called_once_with("GET","/readyz")
            connection.close.assert_called_once()

    def test_health_check_handles_malformed_http_response(self):
        from http.client import BadStatusLine
        from unittest.mock import patch
        import universal_remote_ui as ui
        with patch("universal_remote_ui.HTTPConnection") as constructor:
            constructor.return_value.getresponse.side_effect=BadStatusLine("broken response")
            self.assertFalse(ui.read_status())
            constructor.return_value.close.assert_called_once()

    def test_legacy_bootstrap_verifies_microsoft_authenticode_signer(self):
        source=(ROOT/"scripts"/"Resolve-PowerShell.ps1").read_text(encoding="utf-8")
        self.assertIn("Import-Module Microsoft.PowerShell.Security -RequiredVersion 3.0.0.0", source)
        self.assertIn("Get-AuthenticodeSignature", source)
        self.assertIn("O=Microsoft Corporation", source)

    def test_pillow_pin_addresses_known_2026_advisories(self):
        requirements=(ROOT/"requirements.txt").read_text(encoding="utf-8")
        self.assertIn("Pillow==13.0.0",requirements)

    def test_candidate_version_is_not_a_published_release(self):
        import universal_remote_ui as ui
        self.assertEqual(ui.PRODUCT_VERSION, "1.0.0-rc5.1-dev")
        source=(ROOT/"server.py").read_text(encoding="utf-8")
        self.assertIn('"version": "1.0.0-rc5.1-dev"',source)

    def test_public_release_gates_document_exists(self):
        document=ROOT/"docs"/"PUBLIC_RELEASE_GATES.md"
        self.assertTrue(document.is_file(),"Public release gates must be explicit")
        text=document.read_text(encoding="utf-8").lower()
        for word in ("signing","sbom","windows","installer","rollback","privacy"):
            self.assertIn(word,text)

if __name__=="__main__":
    unittest.main()
