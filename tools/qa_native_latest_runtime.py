"""Real Windows native version info, selecting newest private runtime in QA profile."""
from pathlib import Path
import os
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from remote_core import _windows_executable_version,_powershell

global_path=Path(os.environ.get("ProgramFiles",r"C:\Program Files"))/"PowerShell"/"7"/"pwsh.exe"
private_root=ROOT/"evidence"/"qa"/"pwsh-first-run-sandbox"
private=private_root/"UniversalRemote"/"runtime"/"powershell"/"7.7.0-x64"/"pwsh.exe"
print("GLOBAL",_windows_executable_version(global_path))
print("PRIVATE",_windows_executable_version(private))
assert private.exists()
assert _windows_executable_version(private)==(7,7,0)
with patch.dict(os.environ,{"LOCALAPPDATA":str(private_root)}):
    result=_powershell("Write-Output 'UNIVERSAL_REMOTE_LATEST_ENGINE_CONFIRMED'",20)
print("ENGINE_EXIT",result["exit_code"],"ACTUAL_TIMEOUT",result.get("timed_out"))
print("ENGINE_OUTPUT",result.get("stdout","")[:180])
assert result["exit_code"]==0
assert "UNIVERSAL_REMOTE_LATEST_ENGINE_CONFIRMED" in result.get("stdout","")
print("NATIVE_POWERSHELL_LATEST_SELECTION_PASS")
