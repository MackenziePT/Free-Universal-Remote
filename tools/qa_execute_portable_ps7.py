"""Use real verified portable PowerShell 7 without shell PATH and without global changes."""
from pathlib import Path
import os
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import remote_core
HOME=ROOT/"evidence"/"qa"/"pwsh-first-run-sandbox"
PWSH=HOME/"UniversalRemote"/"runtime"/"powershell"/"7.7.0-x64"/"pwsh.exe"
assert PWSH.is_file(),PWSH
with patch.dict(os.environ,{"LOCALAPPDATA":str(HOME)}), \
     patch("remote_core.shutil.which",return_value=None):
    result=remote_core._powershell("Write-Output 'URM_SIGNED_PS7_RUNTIME_PASS'",30)
assert result["exit_code"]==0,result
assert "URM_SIGNED_PS7_RUNTIME_PASS" in result["stdout"],result
print("PRIVATE_SIGNED_PS7_EXECUTION_PASS",PWSH.name,result["timed_out"])
