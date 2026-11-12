"""Assemble unsigned internal portable preview + evidence manifest without private state."""
from __future__ import annotations
import hashlib,json,shutil,zipfile
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
BUNDLE=QA/"public-portable-prototype"
OUT=QA/"portable-release-automatic"
NAME="UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED-AUTO"
STAGE=OUT/NAME
ZIP=OUT/(NAME+".zip")
SETUP=QA/"installer-build"/"UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"

if not (BUNDLE/"UniversalRemote-Preview"/"UniversalRemote-Preview.exe").is_file():
    raise SystemExit("GUI build missing")
if not (BUNDLE/"UniversalRemoteAgent-Preview"/"UniversalRemoteAgent-Preview.exe").is_file():
    raise SystemExit("Agent build missing")
if not SETUP.is_file():
    raise SystemExit("Installer build missing")
if STAGE.exists() or ZIP.exists():
    raise SystemExit("Refusing to overwrite prior portable release; clean manually after preserving evidence")
OUT.mkdir(parents=True,exist_ok=True)
STAGE.mkdir()
try:
    shutil.copytree(BUNDLE/"UniversalRemote-Preview",STAGE/"GUI")
    shutil.copytree(BUNDLE/"UniversalRemoteAgent-Preview",STAGE/"Agent")
    (STAGE/"scripts").mkdir()
    for name in ("Resolve-PowerShell.ps1","Prepare-PowerShell.ps1"):
        shutil.copy2(ROOT/"scripts"/name,STAGE/"scripts"/name)
    (STAGE/"docs").mkdir()
    for relative in ("README.md","docs/PUBLIC_SECURITY_MODEL.md",
                     "docs/PUBLIC_RELEASE_GATES.md","docs/INSTALLER_AND_UX_SPEC.md"):
        shutil.copy2(ROOT/relative,STAGE/"docs"/Path(relative).name)
    (STAGE/"UNSIGNED-PREVIEW-NOT-FOR-PUBLICATION.txt").write_text(
        "Internal development preview. Not digitally signed by a trusted publisher.\n"
        "Do not publicly distribute. Does not include authenticated remote pairing.\n"
        "No global Python or PowerShell installation is required to start the GUI/agent.\n",
        encoding="utf-8")
    paths=sorted(p for p in STAGE.rglob("*") if p.is_file())
    checks=[]
    for p in paths:
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        checks.append({"path":p.relative_to(STAGE).as_posix(),"sha256":sha,"bytes":p.stat().st_size})
    manifest={
        "kind":"unsigned-preview-internal",
        "product":"Universal Remote",
        "version":"1.0.0-rc5.1-dev",
        "platform":"Windows x64",
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "stdio_tools":27,
        "remote_transport":"NOT CONFIGURED",
        "global_python_required":False,
        "global_powershell_required_for_gui":False,
        "signed_publisher":False,
        "files":checks,
    }
    (STAGE/"RELEASE-MANIFEST.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    (STAGE/"SHA256SUMS.txt").write_text(
        "\n".join(item["sha256"]+"  "+item["path"] for item in checks)+"\n",
        encoding="utf-8")
    with zipfile.ZipFile(ZIP,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                archive.write(p,f"{NAME}/{p.relative_to(STAGE).as_posix()}")
    with zipfile.ZipFile(ZIP) as archive:
        bad=archive.testzip()
        if bad:raise RuntimeError("ZIP CRC corruption "+bad)
        zipfiles=len(archive.namelist())
    report={
        "portable_zip_sha256":hashlib.sha256(ZIP.read_bytes()).hexdigest(),
        "portable_zip_size_mb":round(ZIP.stat().st_size/1048576,2),
        "portable_zip_entries":zipfiles,
        "installer_sha256":hashlib.sha256(SETUP.read_bytes()).hexdigest(),
        "installer_size_mb":round(SETUP.stat().st_size/1048576,2),
        "status":"UNSIGNED INTERNAL PREVIEW — NOT READY FOR PUBLIC RELEASE",
    }
    (OUT/"RELEASE-EVIDENCE.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("INTERNAL_DISTRIBUTION_PACKAGED",json.dumps(report),flush=True)
except BaseException:
    if STAGE.exists():shutil.rmtree(STAGE)
    if ZIP.exists():ZIP.unlink()
    raise
