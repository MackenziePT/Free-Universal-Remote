from pathlib import Path
import hashlib
import zipfile
base=Path(__file__).resolve().parents[1]/"evidence"/"qa"
source=base/"public-portable-prototype"/"UniversalRemoteAgent-Preview"/"_internal"/"base_library.zip"
for candidate in base.glob("urm-signed-e2e-*/.ur-failed-*/Agent/_internal/base_library.zip"):
    for f in (source,candidate):
        print("path length",len(str(f)), "file length",f.stat().st_size,
              "sha256",hashlib.sha256(f.read_bytes()).hexdigest())
        with zipfile.ZipFile(f) as z:
            print("bad zip member",z.testzip(),"has encodings",
               any(n.startswith("encodings/") for n in z.namelist()))
    print("EQUAL_BYTES",source.read_bytes()==candidate.read_bytes())
