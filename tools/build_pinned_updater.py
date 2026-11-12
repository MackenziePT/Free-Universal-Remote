"""Build an isolated PRODUCTION trust-pinned updater from PUBLIC Ed25519 keys.

No private signing key or Authenticode certificate is handled here.
The resulting binary is NOT signed and must never be published until
CA Authenticode and independent security/compatibility gates succeed.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/"evidence"/"qa"
SOURCE=QA/"public-portable-prototype"
STAGING=QA/"publisher-ready-bundle"
from public_update_cli import _validate_public_keys
from release_security import ReleaseError


def read_public_keyring(path: Path) -> dict:
    path=Path(path).resolve(strict=True)
    if path.is_relative_to(ROOT):
        raise ReleaseError("Release publisher public keys must be provisioned out-of-band")
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or set(data)!={"format","product","keys"} or data["format"]!=1 or data["product"]!="universal-remote":
        raise ReleaseError("Invalid public keyring format")
    return _validate_public_keys(data["keys"])


def prepare_sources(out: Path, pubkeys: dict) -> None:
    if out.exists():
        raise FileExistsError("Refusing to overwrite production candidate sources")
    out.mkdir(parents=True)
    for name in ("release_security.py","public_update_cli.py"):
        shutil.copy2(ROOT/name, out/name)
    anchor=('"""Build-time embedded Ed25519 public publisher keys. NO private keys."""\n'
            'RELEASE_CHANNEL = "PRODUCTION"\n'
            'PUBLISHER_KEYRING = '+repr(pubkeys)+'\n')
    (out/"release_trust_anchor.py").write_text(anchor,encoding="utf-8")


def build(pubkeys: dict, *, python_bin: Path) -> dict:
    if STAGING.exists():
        raise FileExistsError("Pinned release staging already exists, refusing overwrite")
    stage_source=QA/"production-trust-source"
    if stage_source.exists():
        raise FileExistsError("Production trust source already exists; inspect before rerun")
    prepare_sources(stage_source,pubkeys)
    try:
        STAGING.mkdir(parents=True)
        for name in ("UniversalRemote-Preview","UniversalRemoteAgent-Preview",
                     "UniversalRemoteTunnel-Preview"):
            shutil.copytree(SOURCE/name,STAGING/name)
        command=[str(python_bin),"-m","PyInstaller",
           "--noconfirm","--clean","--noupx","--onedir","--console",
           "--name","UniversalRemoteUpdater-Preview",
           "--distpath",str(STAGING),
           "--workpath",str(QA/"pinned-updater-work"),
           "--specpath",str(QA/"pinned-updater-spec"),
           "--paths",str(stage_source),
           "--hidden-import","release_trust_anchor",
           "--hidden-import","cryptography.hazmat.primitives.asymmetric.ed25519",
           str(stage_source/"public_update_cli.py")]
        log=QA/"pinned-updater-build.log"
        with log.open("wb") as output:
            completed=subprocess.run(command,cwd=str(stage_source),stdout=output,
                                     stderr=subprocess.STDOUT,timeout=900,check=False)
        if completed.returncode:
            raise RuntimeError("Pinned updater PyInstaller build failed; see pinned-updater-build.log")
        executable=STAGING/"UniversalRemoteUpdater-Preview"/"UniversalRemoteUpdater-Preview.exe"
        source_zlib=SOURCE/"UniversalRemoteAgent-Preview"/"_internal"/"zlib1.dll"
        target_zlib=executable.parent/"_internal"/"zlib1.dll"
        if source_zlib.exists() and not target_zlib.exists():
            shutil.copy2(source_zlib,target_zlib)
        result=subprocess.run([str(executable),"trust-profile"],capture_output=True,text=True,
                              errors="replace",timeout=45,check=False)
        if result.returncode or json.loads(result.stdout)!={"channel":"PRODUCTION","embedded_keys":len(pubkeys)}:
            raise RuntimeError("Compiled publisher trust anchor failed runtime verification")
        check={"status":"UNSIGNED_CA_SIGNING_REQUIRED","channel":"PRODUCTION",
               "key_ids":sorted(pubkeys),"keys_sha256":
                 hashlib.sha256(json.dumps(pubkeys,sort_keys=True).encode()).hexdigest(),
               "updater_sha256":hashlib.sha256(executable.read_bytes()).hexdigest()}
        (STAGING/"PINNED-TRUST-BUILD-MANIFEST.json").write_text(
             json.dumps(check,indent=2),encoding="utf-8")
        return check
    except BaseException:
        # Retain staging for forensic review rather than claim success.
        (STAGING/"FAILED-BUILD.txt").write_text("Do not sign or publish this build.",encoding="utf-8")
        raise


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--public-keyring",type=Path,required=True,
        help="Only the PUBLIC Ed25519 keys, supplied out-of-band, never a private key")
    ap.add_argument("--python-bin",type=Path,default=Path(sys.executable))
    ap.add_argument("--preflight",action="store_true",
        help="Validate public keyring and source prerequisites; do not build")
    args=ap.parse_args()
    keys=read_public_keyring(args.public_keyring)
    if args.preflight:
        print(json.dumps({"source_ready":True,"key_ids":sorted(keys),
             "signed":False,"production_binary_built":False}))
        return
    print(json.dumps(build(keys,python_bin=args.python_bin),indent=2))


if __name__=="__main__":
    main()
