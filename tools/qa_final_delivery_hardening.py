"""Final portable delivery validation: ZIP integrity, manifests, path hygiene, no personal state."""
from __future__ import annotations
import hashlib,json,os
from pathlib import Path,PurePosixPath
import zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/"Universal-Remote-Preview-v1.0.0-rc5.1"
QA=ROOT/"evidence"/"qa"
ZIP=BASE/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED-LATEST.zip"
EXE=BASE/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"
MANIFEST=BASE/"RELEASE-EVIDENCE.json"
def sha(path:Path)->str:
    with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def main():
    assert ZIP.is_file() and EXE.is_file()
    report=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert sha(ZIP)==report["portable_zip_sha256"]
    assert sha(EXE)==report["installer_sha256"]
    accepted=json.loads((QA/"installer-e2e-results.json").read_text(encoding="utf-8"))
    assert sha(EXE)==accepted["package_sha256"],"Installer not the accepted build"
    with zipfile.ZipFile(ZIP) as z:
        assert z.testzip() is None, "Corrupt zip CRC"
        names=z.namelist()
        assert len(names)==len({p.casefold() for p in names}),"Case-insensitive duplicate archive paths"
        roots={n.split("/",1)[0] for n in names}
        assert len(roots)==1
        prefix=next(iter(roots))+"/"
        for n in names:
            path=PurePosixPath(n)
            assert not n.startswith(("/","\\")) and "\\" not in n and ".." not in path.parts,n
            assert n.startswith(prefix),n
            lower=n.casefold()
            assert not lower.endswith(("/grants.json","/config.json","/tunnel.log",
                                        "/credentials.json","/.env","/.env.local")),n
            assert "/appdata/" not in lower,n
        required=("GUI/UniversalRemote-Preview.exe","Agent/UniversalRemoteAgent-Preview.exe",
                  "scripts/Prepare-PowerShell.ps1","scripts/Resolve-PowerShell.ps1",
                  "RELEASE-MANIFEST.json","SHA256SUMS.txt",
                  "docs/README.md","UNSIGNED-PREVIEW-NOT-FOR-PUBLICATION.txt")
        for path in required:assert prefix+path in names,"Missing "+path
        manifest=json.loads(z.read(prefix+"RELEASE-MANIFEST.json").decode("utf-8"))
        assert manifest["signed_publisher"] is False
        assert manifest["stdio_tools"]==27
        checks={row["path"]:row["sha256"] for row in manifest["files"]}
        assert checks
        for name,digest in checks.items():
            with z.open(prefix+name) as stream:
                computed=hashlib.file_digest(stream,"sha256").hexdigest()
            assert computed==digest,"Manifest entry mismatch "+name
        sums=z.read(prefix+"SHA256SUMS.txt").decode("utf-8")
        for name,digest in checks.items():
            assert digest+"  "+name in sums
    result={"zip_sha256":sha(ZIP),"installer_sha256":sha(EXE),
            "entries":len(names),"internal_files_hashed":len(checks),
            "dangerous_paths":0,"user_state_files":0,
            "installer_e2e":True,"public_signed":False}
    (QA/"RC51-HARDENING-DELIVERY-AUDIT.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print("RC51_FINAL_RELEASE_INTEGRITY_PASS",json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
