"""Extract actual portable ZIP into disposable Windows folder; run without Python in PATH."""
from pathlib import Path
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
NAME="UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED"
ZIP=QA/"portable-release"/(NAME+".zip")
sys.path.insert(0,str(ROOT/"tools"))
from qa_installer_e2e import restricted_env,run,verify_stdio

def main():
    assert ZIP.is_file()
    with tempfile.TemporaryDirectory(prefix="URM-ZIP-QA-") as temp:
        base=Path(temp)
        with zipfile.ZipFile(ZIP) as archive:
            assert archive.testzip() is None
            archive.extractall(base)
        path=base/NAME
        ui=path/"GUI"/"UniversalRemote-Preview.exe"
        agent=path/"Agent"/"UniversalRemoteAgent-Preview.exe"
        assert ui.is_file() and agent.is_file()
        assert (path/"scripts"/"Prepare-PowerShell.ps1").is_file()
        manifest=json.loads((path/"RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            file=path/entry["path"]
            assert file.is_file()
            assert hashlib.sha256(file.read_bytes()).hexdigest()==entry["sha256"],entry["path"]
        data=base/"private-user"
        data.mkdir()
        env=restricted_env(data)
        no_config=run("PORTABLE_DENY_UNCONFIGURED",[str(agent),"--version"],env,limit=60)
        assert no_config.returncode==12,no_config.stderr[-400:]
        gui=run("PORTABLE_GUI",[str(ui),"--self-test"],env,limit=120)
        assert gui.returncode==0,gui.stderr[-400:]
        sys.path.insert(0,str(ROOT))
        from unittest.mock import patch
        from public_paths import write_initial_config
        with patch.dict(os.environ,{"LOCALAPPDATA":str(data)}):
            write_initial_config(data/"work")
        count=asyncio.run(verify_stdio(agent,env))
        assert count==27,count
        assert not (data/"HarmonyRemoteMCP").exists()
    print("PORTABLE_ZIP_E2E_PASS",json.dumps(
        {"sha256":hashlib.sha256(ZIP.read_bytes()).hexdigest(),
         "files_verified":len(manifest["files"]),
         "mcp_tools":count,"python_on_path":False}),flush=True)

if __name__=="__main__":main()
