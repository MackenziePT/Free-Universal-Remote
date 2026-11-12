from pathlib import Path
import hashlib,zipfile,sys
root=Path(sys.argv[1])
for p in sorted(root.iterdir()):
    if not p.is_dir() or not p.name.startswith("UniversalRemote"):
        continue
    z=p/"_internal"/"base_library.zip"
    with zipfile.ZipFile(z) as arc:
        print("COMPONENT",p.name)
        print("BASE_ZIP",z.stat().st_size,"SHA",hashlib.sha256(z.read_bytes()).hexdigest(),"CRC",arc.testzip())
        entries=[name for name in arc.namelist() if name.startswith("encodings/")]
        print("ENCODINGS_COUNT",len(entries),"HEAD",entries[:7])
        import importlib.util
        magic=arc.read("encodings/__init__.pyc")[:4]
        print("MAGIC",magic.hex(),"EXPECTED",importlib.util.MAGIC_NUMBER.hex())
        for n in ("python314.dll","python3.dll","ucrtbase.dll","VCRUNTIME140.dll","python314.zip"):
            f=p/"_internal"/n
            print("DLL",n,"size",f.stat().st_size if f.exists() else None,
                  "SHA",hashlib.sha256(f.read_bytes()).hexdigest()[:24] if f.exists() else None)
        print("INNER",len(list((p/"_internal").iterdir())))

source=root/"UniversalRemoteAgent-Preview"/"_internal"
for name in ("UniversalRemote-Preview","UniversalRemoteUpdater-Preview"):
    other=root/name/"_internal"
    missing=sorted(str(f.relative_to(source)) for f in source.rglob("*")
                   if f.is_file() and not (other/f.relative_to(source)).exists())
    print("MISSING_IN",name,"count",len(missing),"files",missing[:60])
    print("NOW_HASH",name,hashlib.sha256((other/"base_library.zip").read_bytes()).hexdigest())
