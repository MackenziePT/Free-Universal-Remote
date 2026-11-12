"""Release gate: Windows bundles must contain Python and VC runtime DLLs locally."""
from __future__ import annotations
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dependency_preflight import BUNDLED_PYTHON_FILES

PRODUCT_MACHINE = 0x8664  # IMAGE_FILE_MACHINE_AMD64

def pe_machine(path: Path) -> int:
    with path.open("rb") as handle:
        dos = handle.read(64)
        if len(dos) != 64 or dos[:2] != b"MZ":
            raise ValueError(f"Missing DOS/PE header: {path.name}")
        header_offset = struct.unpack_from("<I",dos,0x3C)[0]
        if not (64 <= header_offset <= 1_000_000):
            raise ValueError(f"Invalid PE header offset: {path.name}")
        handle.seek(header_offset)
        signature=handle.read(6)
    if len(signature)!=6 or signature[:4]!=b"PE\x00\x00":
        raise ValueError(f"Invalid PE signature: {path.name}")
    return struct.unpack_from("<H",signature,4)[0]

def audit_one(directory:Path,executable:str,expected_machine:int=PRODUCT_MACHINE)->dict:
    exe=directory/executable
    inner=directory/"_internal"
    missing=[]
    if not exe.is_file():missing.append(executable)
    if not inner.is_dir():missing.append("_internal/")
    else:
        missing.extend(name for name in BUNDLED_PYTHON_FILES if not (inner/name).is_file())
    if missing:
        raise ValueError(f"Bundle {directory.name}: missing required files: {', '.join(missing)}")
    exe_arch=pe_machine(exe)
    dll_arch=pe_machine(inner/"python314.dll")
    if exe_arch!=expected_machine or dll_arch!=expected_machine:
        raise ValueError(f"Wrong architecture in {directory.name}: exe={exe_arch:x}, Python={dll_arch:x}")
    return {"component":directory.name,"architecture":"Windows x64","embedded_python":True,
            "embedded_vc_runtime":True,"files":len(list(directory.rglob("*")))}

def audit_all(distribution:Path)->list[dict]:
    return [
        audit_one(distribution/"UniversalRemote-Preview","UniversalRemote-Preview.exe"),
        audit_one(distribution/"UniversalRemoteAgent-Preview","UniversalRemoteAgent-Preview.exe"),
        audit_one(distribution/"UniversalRemoteUpdater-Preview","UniversalRemoteUpdater-Preview.exe"),
        audit_one(distribution/"UniversalRemoteTunnel-Preview","UniversalRemoteTunnel-Preview.exe")
    ]

if __name__=="__main__":
    dist=Path(sys.argv[1]) if len(sys.argv)>1 else (
        Path(__file__).resolve().parents[1]/"evidence"/"qa"/"public-portable-prototype")
    result=audit_all(dist)
    print("BUNDLED_WINDOWS_PREREQUISITES_PASS",json.dumps(result,ensure_ascii=False))
