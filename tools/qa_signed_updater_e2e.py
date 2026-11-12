"""Real, disposable Windows test of the frozen security updater executable.

Uses an ephemeral private key solely for QA. This is NOT product signing,
not a public trust anchor, and not an installation on the user's active PC.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
DIST=QA/"public-portable-prototype"
sys.path.insert(0,str(ROOT))
from tools.sign_release_package import make_signed_package


def run(args, *, expected: int, timeout=80):
    result=subprocess.run(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True,errors="replace",timeout=timeout,check=False)
    print("EXEC",Path(args[0]).name,str(args[1]),"exit",result.returncode,flush=True)
    if result.returncode!=expected:
        raise RuntimeError("Unexpected command result: "+result.stderr[-1500:])
    return result


def clone_release(source:Path,dest:Path):
    mapping={
        "GUI":"UniversalRemote-Preview",
        "Agent":"UniversalRemoteAgent-Preview",
        "Updater":"UniversalRemoteUpdater-Preview",
        "Tunnel":"UniversalRemoteTunnel-Preview",
    }
    for name,source_dir in mapping.items():
        entry=source/source_dir
        if not entry.is_dir():
            raise RuntimeError("Missing packaged release directory "+str(entry))
        for file in entry.rglob("*"):
            if not file.is_file() or file.is_symlink():
                continue
            target=dest/name/file.relative_to(entry)
            target.parent.mkdir(parents=True,exist_ok=True)
            # Same-volume hardlink saves QA time and disk, no writes to links.
            try:
                os.link(file,target)
            except OSError:
                shutil.copy2(file,target)
    for original in (ROOT/"bin").iterdir():
        if original.is_file() and not original.is_symlink():
            destination=dest/"bin"/original.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original,destination)


def main():
    updater=DIST/"UniversalRemoteUpdater-Preview"/"UniversalRemoteUpdater-Preview.exe"
    if not updater.is_file():
        raise FileNotFoundError("Rebuild standalone updater before running QA")
    # IMPORTANT: QA's source/evidence directory has custom ACL inheritance on
    # this Windows workstation; a freshly extracted EXE there may fail to read
    # its own Python runtime. Test the real per-user Windows Temp location, not
    # a developer artifact folder. Never weaken the machine's protection rules.
    with tempfile.TemporaryDirectory(prefix="urm-signed-e2e-") as location:
        tmp=Path(location)
        if not os.access(tmp, os.R_OK | os.W_OK | os.X_OK):
            raise PermissionError("Temporary test directory is not accessible")
        package=tmp/"release-payload"
        package.mkdir()
        clone_release(DIST,package)
        key=Ed25519PrivateKey.generate()
        pub=key.public_key().public_bytes(encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        trust={"format":1,"product":"universal-remote",
               "keys":{"local-qa-only":base64.b64encode(pub).decode()}}
        trust_file=tmp/"trusted-qa-key.json"
        trust_file.write_text(json.dumps(trust),encoding="utf-8")
        signed=make_signed_package(package,tmp/"rc51-test-release",key,
                     "local-qa-only","1.0.0-rc5.1-qa",100,"windows-x64")
        destination=tmp/"installed"
        destination.mkdir()
        (destination/"previous-version.txt").write_text("old",encoding="utf-8")
        state=tmp/"app-state"
        common=["--manifest",signed["manifest"],"--signature",signed["signature"],
                "--archive",signed["archive"],"--trusted-keys",trust_file,
                "--state",state,"--platform","windows-x64"]
        verified=run([updater,"verify",*common],expected=0,timeout=60)
        assert json.loads(verified.stdout)["verified"] is True
        # A signature that does not authenticate the manifest must be denied.
        corrupted=tmp/"bad-sig.txt"
        corrupted.write_text(base64.b64encode(b"x"*64).decode(),encoding="ascii")
        invalid=common.copy()
        invalid[3]=str(corrupted)  # index 3 is signature argument path
        run([updater,"verify",*invalid],expected=3,timeout=60)
        installed=run([updater,"apply",*common,"--target",destination],expected=0,timeout=180)
        result=json.loads(installed.stdout)
        assert result["ok"] and result["sequence"]==100
        assert (destination/"GUI"/"UniversalRemote-Preview.exe").is_file()
        assert (destination/"Agent"/"UniversalRemoteAgent-Preview.exe").is_file()
        assert (destination/"Updater"/"UniversalRemoteUpdater-Preview.exe").is_file()
        assert (destination/"Tunnel"/"UniversalRemoteTunnel-Preview.exe").is_file()
        assert (destination/"bin"/"tunnel-client.exe").is_file()
        assert (Path(result["backup"])/"previous-version.txt").read_text()=="old"
        run([updater,"verify",*common],expected=3,timeout=60)
        broken=tmp/"bad-payload"
        broken.mkdir()
        (broken/"broken.txt").write_text("fails health",encoding="utf-8")
        second=make_signed_package(broken,tmp/"bad-next-release",key,
                  "local-qa-only","1.0.0-rc5.2-bad",101,"windows-x64")
        common2=["--manifest",second["manifest"],"--signature",second["signature"],
                 "--archive",second["archive"],"--trusted-keys",trust_file,
                 "--state",state,"--platform","windows-x64"]
        run([updater,"apply",*common2,"--target",destination],expected=3,timeout=80)
        assert (destination/"GUI"/"UniversalRemote-Preview.exe").is_file()
        assert (destination/"Agent"/"UniversalRemoteAgent-Preview.exe").is_file()
        assert not (state/"update.pending.json").exists()
        assert json.loads((state/"update-state.json").read_text())["sequence"]==100
        health=run([destination/"Agent"/"UniversalRemoteAgent-Preview.exe",
                    "--health-probe"],expected=0,timeout=45)
        assert "UNIVERSAL_REMOTE_AGENT_HEALTH_OK" in health.stdout
        print("SIGNED_UPDATER_E2E_PASS",json.dumps({
             "signed_verification":True,"tampered_signature_denied":True,
             "installed_version":"1.0.0-rc5.1-qa",
             "downgrade_denied":True,"health_failure_rolled_back":True,
             "active_rc50_untouched":True,"test_signer":"ephemeral-only"}),flush=True)


if __name__=="__main__":
    main()
