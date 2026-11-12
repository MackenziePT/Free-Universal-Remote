"""Read-only validation of the 2026-11-11 private security preview."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import sys
import zipfile

base=Path(sys.argv[1]).resolve()
report=json.loads((base/"RELEASE-EVIDENCE.json").read_text(encoding="utf-8"))
checks=[
    ("zip",base/"UniversalRemote-RC5.1-SECURITY-TEST-UNSIGNED.zip","zip_sha256"),
    ("installer",base/"UniversalRemote-RC5.1-SECURITY-TEST-UNSIGNED.exe","installer_sha256"),
]
for label,path,key in checks:
    assert path.is_file() and path.stat().st_size>1_000_000,(label,"file missing or empty")
    with path.open("rb") as stream: sha=hashlib.file_digest(stream,"sha256").hexdigest()
    assert sha==report[key],(label,"hash mismatch")
    print(label.upper(),"HASH_PASS",sha,"BYTES",path.stat().st_size)
with zipfile.ZipFile(checks[0][1]) as bundle:
    assert bundle.testzip() is None,"CRC failure"
    names=bundle.namelist()
    assert len(names)==len({name.casefold() for name in names}),"duplicated paths"
    assert all(".." not in PurePosixPath(name).parts and "\\" not in name
               and not name.startswith("/") for name in names),"unsafe paths"
    required=("GUI/UniversalRemote-Preview.exe","Agent/UniversalRemoteAgent-Preview.exe",
              "Updater/UniversalRemoteUpdater-Preview.exe","scripts/Test-Independent-PC.ps1")
    for expected in required:
        assert any(name.endswith("/"+expected) for name in names),("missing",expected)
    assert not any(name.casefold().endswith(("/config.json","/grants.json",
                  "/credentials.json","/.env")) for name in names),"private state included"
    print("ZIP_INTEGRITY_PASS","ENTRIES",len(names))
assert report["do_not_publish"] is True and report["publisher_signature"] is False
print("PRIVATE_SECURITY_PREVIEW_VERIFIED")
