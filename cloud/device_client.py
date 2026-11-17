"""Secure outbound Windows device protocol client (transport, not privilege broker).

The native Universal Remote app MUST provide the local authorization / dispatch
callback and protect the Ed25519 private key with Windows DPAPI. This transport
has no way to grant shell, screen, file, or input permissions by itself.
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .auth import public_https
from .storage import encode_json


class AgentError(RuntimeError):
    pass


ALLOWED_REMOTE_OPS = frozenset({
    "windows_diagnostic", "read_text_file", "run_powershell", "desktop_screenshot", "desktop_action"
})


def _id(raw: str) -> str:
    try:
        obj=uuid.UUID(raw)
    except (ValueError,AttributeError,TypeError) as exc:
        raise AgentError("Noncanonical operation identifier") from exc
    if obj.version!=4 or str(obj)!=raw:
        raise AgentError("Noncanonical operation identifier")
    return raw


@dataclass(frozen=True)
class Signer:
    """Owner-provided key, stored encrypted by the native Windows desktop UI."""
    private_key: Ed25519PrivateKey

    @classmethod
    def generate_for_local_enrollment(cls):
        # Caller MUST persist this with DPAPI; never send the private key to the server.
        return cls(Ed25519PrivateKey.generate())

    def public_key(self) -> str:
        raw=self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        return base64.b64encode(raw).decode("ascii")

    def sign_enrollment(self, info: dict) -> dict:
        owner=info.get("owner")
        if not isinstance(owner,str) or len(owner)!=64:
            raise AgentError("Invalid enrollment owner")
        ident=_id(info.get("id"))
        challenge=info.get("challenge")
        if not isinstance(challenge,str):
            raise AgentError("Invalid challenge")
        if len(base64.b64decode(challenge,validate=True))!=32:
            raise AgentError("Invalid challenge length")
        msg=encode_json({"domain":"universal-remote-enroll/v1", "owner":owner,
                         "id":ident,"challenge":challenge,"public_key":self.public_key()})
        return {"id":ident,"public_key":self.public_key(),
                "signature":base64.b64encode(self.private_key.sign(msg)).decode("ascii")}

    def sign(self,device_id:str,method:str,path:str,body:bytes=b"") -> dict:
        device_id=_id(device_id)
        nonce=str(uuid.uuid4())
        timestamp=int(time.time())
        message=encode_json({"domain":"universal-remote-agent/v1",
             "device_id":device_id,"nonce":nonce,"timestamp":timestamp,
             "method":method,"path":path,"sha256":hashlib.sha256(body).hexdigest()})
        return {"x-ur-nonce":nonce,"x-ur-timestamp":str(timestamp),
                "x-ur-signature":base64.b64encode(self.private_key.sign(message)).decode("ascii")}


class DeviceAgent:
    """Poll authorized jobs, check local grants, dispatch, and return signed results.

    `has_local_permission` MUST query the current native app policy/grants and
    `dispatch_local` MUST invoke that trusted native app. These callbacks are
    mandatory and intentionally cannot be remote-set through MCP.
    """
    def __init__(self, origin: str, device_id: str, signer: Signer, *,
                 has_local_permission: Callable[[str],bool],
                 dispatch_local: Callable[[str,dict],dict],
                 http=None):
        if not public_https(origin) or origin.rstrip("/")!=origin or '/' in origin.split('://',1)[1]:
            raise AgentError("Agent origin must be a public HTTPS origin")
        self.origin=origin
        self.device_id=_id(device_id)
        self.signer=signer
        if not callable(has_local_permission) or not callable(dispatch_local):
            raise AgentError("Native Windows authorization and dispatch are required")
        self.has_local_permission=has_local_permission
        self.dispatch_local=dispatch_local
        self.http=http or httpx.Client(timeout=20,verify=True,follow_redirects=False)

    def poll_once(self):
        path=f"/v1/agent/{self.device_id}/poll"
        resp=self.http.get(self.origin+path,headers=self.signer.sign(self.device_id,'GET',path))
        resp.raise_for_status()
        job=resp.json().get('job')
        if job is None:
            return None
        operation=_id(job.get('operation_id'))
        name=job.get('tool')
        args=job.get('arguments')
        if name not in ALLOWED_REMOTE_OPS or not isinstance(args,dict):
            output={'error':'Unknown or malformed cloud instruction'};okay=False
        elif not self.has_local_permission(name):
            output={'error':'Local owner has not granted this capability'};okay=False
        else:
            try:
                output=self.dispatch_local(name,args)
                okay=True
            except Exception:
                # Never relay internal traceback or secrets to public gateway.
                output={'error':'Locally authorized action failed'};okay=False
        body=encode_json({'operation_id':operation,'ok':okay,'output':output})
        path=f"/v1/agent/{self.device_id}/result"
        response=self.http.post(self.origin+path,headers=self.signer.sign(self.device_id,'POST',path,body),content=body)
        response.raise_for_status()
        return {'operation_id':operation,'status':'done' if okay else 'denied'}
