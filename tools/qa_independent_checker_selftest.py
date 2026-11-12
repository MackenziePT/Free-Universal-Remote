"""Validate the future independent-PC checker against disposable frozen binaries.

On developer ASUS only; this proves the checker, NOT a second-PC acceptance.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
DIST=QA/"public-portable-prototype"
INSTALLER=QA/"installer-build"/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"
SCRIPT=ROOT/"tools"/"Check-Independent-Windows-PC.ps1"
SOURCE={
    "GUI":"UniversalRemote-Preview",
    "Agent":"UniversalRemoteAgent-Preview",
    "Updater":"UniversalRemoteUpdater-Preview",
}
with tempfile.TemporaryDirectory(prefix="urm-independent-check-") as temporary:
    destination=Path(temporary)/"Installed"
    for name,bundle in SOURCE.items():
        folder=DIST/bundle
        for item in folder.rglob("*"):
            if not item.is_file():
                continue
            target=destination/name/item.relative_to(folder)
            target.parent.mkdir(parents=True,exist_ok=True)
            try:
                os.link(item,target)
            except OSError:
                shutil.copy2(item,target)
    with INSTALLER.open("rb") as f:
        digest=hashlib.file_digest(f,"sha256").hexdigest()
    args=["pwsh.exe","-NoProfile","-File",str(SCRIPT),"-Installer",str(INSTALLER),
          "-ExpectedSHA256",digest,"-InstallDir",str(destination)]
    completed=subprocess.run(args,capture_output=True,text=True,errors="replace",timeout=130)
    result=json.loads((ROOT/"tools"/"Independent-PC-QA-Result.json").read_text(encoding="utf-8-sig"))
    print("TEST_CHECKER_EXIT",completed.returncode,flush=True)
    print("CHECKER_RESULT",json.dumps({
      k:result[k] for k in ("InstallerAuthenticode","ExpectedHashMatches",
                            "AgentHealth","GUIHealth","UpdaterHelp")},indent=2),flush=True)
    assert completed.returncode==0,(completed.stderr[-1200:],result)
    assert result["ExpectedHashMatches"] is True
    assert all(result[name]=="PASS" for name in ("AgentHealth","GUIHealth","UpdaterHelp"))
print("INDEPENDENT_CHECKER_LOCAL_SELFTEST_PASS")
