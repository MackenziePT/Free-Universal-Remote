"""Read-only Windows diagnostics for the bundled Python runtime."""
from __future__ import annotations
from ctypes import WinDLL
import hashlib
from pathlib import Path
import zipfile
from audit_bundled_runtime import audit_one

root = Path(__file__).resolve().parents[1] / "evidence" / "qa" / "public-portable-prototype"
variants = ("python313.dll", "python314.dll")
names = ("UniversalRemoteAgent-Preview", "UniversalRemoteUpdater-Preview",
         "UniversalRemoteTunnel-Preview")

for name in names:
    package = root / name
    inner = package / "_internal"
    found = [n for n in variants if (inner / n).is_file()]
    if len(found) != 1:
        raise RuntimeError(f"Expected exactly one Python DLL: {name}, found {found}")
    print("COMPONENT", name, "PYTHON_DLL", found[0])
    for filename in ("base_library.zip", "zlib1.dll", found[0]):
        p = inner / filename
        with p.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        print("FILE", filename, "BYTES", p.stat().st_size, "SHA256", digest)
    print("AUDIT", audit_one(package, name + ".exe"))
    for filename in ("zlib1.dll", found[0]):
        try:
            print("DLL_LOAD", filename, bool(WinDLL(str(inner / filename))._handle))
        except OSError as exc:
            print("DLL_LOAD_FAILED", filename, type(exc).__name__)
            raise
    with zipfile.ZipFile(inner / "base_library.zip") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Frozen Python standard-library ZIP is corrupt")
        members = set(archive.namelist())
        for entry in ("encodings/__init__.pyc", "encodings/utf_8.pyc", "codecs.pyc"):
            if entry not in members:
                raise RuntimeError("Missing CPython bootstrap entry: " + entry)
        print("EMBEDDED_ENCODING_BOOTSTRAP_VERIFIED")
