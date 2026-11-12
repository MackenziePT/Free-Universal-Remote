"""Offline publisher-side signing utility (not shipped with customer installer).

Private signing keys must stay OUTSIDE the source tree, build artifacts and
the target machine. This tool never generates or uploads a production key.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime,timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from release_security import _safe_name,_canonical,ReleaseError


def make_signed_package(source: Path, prefix: Path, private_key: Ed25519PrivateKey,
                        key_id: str, version: str, sequence: int, platform: str,
                        now: int | None = None) -> dict:
    source=Path(source).resolve(strict=True)
    prefix=Path(prefix)
    archive=prefix.with_suffix(".zip")
    manifest=prefix.with_suffix(".manifest.json")
    signature=prefix.with_suffix(".manifest.sig")
    if not source.is_dir() or archive.exists() or manifest.exists() or signature.exists():
        raise ReleaseError("Source directory invalid or release output already exists")
    files={}
    names=set()
    for dirpath, directories, filenames in os.walk(source,followlinks=False):
        here=Path(dirpath)
        for dirname in directories:
            entry=here/dirname
            if entry.is_symlink() or getattr(entry,"is_junction",lambda:False)():
                raise ReleaseError("Refusing symlink or junction in package")
        for filename in filenames:
            entry=here/filename
            if entry.is_symlink() or not entry.is_file():
                raise ReleaseError("Package contains nonregular file")
            rel=entry.relative_to(source).as_posix()
            _safe_name(rel)
            if rel.casefold() in names:
                raise ReleaseError("Path alias in release tree")
            names.add(rel.casefold())
            if entry.stat().st_size>500_000_000:
                raise ReleaseError("Payload file too large")
            with entry.open("rb") as fd:
                digest=hashlib.file_digest(fd,"sha256").hexdigest()
            files[rel]={"sha256":digest,"bytes":entry.stat().st_size}
    if not files:
        raise ReleaseError("Empty package")
    archive.parent.mkdir(parents=True,exist_ok=True)
    try:
        with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
            for rel in sorted(files):
                item=zipfile.ZipInfo(rel,(2020,1,1,0,0,0))
                item.compress_type=zipfile.ZIP_DEFLATED
                item.external_attr=(stat.S_IFREG|0o644)<<16
                with (source/rel).open("rb") as src, z.open(item,"w",force_zip64=True) as dest:
                    import shutil
                    shutil.copyfileobj(src,dest,1024*1024)
        now=int(time.time()) if now is None else int(now)
        with archive.open("rb") as f:
            archive_hash=hashlib.file_digest(f,"sha256").hexdigest()
        metadata={"format":1,"product":"universal-remote","key_id":key_id,
                  "sequence":sequence,"issued_at":now-30,"expires_at":now+14*86400,
                  "version":version,"platform":platform,"archive_sha256":archive_hash,
                  "archive_bytes":archive.stat().st_size,"files":files}
        raw=_canonical(metadata)
        signed=base64.b64encode(private_key.sign(raw)).decode("ascii")
        manifest.write_bytes(raw)
        signature.write_text(signed+"\n",encoding="ascii")
        return {"archive":str(archive),"manifest":str(manifest),
                "signature":str(signature),"bytes":archive.stat().st_size,
                "files":len(files),"sequence":sequence}
    except BaseException:
        for file in (archive,manifest,signature):
            file.unlink(missing_ok=True)
        raise


def main():
    parser=argparse.ArgumentParser(description="Offline Ed25519 package signer")
    parser.add_argument("--source",required=True,type=Path)
    parser.add_argument("--prefix",required=True,type=Path)
    parser.add_argument("--publisher-key",required=True,type=Path)
    parser.add_argument("--key-id",required=True)
    parser.add_argument("--version",required=True)
    parser.add_argument("--sequence",required=True,type=int)
    parser.add_argument("--platform",choices=["windows-x64","windows-arm64"],required=True)
    args=parser.parse_args()
    if args.source.resolve() == args.publisher_key.resolve() or args.publisher_key.resolve().is_relative_to(args.source.resolve()):
        raise SystemExit("Publisher private key cannot reside in package source directory")
    password=getpass.getpass("Offline publisher key passphrase: ").encode("utf-8")
    if not password:
        raise SystemExit("Encrypted publisher signing keys only")
    key=serialization.load_pem_private_key(args.publisher_key.read_bytes(),password=password)
    if not isinstance(key,Ed25519PrivateKey):
        raise SystemExit("Publisher key is not Ed25519")
    result=make_signed_package(args.source,args.prefix,key,args.key_id,args.version,
                               args.sequence,args.platform)
    print(json.dumps(result,sort_keys=True))
    print("Separately sign customer EXE/MSIX with trusted Authenticode publisher certificate.")


if __name__=="__main__":
    main()
