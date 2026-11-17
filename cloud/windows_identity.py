"""DPAPI-bound private device identity persistence for the Windows desktop app.

The remote gateway NEVER receives device private key bytes. Windows DPAPI binds
the encrypted key to the logged-in user. Enrollment uses the system browser's
OAuth flow, implemented in the native UI; this module does not fake login.
"""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from .auth import public_https
from .device_client import Signer, _id


class IdentityError(PermissionError):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_=[("cbData",wintypes.DWORD),("pbData",ctypes.POINTER(ctypes.c_ubyte))]


def _windows_only():
    if sys.platform!="win32":
        raise IdentityError("DPAPI requires a real Windows user session")


def _dpapi(data: bytes, *, encrypt: bool) -> bytes:
    _windows_only()
    crypt32=ctypes.windll.crypt32
    kernel=ctypes.windll.kernel32
    source=ctypes.create_string_buffer(data)
    inp=DATA_BLOB(len(data),ctypes.cast(source,ctypes.POINTER(ctypes.c_ubyte)))
    output=DATA_BLOB()
    entropy_bytes=b"UniversalRemote/PublicDeviceIdentity/v1"
    entropy=ctypes.create_string_buffer(entropy_bytes)
    extra=DATA_BLOB(len(entropy_bytes),ctypes.cast(entropy,ctypes.POINTER(ctypes.c_ubyte)))
    flags=0x01 # CRYPTPROTECT_UI_FORBIDDEN. Do NOT use CRYPTPROTECT_LOCAL_MACHINE.
    if encrypt:
        crypt32.CryptProtectData.argtypes=[ctypes.POINTER(DATA_BLOB),wintypes.LPCWSTR,
            ctypes.POINTER(DATA_BLOB),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB)]
        crypt32.CryptProtectData.restype=wintypes.BOOL
        success=crypt32.CryptProtectData(ctypes.byref(inp),"Universal Remote device identity",
            ctypes.byref(extra),None,None,flags,ctypes.byref(output))
    else:
        crypt32.CryptUnprotectData.argtypes=[ctypes.POINTER(DATA_BLOB),ctypes.c_void_p,
            ctypes.POINTER(DATA_BLOB),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB)]
        crypt32.CryptUnprotectData.restype=wintypes.BOOL
        success=crypt32.CryptUnprotectData(ctypes.byref(inp),None,
            ctypes.byref(extra),None,None,flags,ctypes.byref(output))
    if not success:
        raise IdentityError("Windows DPAPI operation failed")
    try:
        return ctypes.string_at(output.pbData,output.cbData)
    finally:
        kernel.LocalFree.argtypes=[ctypes.c_void_p]
        kernel.LocalFree.restype=ctypes.c_void_p
        kernel.LocalFree(output.pbData)


def default_identity_path() -> Path:
    _windows_only()
    path=os.environ.get("LOCALAPPDATA")
    if not path:
        raise IdentityError("LOCALAPPDATA is missing")
    return Path(path)/"UniversalRemote"/"PublicLink"/"device_identity.json"


def save_identity(path: Path, signer: Signer, origin: str, device_id: str) -> None:
    _windows_only()
    if not public_https(origin) or origin.rstrip('/')!=origin or '/' in origin.split('://',1)[1]:
        raise IdentityError("Only public HTTPS origins are allowed")
    _id(device_id)
    key=signer.private_key.private_bytes(serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,serialization.NoEncryption())
    encrypted=_dpapi(key,encrypt=True)
    record={"version":1,"origin":origin,"device_id":device_id,
            "dpapi_key":base64.b64encode(encrypted).decode()}
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        raise IdentityError("Identity already exists; revoke first, do not overwrite")
    # OS directory is user-specific and key is encrypted under current-user DPAPI.
    fd,name=tempfile.mkstemp(prefix='.identity-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as handle:
            json.dump(record,handle,sort_keys=True)
            handle.flush();os.fsync(handle.fileno())
        if path.exists():
            raise IdentityError("Identity created concurrently")
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_identity(path: Path):
    _windows_only()
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    if set(obj)!={"version","origin","device_id","dpapi_key"} or obj['version']!=1:
        raise IdentityError("Unsupported device identity format")
    if not public_https(obj['origin']):
        raise IdentityError("Invalid paired origin")
    device_id=_id(obj['device_id'])
    encrypted=base64.b64decode(obj['dpapi_key'],validate=True)
    key=_dpapi(encrypted,encrypt=False)
    if len(key)!=32:
        raise IdentityError("Invalid decrypted Ed25519 key")
    return obj['origin'],device_id,Signer(Ed25519PrivateKey.from_private_bytes(key))
