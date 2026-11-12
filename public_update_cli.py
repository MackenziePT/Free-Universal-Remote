"""Standalone verified update/recovery worker for Universal Remote.

Run this sidecar only after closing the main application. Publisher keys are
read from a separately provisioned, trusted location outside the payload.
A developer test key does not establish public publisher identity.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

from release_security import (ReleaseError, apply_signed_update,
                              recover_update, verify_signed_release, verify_payload,
                              _unique_json)
from release_trust_anchor import RELEASE_CHANNEL, PUBLISHER_KEYRING


def _validate_public_keys(keys: dict) -> dict[str,str]:
    if not isinstance(keys, dict) or not 1 <= len(keys) <= 5:
        raise ReleaseError("Invalid publisher keyring")
    for key_id, encoded in keys.items():
        if not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", key_id):
            raise ReleaseError("Invalid publisher key id")
        if not isinstance(encoded, str):
            raise ReleaseError("Invalid publisher key data")
        try:
            material = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ReleaseError("Invalid publisher key encoding") from exc
        if len(material) != 32:
            raise ReleaseError("Invalid publisher key length")
    return dict(keys)


def trusted_keys(path: Path | None) -> dict[str,str]:
    """Production never trusts caller-chosen public keys."""
    if RELEASE_CHANNEL == "PRODUCTION":
        if path is not None:
            raise ReleaseError("Production updater forbids external keyrings")
        return _validate_public_keys(PUBLISHER_KEYRING)
    if RELEASE_CHANNEL != "PRIVATE_QA":
        raise ReleaseError("Unknown build channel denied")
    if path is None:
        raise ReleaseError("Private QA requires explicit disposable trust store")
    store = _unique_json(Path(path).read_bytes())
    if set(store) != {"format", "product", "keys"} or store["format"] != 1 or store["product"] != "universal-remote":
        raise ReleaseError("Invalid disposable QA keyring")
    return _validate_public_keys(store["keys"])


def app_health(target:Path) -> bool:
    agent=target/"Agent"/"UniversalRemoteAgent-Preview.exe"
    gui=target/"GUI"/"UniversalRemote-Preview.exe"
    tunnel=target/"Tunnel"/"UniversalRemoteTunnel-Preview.exe"
    client=target/"bin"/"tunnel-client.exe"
    if os.name!="nt" or not all(x.is_file() for x in (agent,gui,tunnel,client)):
        return False
    if client.stat().st_size!=22591488:
        return False
    with client.open("rb") as stream:
        if hashlib.file_digest(stream,"sha256").hexdigest()!="4226bb74a72388147882881f29f79801b95e285d731a138071812e3aa6766571":
            return False
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    try:
        result=subprocess.run([str(agent),"--health-probe"],cwd=agent.parent,
                   stdin=subprocess.DEVNULL,capture_output=True,
                   timeout=20,check=False,creationflags=flags)
        if result.returncode or b"UNIVERSAL_REMOTE_AGENT_HEALTH_OK" not in result.stdout:
            return False
        smoke=subprocess.run([str(gui),"--self-test"],cwd=gui.parent,
                   stdin=subprocess.DEVNULL,capture_output=True,
                   timeout=35,check=False,creationflags=flags)
        if smoke.returncode!=0:
            return False
        service=subprocess.run([str(tunnel),"--self-test"],cwd=tunnel.parent,
                   stdin=subprocess.DEVNULL,capture_output=True,
                   timeout=35,check=False,creationflags=flags)
        return service.returncode==0 and b"UNIVERSAL_REMOTE_TUNNEL_SELFTEST_OK" in service.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def main()->int:
    parser=argparse.ArgumentParser(description="Verified Universal Remote updater")
    sub=parser.add_subparsers(dest="action",required=True)
    for name in ("verify","apply"):
        p=sub.add_parser(name)
        p.add_argument("--manifest",required=True,type=Path)
        p.add_argument("--signature",required=True,type=Path)
        p.add_argument("--archive",required=True,type=Path)
        p.add_argument("--trusted-keys",type=Path,
                       help="Only permitted in explicitly PRIVATE_QA development builds")
        p.add_argument("--state",required=True,type=Path)
        p.add_argument("--platform",choices=["windows-x64","windows-arm64"],required=True)
        if name=="apply":
            p.add_argument("--target",required=True,type=Path)
    profile=sub.add_parser("trust-profile",help="Inspect embedded release trust mode; no private keys")
    recovery=sub.add_parser("recover")
    recovery.add_argument("--target",required=True,type=Path)
    recovery.add_argument("--state",required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.action == "trust-profile":
            if RELEASE_CHANNEL == "PRODUCTION":
                _validate_public_keys(PUBLISHER_KEYRING)
            elif RELEASE_CHANNEL != "PRIVATE_QA":
                raise ReleaseError("Unrecognized updater build channel")
            print(json.dumps({"channel": RELEASE_CHANNEL, "embedded_keys":len(PUBLISHER_KEYRING)}))
            return 0
        if args.action=="recover":
            result=recover_update(args.target,args.state)
            print("RECOVERED" if result else "NO_PENDING_UPDATE")
            return 0
        keys=trusted_keys(args.trusted_keys)
        current_file=args.state/"update-state.json"
        current=_unique_json(current_file.read_bytes()) if current_file.is_file() else {"sequence":0}
        sequence=current.get("sequence",0)
        if type(sequence) is not int or sequence<0:
            raise ReleaseError("Invalid installed sequence")
        metadata=args.manifest.read_bytes()
        signature=args.signature.read_text(encoding="ascii").strip()
        manifest=verify_signed_release(metadata,signature,keys,minimum_sequence=sequence)
        if manifest["platform"]!=args.platform:
            raise ReleaseError("Architecture mismatch")
        verify_payload(args.archive,manifest)
        if args.action=="verify":
            print(json.dumps({"verified":True,"version":manifest["version"],
                 "sequence":manifest["sequence"],"files":len(manifest["files"])}))
            return 0
        result=apply_signed_update(target=args.target,state_dir=args.state,
                    archive=args.archive,metadata_bytes=metadata,
                    signature_b64=signature,trusted_keys=keys,
                    platform=args.platform,health_check=app_health)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ReleaseError,OSError,ValueError) as exc:
        # No secrets, release paths or metadata in error output.
        print("UPDATE_REFUSED: "+type(exc).__name__,file=sys.stderr)
        return 3


if __name__=="__main__":
    raise SystemExit(main())
