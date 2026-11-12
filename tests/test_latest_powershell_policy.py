"""Latest stable PowerShell is resolved at installation time, never pinned to v7."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
RESOLVER=ROOT/"scripts"/"Resolve-PowerShell.ps1"


class LatestPowerShellPolicyTests(unittest.TestCase):
    @unittest.skipUnless(os.name=="nt","Windows PowerShell bootstrap")
    def test_future_stable_major_version_preserves_newer_existing(self):
        ps=shutil.which("powershell.exe")
        self.assertIsNotNone(ps)
        quoted=str(RESOLVER).replace("'","''")
        command=r'''
$ErrorActionPreference='Stop'
. '{resolver}'
$script:Requested=0
function Invoke-RestMethod {{
    param($Uri,$Headers,$TimeoutSec,$ErrorAction)
    if ($Uri -ne 'https://api.github.com/repos/PowerShell/PowerShell/releases/latest') {{
        throw 'Wrong endpoint'
    }}
    $script:Requested++
    return [pscustomobject]@{{
        tag_name='v8.1.0'
        prerelease=$false
        draft=$false
        assets=@([pscustomobject]@{{
            name='PowerShell-8.1.0-win-x64.zip'
            digest='sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            browser_download_url='https://github.com/PowerShell/PowerShell/releases/download/v8.1.0/PowerShell-8.1.0-win-x64.zip'
        }})
    }}
}}
function Get-UniversalPwshVersion {{
    param([string]$Executable)
    if ($Executable -eq 'C:\Mock\pwsh.exe') {{return [version]'8.1.1'}}
    return $null
}}
function Invoke-WebRequest {{ throw 'Downloading a downgrade is forbidden' }}
$answer = Install-UniversalPortablePowerShell -MinimumVersion ([version]'7.4.0') -ExistingPath 'C:\Mock\pwsh.exe'
if ($answer -ne 'C:\Mock\pwsh.exe') {{ throw ('Did not preserve higher version: '+$answer) }}
if ($script:Requested -ne 1) {{throw 'Must query latest once at runtime'}}
Write-Output 'FUTURE_MAJOR_NO_DOWNGRADE_PASS'
'''.replace("{resolver}",quoted).replace("{{","{").replace("}}","}")
        result=subprocess.run([ps,"-NoLogo","-NoProfile","-ExecutionPolicy","Bypass",
                               "-Command",command],capture_output=True,text=True,timeout=35)
        self.assertEqual(result.returncode,0,result.stderr+"\n"+result.stdout)
        self.assertIn("FUTURE_MAJOR_NO_DOWNGRADE_PASS",result.stdout)

    def test_installer_uses_live_official_stable_release_not_fixed_major(self):
        script=RESOLVER.read_text(encoding="utf-8")
        self.assertIn("/PowerShell/PowerShell/releases/latest",script)
        self.assertIn("Install-UniversalPortablePowerShell -MinimumVersion $MinimumVersion -ExistingPath $BestPath",script)
        self.assertIn("if ($CurrentVersion -ge $Version)",script)
        self.assertIn(r"^v(\d+\.\d+\.\d+)$",script)
        self.assertNotIn(r"^v(7\.\d+\.\d+)$",script)

    def test_execution_uses_newer_private_runtime_over_old_global(self):
        import tempfile
        from unittest.mock import patch
        import remote_core
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            global_shell=home/"global"/"pwsh.exe"
            global_shell.parent.mkdir()
            global_shell.write_bytes(b"fake global")
            updated=home/"UniversalRemote"/"runtime"/"powershell"/"8.0.0-x64"/"pwsh.exe"
            updated.parent.mkdir(parents=True)
            updated.write_bytes(b"fake verified private")
            def version(p):
                return (7,7,0) if str(p)==str(global_shell) else None
            with patch.dict(os.environ,{"LOCALAPPDATA":folder}), \
                 patch("remote_core.shutil.which",return_value=str(global_shell)), \
                 patch("remote_core._windows_executable_version",side_effect=version), \
                 patch("remote_core.run_limited_process",return_value={"exit_code":0}) as execution:
                remote_core._powershell("Get-Date",5)
                self.assertEqual(execution.call_args.args[0][0],str(updated))

    def test_execution_does_not_downgrade_when_global_is_newer(self):
        import tempfile
        from unittest.mock import patch
        import remote_core
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            global_shell=home/"global"/"pwsh.exe"
            global_shell.parent.mkdir()
            global_shell.write_bytes(b"fake newer global")
            private=home/"UniversalRemote"/"runtime"/"powershell"/"7.7.0-x64"/"pwsh.exe"
            private.parent.mkdir(parents=True)
            private.write_bytes(b"fake older private")
            with patch.dict(os.environ,{"LOCALAPPDATA":folder}), \
                 patch("remote_core.shutil.which",return_value=str(global_shell)), \
                 patch("remote_core._windows_executable_version",return_value=(8,0,0)), \
                 patch("remote_core.run_limited_process",return_value={"exit_code":0}) as execution:
                remote_core._powershell("Get-Date",5)
                self.assertEqual(execution.call_args.args[0][0],str(global_shell))

    def test_programfiles_future_major_without_path_is_discovered(self):
        import tempfile
        from unittest.mock import patch
        import remote_core
        with tempfile.TemporaryDirectory() as temp:
            install=Path(temp)/"Programs"/"PowerShell"/"8"
            install.mkdir(parents=True)
            shell=install/"pwsh.exe"
            shell.write_bytes(b"test fake")
            with patch.dict(os.environ,{"ProgramFiles":str(Path(temp)/"Programs"),"LOCALAPPDATA":temp}), \
                 patch("remote_core.shutil.which",return_value=None), \
                 patch("remote_core._windows_executable_version",return_value=(8,0,0)), \
                 patch("remote_core.run_limited_process",return_value={"exit_code":0}) as execution:
                remote_core._powershell("Get-Date",5)
                self.assertEqual(execution.call_args.args[0][0],str(shell))

    def test_preflight_recognizes_future_major_in_programfiles(self):
        import tempfile
        from unittest.mock import patch
        from dependency_preflight import powershell_check
        with tempfile.TemporaryDirectory() as temp:
            shell=Path(temp)/"Programs"/"PowerShell"/"8"/"pwsh.exe"
            shell.parent.mkdir(parents=True)
            shell.write_bytes(b"test fake")
            environment={"ProgramFiles":str(Path(temp)/"Programs"),"LOCALAPPDATA":temp,
                         "PATH":str(Path(temp)/"unknown")}
            with patch.dict(os.environ,environment):
                self.assertTrue(powershell_check().ok)

    def test_gui_does_not_download_optional_powershell_by_default(self):
        ui=(ROOT/"public_gui.py").read_text(encoding="utf-8")
        self.assertIn("self.prepare_powershell=tk.BooleanVar(value=False)",ui)
        # Optional runtime must not be downloaded automatically by the short wizard.
        self.assertNotIn("verificar e atualizar automaticamente o powershell após a configuração",ui.lower())
        panel=(ROOT/"universal_remote_ui.py").read_text(encoding="utf-8")
        self.assertIn("Verificar ou atualizar PowerShell",panel)
        self.assertNotIn("Obter ou atualizar PowerShell 7",panel)

if __name__=="__main__":
    unittest.main()
