"""Verify that the externally shareable QA ZIP contains only approved files."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT.parent/"Universal-Remote-Preview-v1.0.0-rc5.1"/"UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip"
with zipfile.ZipFile(ZIP) as archive:
    entries=archive.namelist()
    expected={
        "UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe",
        "Check-Independent-Windows-PC.ps1",
        "LEIA-PRIMEIRO-QA-EXTERNO.txt",
        "QA-MANIFEST.json",
        "SHA256SUMS.txt",
    }
    assert set(entries)==expected,entries
    assert archive.testzip() is None
    m=json.loads(archive.read("QA-MANIFEST.json"))
    digest=hashlib.sha256(archive.read(m["installer"])).hexdigest()
    assert digest==m["installer_sha256"]
    assert m["signed"] is False and m["publisher_verified"] is False
    assert m["certified"] is False and m["tested_on_other_PCs"] is False
    with ZIP.open("rb") as stream:
        zip_digest=hashlib.file_digest(stream,"sha256").hexdigest()
print("INDEPENDENT_QA_ZIP_PASS",str(ZIP),"bytes",ZIP.stat().st_size,
      "installer_hash",digest,"zip_hash",zip_digest)
