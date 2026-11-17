"""Authenticated public Streamable HTTP MCP gateway for Universal Remote.

This component routes jobs, not Windows privileges. Sensitive operations MUST also
be approved by the local Windows agent at execution time. It does not bootstrap
an identity provider and never accesses the owner's existing private MCP tunnel.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from .auth import OIDC, Settings, Unauthorized, Principal
from .storage import Denied, Store, encode_json

VERSION = "0.2.0-rc-gateway"
PROTOCOLS = {"2025-03-26", "2025-06-18", "2025-11-25"}
DIAGNOSTICS = {"computer", "cpu", "gpu", "network", "memory_manager", "volumes"}


def b64_decode(raw: str, expected: int) -> bytes:
    try:
        output=base64.b64decode(raw,validate=True)
    except (ValueError,TypeError) as exc:
        raise Denied("Invalid base64") from exc
    if len(output)!=expected:
        raise Denied("Invalid key/signature length")
    return output


def uuid4(value: str) -> str:
    try:
        parsed=uuid.UUID(value)
    except (ValueError,TypeError,AttributeError) as exc:
        raise Denied("Invalid identifier") from exc
    if parsed.version!=4 or str(parsed)!=value:
        raise Denied("Canonical UUIDv4 required")
    return value


TOOL_DEFS = [
    {"name":"list_windows_devices", "description":"List only the signed-in account's enrolled Windows devices. Never exposes other accounts' devices.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False},
     "annotations":{"title":"List my Windows devices","readOnlyHint":True,"openWorldHint":False,"destructiveHint":False}},
    {"name":"get_windows_device", "description":"Check whether one of my own enrolled Windows devices has contacted the gateway recently.",
     "inputSchema":{"type":"object","properties":{"device_id":{"type":"string"}},"required":["device_id"],"additionalProperties":False},
     "annotations":{"title":"Check Windows device","readOnlyHint":True,"openWorldHint":False,"destructiveHint":False}},
    {"name":"request_windows_diagnostic", "description":"Queue a bounded Windows diagnostic from my enrolled device. Requires a live locally approved agent. Returns an operation ID; poll the result separately.",
     "inputSchema":{"type":"object","properties":{"device_id":{"type":"string"},"diagnostic":{"type":"string","enum":sorted(DIAGNOSTICS)}},"required":["device_id","diagnostic"],"additionalProperties":False},
     "annotations":{"title":"Request Windows diagnostics","readOnlyHint":False,"openWorldHint":False,"destructiveHint":False}},
    {"name":"request_windows_file_read", "description":"Queue a file read inside the Windows agent's locally allowed roots. Cloud access never expands those roots. May return sensitive file contents; requester must be authorized.",
     "inputSchema":{"type":"object","properties":{"device_id":{"type":"string"},"path":{"type":"string","minLength":1,"maxLength":1000}},"required":["device_id","path"],"additionalProperties":False},
     "annotations":{"title":"Read authorized Windows file","readOnlyHint":False,"openWorldHint":False,"destructiveHint":False}},
    {"name":"request_windows_powershell", "description":"Queue a PowerShell command on my Windows PC. Never runs without the Windows owner's separate fresh local shell grant. This can change files or system state.",
     "inputSchema":{"type":"object","properties":{"device_id":{"type":"string"},"command":{"type":"string","minLength":1,"maxLength":12000},"confirmation":{"type":"string","enum":["I understand this requires local Windows approval"]}},"required":["device_id","command","confirmation"],"additionalProperties":False},
     "annotations":{"title":"Request locally approved PowerShell","readOnlyHint":False,"openWorldHint":True,"destructiveHint":True}},
    {"name":"request_windows_screenshot", "description":"Queue capture of my Windows display. Requires a separate fresh local screen permission; can reveal private content.",
     "inputSchema":{"type":"object","properties":{"device_id":{"type":"string"},"monitor":{"type":"integer","minimum":1,"maximum":8}},"required":["device_id"],"additionalProperties":False},
     "annotations":{"title":"Request locally approved screenshot","readOnlyHint":False,"openWorldHint":False,"destructiveHint":False}},
    {"name":"request_windows_input", "description":"Queue a mouse click, Unicode text input or restricted key press on my enrolled PC. Requires an independent fresh local Windows input grant. May change applications or send text.",
     "inputSchema":{"type":"object","properties":{"device_id":{"type":"string"},"action":{"type":"string","enum":["click","type","press"]},"x":{"type":"integer"},"y":{"type":"integer"},"text":{"type":"string","maxLength":500},"confirmation":{"type":"string","enum":["I understand this requires local Windows approval"]}},"required":["device_id","action","confirmation"],"additionalProperties":False},
     "annotations":{"title":"Request locally approved mouse or keyboard action","readOnlyHint":False,"openWorldHint":True,"destructiveHint":True}},
    {"name":"get_windows_operation", "description":"Retrieve the status or output of my previously queued Windows operation by ID. Other users' operation IDs do not work.",
     "inputSchema":{"type":"object","properties":{"operation_id":{"type":"string"}},"required":["operation_id"],"additionalProperties":False},
     "annotations":{"title":"Get Windows operation","readOnlyHint":True,"openWorldHint":False,"destructiveHint":False}},
    {"name":"revoke_windows_device", "description":"Permanently revoke one of my paired device identities at this gateway and invalidate its queued operations.",
     "inputSchema":{"type":"object","properties":{"device_id":{"type":"string"},"confirmation":{"type":"string","enum":["REVOKE DEVICE"]}},"required":["device_id","confirmation"],"additionalProperties":False},
     "annotations":{"title":"Revoke Windows device","readOnlyHint":False,"openWorldHint":False,"destructiveHint":True}},
]
# Expose the exact OAuth permission required for each tool to ChatGPT.
# Read-only tool discovery does not imply any access to a Windows device.
TOOL_SCOPES = {
    "list_windows_devices": ["ur:read"],
    "get_windows_device": ["ur:read"],
    "get_windows_operation": ["ur:read"],
    "revoke_windows_device": ["ur:read", "ur:devices"],
    "request_windows_diagnostic": ["ur:read", "ur:control"],
    "request_windows_file_read": ["ur:read", "ur:control"],
    "request_windows_powershell": ["ur:read", "ur:shell"],
    "request_windows_screenshot": ["ur:read", "ur:screen"],
    "request_windows_input": ["ur:read", "ur:input"],
    "get_profile": ["ur:read"],
}
TOOL_DEFS.append({
    "name": "get_profile",
    "description": "Return the stable, opaque profile id from the signed-in account. Never returns another user's profile.",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "outputSchema": {"$schema": "https://json-schema.org/draft/2020-12/schema",
                     "type": "object", "properties": {"id": {
                         "type": "string", "minLength": 1, "pattern": r"\S"}},
                     "required": ["id"], "additionalProperties": False},
    "annotations": {"title": "My Universal Remote profile", "readOnlyHint": True,
                    "openWorldHint": False, "destructiveHint": False},
    "_meta": {"openai/profile": True},
})
for _description in TOOL_DEFS:
    _schemes = [{"type": "oauth2", "scopes": TOOL_SCOPES[_description["name"]]}]
    _description["securitySchemes"] = _schemes
    _description.setdefault("_meta", {})["securitySchemes"] = _schemes

TOOLS={t["name"]:t for t in TOOL_DEFS}


def create_app(settings: Settings, store: Store, oidc: OIDC, *, clock=time.time,
               challenge_token: Optional[str]=None, provider_mode: str="oidc") -> FastAPI:
    if provider_mode not in ("oidc","supabase"):
        raise ValueError("Unknown OAuth provider mode")
    # Supabase supports only OIDC profile scopes, not ur:* OAuth scopes.
    # All Windows privileges remain governed by signed OAuth client ID and
    # independent native local grants; do not suggest unsupported elevation.
    public_tools=json.loads(json.dumps(TOOL_DEFS))
    if provider_mode=="supabase":
        for tool in public_tools:
            schemes=[{"type":"oauth2","scopes":["openid"]}]
            tool["securitySchemes"]=schemes
            tool.setdefault("_meta",{})["securitySchemes"]=schemes
    app=FastAPI(title="Universal Remote Public MCP",version=VERSION,
                docs_url=None,redoc_url=None,openapi_url=None)

    async def capped_body(request: Request, max_bytes: int) -> bytes:
        # Content-Length can be absent for chunked requests; enforce an actual
        # streaming limit before buffering or deserializing untrusted payloads.
        pieces=bytearray()
        async for chunk in request.stream():
            if len(chunk)>max_bytes-len(pieces):
                raise HTTPException(413, "Payload too large")
            pieces.extend(chunk)
        return bytes(pieces)

    @app.middleware("http")
    async def headers(request: Request, next_call):
        # Only an HTTPS edge is permitted on a public origin. Health checks arrive
        # HTTP internally on Railway; the proxy must strip forged Forwarded headers.
        if request.url.path != "/healthz" and request.headers.get("x-forwarded-proto") not in (None,"https"):
            return JSONResponse({"error":"HTTPS required"},status_code=426)
        # Browser-originated cross-site requests are forbidden; ChatGPT's
        # server-to-server MCP requests normally omit Origin entirely.
        origin=request.headers.get("origin")
        if origin and origin not in ("https://chatgpt.com","https://chat.openai.com",settings.public_origin):
            return JSONResponse({"error":"Untrusted origin"},status_code=403)
        raw_length=request.headers.get("content-length")
        if raw_length is not None:
            try:
                declared=int(raw_length)
            except ValueError:
                return JSONResponse({"error":"Invalid content length"},status_code=400)
            max_len=2_500_000 if request.url.path.endswith("/result") else 150_000
            if declared<0 or declared>max_len:
                return JSONResponse({"error":"Payload too large"},status_code=413)
        response=await next_call(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["Strict-Transport-Security"]="max-age=31536000"
        return response

    def principal(authorization: Optional[str]) -> Principal:
        if not authorization or not authorization.startswith("Bearer ") or authorization.count(" ")!=1:
            raise HTTPException(401,"OAuth authorization required",headers={
                "WWW-Authenticate":f'Bearer resource_metadata="{settings.public_origin}/.well-known/oauth-protected-resource"'})
        try:
            return oidc.principal(authorization[7:])
        except Unauthorized:
            raise HTTPException(401,"OAuth authorization required",headers={
                "WWW-Authenticate":f'Bearer resource_metadata="{settings.public_origin}/.well-known/oauth-protected-resource"'}) from None

    def verify_device(device_id: str, raw: bytes, method: str, path: str, headers):
        # Each request is bound to an enrolled Ed25519 key and unique nonce.
        uuid4(device_id)
        nonce=uuid4(headers.get("x-ur-nonce"))
        timestamp=headers.get("x-ur-timestamp")
        try:
            stamp=int(timestamp)
        except (TypeError, ValueError) as exc:
            raise Denied("Invalid signed timestamp") from exc
        now=int(clock())
        if not re.fullmatch(r"\d{10,12}",timestamp) or abs(now-stamp)>60:
            raise Denied("Expired signed request")
        signature=b64_decode(headers.get("x-ur-signature"),64)
        content=encode_json({"domain":"universal-remote-agent/v1", "device_id":device_id,
                             "nonce":nonce,"timestamp":stamp,"method":method,
                             "path":path,"sha256":hashlib.sha256(raw).hexdigest()})
        try:
            Ed25519PublicKey.from_public_bytes(store.get_public_key(device_id)).verify(signature,content)
        except InvalidSignature as exc:
            raise Denied("Device signature invalid") from exc
        store.accept_nonce(device_id,nonce,now)

    def invoke(name, arguments, user: Principal):
        if not isinstance(arguments,dict) or name not in TOOLS:
            raise Denied("Unknown tool or invalid arguments")
        schema=TOOLS[name]["inputSchema"]
        if not set(arguments).issubset(schema["properties"]) or not set(schema.get("required",[])).issubset(arguments):
            raise Denied("Unknown or missing tool input")
        user.requires("ur:read")
        owner=user.account
        if name=="get_profile":
            return {"id": owner}
        if name=="list_windows_devices":
            return {"devices":store.list_devices(owner)}
        if name=="get_windows_device":
            return store.find_device(owner,uuid4(arguments["device_id"]))
        if name=="get_windows_operation":
            return store.operation(owner,uuid4(arguments["operation_id"]))
        if name=="revoke_windows_device":
            user.requires("ur:devices")
            if arguments["confirmation"]!="REVOKE DEVICE":
                raise Denied("Explicit device revocation confirmation required")
            store.revoke(owner,uuid4(arguments["device_id"]))
            return {"revoked":True}
        device_id=uuid4(arguments["device_id"])
        if name=="request_windows_diagnostic":
            user.requires("ur:control")
            diag=arguments["diagnostic"]
            if not isinstance(diag,str) or diag not in DIAGNOSTICS:
                raise Denied("Unsupported diagnostic")
            op="windows_diagnostic";args={"name":diag}
        elif name=="request_windows_file_read":
            user.requires("ur:control")
            path=arguments["path"]
            if not isinstance(path,str) or not (1<=len(path)<=1000):
                raise Denied("Invalid path")
            op="read_text_file";args={"path":path}
        elif name=="request_windows_powershell":
            user.requires("ur:shell")
            if arguments["confirmation"]!="I understand this requires local Windows approval":
                raise Denied("Local-approval requirement must be acknowledged")
            cmd=arguments["command"]
            if not isinstance(cmd,str) or not (1<=len(cmd)<=12000):
                raise Denied("Invalid shell command")
            op="run_powershell"; args={"command":cmd,"operation_id":str(uuid.uuid4())}
        elif name=="request_windows_input":
            user.requires("ur:input")
            if arguments["confirmation"]!="I understand this requires local Windows approval":
                raise Denied("Local Windows input approval must be acknowledged")
            action=arguments["action"]
            if not isinstance(action,str) or action not in ("click","type","press"):
                raise Denied("Unknown or unsafe desktop action")
            x=arguments.get("x",0);y=arguments.get("y",0)
            text=arguments.get("text","")
            if type(x) is not int or type(y) is not int or not(-100000<=x<=100000 and -100000<=y<=100000):
                raise Denied("Invalid screen coordinates")
            if action=="click" and not set(("x","y")).issubset(arguments):
                raise Denied("Click coordinates required")
            if action=="type" and (not isinstance(text,str) or not 1<=len(text)<=500):
                raise Denied("Invalid input text")
            if action=="press" and text not in {"enter","esc","tab","up","down","left","right","backspace"}:
                raise Denied("Input key not in approved set")
            if action=="click" and text:
                raise Denied("Click must not carry text")
            op="desktop_action";args={"action":action,"x":x,"y":y,"text":text,"operation_id":str(uuid.uuid4())}
        elif name=="request_windows_screenshot":
            user.requires("ur:screen")
            mon=arguments.get("monitor",1)
            if type(mon) is not int or not(1<=mon<=8):
                raise Denied("Invalid monitor")
            op="desktop_screenshot";args={"monitor":mon,"max_width":1200}
        else:
            raise Denied("Unsupported operation")
        return {"operation_id":store.submit(owner,device_id,op,args),"status":"queued",
                "notice":"Execution still requires independent local Windows authorization."}

    @app.get("/oauth/consent")
    def consent_page():
        from .consent_ui import consent_html_response
        return consent_html_response()

    @app.get("/healthz")
    def health():
        return {"service":"universal-remote", "version":VERSION,"status":"gateway-running", "windows_access":"requires-owner-grant"}

    @app.get("/.well-known/oauth-protected-resource")
    def oauth_metadata():
        return {"resource":settings.public_origin+"/mcp" if provider_mode=="supabase" else settings.audience,
                "authorization_servers":[settings.issuer],
                "scopes_supported":["openid","profile"] if provider_mode=="supabase" else
                    ["openid","profile","ur:read","ur:control","ur:shell","ur:screen","ur:input","ur:devices"]}

    @app.get("/.well-known/openai-apps-challenge")
    def challenge():
        if not challenge_token:
            raise HTTPException(404,"Domain verification not configured")
        return PlainTextResponse(challenge_token)

    @app.post("/v1/device/enrollment/begin")
    async def enroll_begin(request: Request, authorization: Optional[str]=Header(default=None)):
        user=principal(authorization)
        try:
            user.requires("ur:devices")
        except Unauthorized:
            raise HTTPException(403,"Insufficient OAuth scope") from None
        try:
            ident,random_bytes,expires=store.begin_enrollment(user.account)
        except Denied:
            raise HTTPException(429,"Too many enrollment requests") from None
        return {"id":ident, "owner":user.account,
                "challenge":base64.b64encode(random_bytes).decode(),"expires":expires}

    @app.post("/v1/device/enrollment/finish")
    async def enroll_finish(request: Request, authorization: Optional[str]=Header(default=None)):
        user=principal(authorization)
        try:
            user.requires("ur:devices")
        except Unauthorized:
            raise HTTPException(403,"Insufficient OAuth scope") from None
        owner=user.account
        try:
            obj=json.loads(await capped_body(request,150_000))
        except (ValueError,UnicodeError):
            raise HTTPException(400,"Invalid enrollment JSON") from None
        if not isinstance(obj,dict) or set(obj)!={"id","public_key","signature","label"}:
            raise HTTPException(400,"Invalid enrollment payload")
        try:
            ident=store.enroll(owner,uuid4(obj["id"]), b64_decode(obj["public_key"],32),
                               b64_decode(obj["signature"],64),obj["label"])
            return {"device_id":ident}
        except Denied as exc:
            raise HTTPException(403,str(exc)) from None

    @app.get("/v1/agent/{device_id}/poll")
    async def poll(device_id: str,request: Request):
        try:
            path=f"/v1/agent/{device_id}/poll"
            verify_device(device_id,b"", "GET",path,request.headers)
            return {"job":store.poll(device_id)}
        except Denied:
            raise HTTPException(401,"Agent authentication failed") from None

    @app.post("/v1/agent/{device_id}/result")
    async def result(device_id:str,request:Request):
        raw=await capped_body(request,2_500_000)
        try:
            path=f"/v1/agent/{device_id}/result"
            verify_device(device_id,raw,"POST",path,request.headers)
            obj=json.loads(raw)
            if not isinstance(obj,dict) or set(obj)!={"operation_id","ok","output"} or type(obj["ok"]) is not bool:
                raise Denied("Invalid result")
            store.complete(device_id,uuid4(obj["operation_id"]),obj["output"],obj["ok"])
            return {"acknowledged":True}
        except (Denied, json.JSONDecodeError):
            raise HTTPException(401,"Agent request denied") from None

    @app.post("/mcp")
    async def mcp(request:Request,authorization: Optional[str]=Header(default=None)):
        # Initialization and tool discovery are safe without a token; execution
        # never is. Otherwise ChatGPT cannot discover per-tool auth policies.
        try:
            data=json.loads(await capped_body(request,150_000))
        except (ValueError,UnicodeError):
            return JSONResponse({"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":"Parse error"}},status_code=400)
        if not isinstance(data,dict) or data.get("jsonrpc")!="2.0" or not isinstance(data.get("method"),str):
            return JSONResponse({"jsonrpc":"2.0","id":None,"error":{"code":-32600,"message":"Invalid request"}},status_code=400)
        ident=data.get("id")
        method=data["method"]
        if method.startswith("notifications/"):
            return Response(status_code=202)
        if not (isinstance(ident,int) or isinstance(ident,str)) or type(ident) is bool:
            return JSONResponse({"jsonrpc":"2.0","id":None,"error":{"code":-32600,"message":"Invalid request"}},status_code=400)
        params=data.get("params", {})
        owner=None
        if method=="tools/call":
            try:
                owner=principal(authorization)
            except HTTPException:
                auth_header=(f'Bearer resource_metadata="{settings.public_origin}/.well-known/oauth-protected-resource", '
                             'error="invalid_token", error_description="Sign in to Universal Remote"')
                result={"isError":True,
                        "content":[{"type":"text","text":"Universal Remote sign-in required"}],
                        "_meta":{"mcp/www_authenticate":[auth_header]}}
                return JSONResponse({"jsonrpc":"2.0","id":ident,"result":result},
                                    headers={"MCP-Protocol-Version":"2025-06-18"})
        try:
            if method=="initialize":
                payload={"protocolVersion":"2025-06-18", "capabilities":{"tools":{"listChanged":False}},
                         "serverInfo":{"name":"universal-remote-public","version":VERSION},
                         "instructions":"Owner-approved Windows tools. Local permissions cannot be overridden by this server."}
            elif method=="ping":
                payload={}
            elif method=="tools/list":
                payload={"tools":public_tools}
            elif method=="tools/call":
                params=data.get("params",{})
                if not isinstance(params,dict):
                    raise Denied("Invalid tool call")
                value=invoke(params.get("name"),params.get("arguments",{}),owner)
                payload={"content":[{"type":"text","text":json.dumps(value,ensure_ascii=False)}],
                         "structuredContent":value,"isError":False}
            else:
                return JSONResponse({"jsonrpc":"2.0","id":ident,"error":{"code":-32601,"message":"Method not found"}})
        except Unauthorized:
            if provider_mode=="supabase":
                payload={"content":[{"type":"text","text":"Operation denied by publisher-defined client grants"}],
                         "isError":True}
            else:
                requested=params.get("name") if isinstance(params,dict) else None
                scopes=TOOL_SCOPES.get(requested, ["ur:read"])
                challenge=(f'Bearer resource_metadata="{settings.public_origin}/.well-known/oauth-protected-resource", '
                           'error="insufficient_scope", error_description="Additional Universal Remote permission required", '
                           f'scope="{" ".join(scopes)}"')
                payload={"content":[{"type":"text","text":"Additional authorization required"}],
                         "isError":True,"_meta":{"mcp/www_authenticate":[challenge]}}
        except (Denied,KeyError,TypeError,ValueError) as exc:
            payload={"content":[{"type":"text","text":"Operation denied or unavailable"}],"isError":True}
            if method!="tools/call":
                return JSONResponse({"jsonrpc":"2.0","id":ident,"error":{"code":-32602,"message":"Invalid parameters"}})
        return JSONResponse({"jsonrpc":"2.0","id":ident,"result":payload},media_type="application/json",
                            headers={"MCP-Protocol-Version":"2025-06-18"})

    return app


def preflight_app() -> FastAPI:
    """Serve only readiness and domain challenge until real OAuth is configured.

    Never expose MCP tools or device enrollment in pre-production mode.
    """
    preview = FastAPI(title="Universal Remote Deployment Preflight",
                      docs_url=None, redoc_url=None, openapi_url=None)

    @preview.get("/oauth/consent")
    def consent_page():
        from .consent_ui import consent_html_response
        return consent_html_response()

    @preview.get("/healthz")
    def healthz():
        return JSONResponse({"service": "universal-remote", "status": "awaiting-oauth",
                             "ready": False, "remote_control": False},
                            headers={"Cache-Control": "no-store"})

    @preview.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    def mcp_unavailable():
        return JSONResponse({"error": "MCP unavailable until OAuth and device control are configured"},
                            status_code=503, headers={"Cache-Control": "no-store",
                                                      "Retry-After": "3600"})

    @preview.get("/.well-known/oauth-protected-resource")
    def oauth_unavailable():
        return JSONResponse({"error": "OAuth not configured"}, status_code=503,
                            headers={"Cache-Control": "no-store"})

    @preview.get("/.well-known/openai-apps-challenge")
    def domain_challenge():
        token = os.environ.get("UR_DOMAIN_CHALLENGE")
        if not token:
            raise HTTPException(404, "Domain verification not configured")
        return PlainTextResponse(token, headers={"Cache-Control": "no-store"})

    return preview


def production_app() -> FastAPI:
    if os.environ.get("UR_REMOTE_CONTROL_ENABLED") != "true":
        return preflight_app()
    import base64
    key=base64.b64decode(os.environ["UR_QUEUE_KEY"],validate=True)
    settings=Settings.from_env()
    database=os.environ["UR_GATEWAY_DB"]
    if not database.startswith("/state/"):
        raise RuntimeError("Production SQLite must reside on persistent /state mount")
    provider=os.environ.get("UR_AUTH_PROVIDER","oidc")
    if provider=="supabase":
        from .auth import SupabaseOIDC
        # The allowlist is publisher-controlled, never a JWT claim or user-input
        # permission. An empty/malformed list MUST prevent the service starting.
        grants=json.loads(os.environ["UR_SUPABASE_CLIENT_GRANTS_JSON"])
        oidc=SupabaseOIDC(settings,client_capabilities=grants)
    elif provider=="oidc":
        oidc=OIDC(settings)
    else:
        raise ValueError("Unknown authentication provider")
    return create_app(settings,Store(Path(database),key),oidc,
                      challenge_token=os.environ.get("UR_DOMAIN_CHALLENGE"),
                      provider_mode=provider)
