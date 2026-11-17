"""Public outbound-only connection to Universal Remote Windows, with local approval."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
import json, os, re, time, webbrowser
import httpx
from .auth import public_https
from .device_client import DeviceAgent, Signer, AgentError, _id

class LinkError(RuntimeError): pass

@dataclass(frozen=True)
class LinkConfig:
    gateway: str
    issuer: str
    client_id: str
    def __post_init__(self):
        if not isinstance(self.gateway,str) or not public_https(self.gateway) or self.gateway.rstrip("/")!=self.gateway or urlsplit(self.gateway).path:
            raise LinkError("Public HTTPS gateway origin required")
        if not isinstance(self.issuer,str) or not public_https(self.issuer):
            raise LinkError("HTTPS issuer required")
        if not isinstance(self.client_id,str) or not re.fullmatch(r"[A-Za-z0-9._~:-]{2,128}",self.client_id):
            raise LinkError("Registered public OAuth client ID required")
    @classmethod
    def from_env(cls):
        path=Path(__file__).with_name("public_link_settings.json")
        try:
            data=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            return cls(os.environ.get("UR_PUBLIC_ORIGIN",data.get("gateway")),
                       os.environ.get("UR_OIDC_ISSUER",data.get("issuer")),
                       os.environ.get("UR_WINDOWS_OAUTH_CLIENT_ID",data.get("client_id")))
        except (OSError,ValueError,KeyError,TypeError) as exc:
            raise LinkError("Publisher OAuth provider is not configured") from exc

def _trusted(url,issuer):
    if not isinstance(url,str) or not public_https(url) or urlsplit(url).hostname!=urlsplit(issuer).hostname:
        raise LinkError("Untrusted OAuth provider URL")
    return url

def device_authorize(cfg, *, http=None, open_browser=None, note=None, sleep=None, now=None):
    own=http is None
    http=http or httpx.Client(timeout=15,verify=True,follow_redirects=False)
    open_browser=open_browser or webbrowser.open
    note=note or (lambda x:None)
    sleep=sleep or time.sleep
    now=now or time.monotonic
    try:
        r=http.get(_trusted(cfg.issuer.rstrip("/")+"/.well-known/openid-configuration",cfg.issuer))
        r.raise_for_status()
        metadata=r.json()
        if not isinstance(metadata,dict) or metadata.get("issuer")!=cfg.issuer:
            raise LinkError("OIDC issuer mismatch")
        url=_trusted(metadata.get("device_authorization_endpoint"),cfg.issuer)
        token_url=_trusted(metadata.get("token_endpoint"),cfg.issuer)
        r=http.post(url,data={"client_id":cfg.client_id,"resource":cfg.gateway+"/mcp",
            "scope":"openid profile ur:read ur:devices"})
        r.raise_for_status()
        info=r.json()
        if not isinstance(info,dict):raise LinkError("Invalid OAuth device response")
        dc=info.get("device_code");uc=info.get("user_code")
        verification=_trusted(info.get("verification_uri_complete",info.get("verification_uri")),cfg.issuer)
        expires=info.get("expires_in");interval=info.get("interval",5)
        if not(isinstance(dc,str) and 10<=len(dc)<=2048 and isinstance(uc,str)
               and 2<=len(uc)<=128 and type(expires) is int and 30<=expires<=900
               and type(interval) is int and 1<=interval<=30):
            raise LinkError("Invalid OAuth device authorization parameters")
        note("Confirma a ligação no navegador. Código: "+uc)
        if open_browser(verification) is False:raise LinkError("Browser unavailable")
        deadline=now()+expires
        while True:
            remaining=deadline-now()
            if remaining<=0:raise LinkError("OAuth sign-in expired")
            sleep(min(interval,remaining))
            r=http.post(token_url,data={"grant_type":"urn:ietf:params:oauth:grant-type:device_code",
                "device_code":dc,"client_id":cfg.client_id,"resource":cfg.gateway+"/mcp"})
            body=r.json()
            if r.status_code==200:
                value=body.get("access_token") if isinstance(body,dict) else None
                if not isinstance(value,str) or len(value)<8 or body.get("token_type","").lower()!="bearer":
                    raise LinkError("Invalid OAuth token")
                return value
            error=body.get("error") if isinstance(body,dict) else None
            if error=="authorization_pending":continue
            if error=="slow_down":interval=min(interval+5,30);continue
            raise LinkError("OAuth sign-in denied or expired")
    except (httpx.HTTPError,TypeError,ValueError,KeyError) as exc:
        raise LinkError("Unable to establish secure provider sign-in") from exc
    finally:
        if own:http.close()

def enroll_windows(cfg,bearer,label, *,http=None,save_identity=None):
    if not isinstance(bearer,str) or len(bearer)<8 or any(c.isspace() for c in bearer):
        raise LinkError("An authenticated OAuth bearer token is required")
    if not isinstance(label,str) or not 1<=len(label)<=48 or any(ord(c)<32 for c in label):
        raise LinkError("Invalid Windows PC name")
    if not callable(save_identity):raise LinkError("DPAPI persistence callback required")
    own=http is None
    http=http or httpx.Client(timeout=15,verify=True,follow_redirects=False)
    try:
        headers={"Authorization":"Bearer "+bearer}
        response=http.post(cfg.gateway+"/v1/device/enrollment/begin",headers=headers)
        response.raise_for_status()
        signer=Signer.generate_for_local_enrollment()
        data=signer.sign_enrollment(response.json());data["label"]=label
        response=http.post(cfg.gateway+"/v1/device/enrollment/finish",headers=headers,json=data)
        response.raise_for_status()
        ident=_id(response.json()["device_id"])
        save_identity(signer,cfg.gateway,ident)
        return ident
    except (httpx.HTTPError,TypeError,ValueError,KeyError) as exc:
        raise LinkError("Device enrollment failed without granting access") from exc
    finally:
        if own:http.close()

def current_link_status(path):
    try:
        o=json.loads(Path(path).read_text(encoding="utf-8"))
        paired=(isinstance(o,dict) and o.get("version")==1
                and isinstance(o.get("dpapi_key"),str)
                and public_https(o.get("origin")) and bool(_id(o.get("device_id"))))
    except (OSError,TypeError,ValueError,KeyError,AgentError):
        paired=False
    return {"paired":paired,"connected":False}

def bridge_once(origin,device_id,signer, *,native_permission=None,native_dispatch=None,http=None):
    if not callable(native_permission) or not callable(native_dispatch):
        raise LinkError("Local Windows policy and dispatcher required")
    return DeviceAgent(origin,device_id,signer,has_local_permission=native_permission,
                       dispatch_local=native_dispatch,http=http).poll_once()

def connect_windows(cfg,label, *,note=None,open_browser=None):
    from .windows_identity import default_identity_path,save_identity
    path=default_identity_path()
    if path.exists():raise LinkError("Device already paired; do not overwrite")
    from .oauth_pkce import authorize
    if note: note("Inicia sessão no navegador e confirma as permissões solicitadas.")
    bearer=authorize(cfg.issuer,cfg.client_id,open_browser=open_browser)
    return enroll_windows(cfg,bearer,label,save_identity=lambda signer,origin,ident:
                          save_identity(path,signer,origin,ident))

def run_agent(*,once=False,interval=3,stopped=None):
    from .windows_identity import default_identity_path,load_identity
    from .native_dispatch import NativeDispatcher
    origin,device_id,signer=load_identity(default_identity_path())
    native=NativeDispatcher()
    with httpx.Client(timeout=20,verify=True,follow_redirects=False) as client:
        while stopped is None or not stopped.is_set():
            try:bridge_once(origin,device_id,signer,native_permission=native.has_local_permission,
                            native_dispatch=native.dispatch_local,http=client)
            except httpx.HTTPError:pass
            if once:return
            if stopped is None:time.sleep(interval)
            else:stopped.wait(interval)
