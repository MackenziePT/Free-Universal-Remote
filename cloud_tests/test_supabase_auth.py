"""Supabase OAuth tokens have aud='authenticated' and no ur:* OAuth scopes.

Capabilities are assigned ONLY by a server-side allowlist of OAuth client IDs.
Neither arbitrary Supabase sessions nor unapproved OAuth clients may drive PCs.
"""
import hashlib
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

from cloud.auth import Settings, SupabaseOIDC, Unauthorized

ISSUER="https://hsztpgfgwlmnocealhcm.supabase.co/auth/v1"
ORIGIN="https://universal-remote-free-production.up.railway.app"


def world():
    key=generate_private_key(public_exponent=65537,key_size=2048)
    class Keys:
        def get_signing_key_from_jwt(self,raw):
            return SimpleNamespace(key=key.public_key())
    settings=Settings(ISSUER,"authenticated",ISSUER+"/.well-known/jwks.json",ORIGIN)
    permitted={"approved-client": frozenset({"ur:read","ur:devices"})}
    oidc=SupabaseOIDC(settings,client_capabilities=permitted,key_provider=Keys())
    def bearer(**claims):
        now=int(time.time())
        fields={"iss":ISSUER,"aud":"authenticated","sub":"test-user-uuid",
                "role":"authenticated","client_id":"approved-client",
                "session_id":"test-session-uuid","iat":now,"exp":now+600}
        fields.update(claims)
        return jwt.encode(fields,key,algorithm="RS256",headers={"kid":"test-kid"})
    return oidc,bearer


def test_allowed_client_signed_identity_uses_server_side_capabilities():
    oidc,bearer=world()
    user=oidc.principal(bearer())
    assert user.scopes==frozenset({"ur:read","ur:devices"})
    assert user.account==hashlib.sha256((ISSUER+"\0test-user-uuid").encode()).hexdigest()
    with pytest.raises(Unauthorized):
        user.requires("ur:shell")


@pytest.mark.parametrize("overrides",[
    {"client_id":"unapproved-client"},
    {"client_id":None},
    {"aud":"https://universal-remote-free-production.up.railway.app/mcp"},
    {"iss":"https://different.example.org/auth/v1"},
    {"role":"anon"},
    {"sub":""},
    {"session_id":None},
    {"is_anonymous":True},
])
def test_unapproved_client_or_untrusted_claim_denied(overrides):
    oidc,bearer=world()
    with pytest.raises(Unauthorized):
        oidc.principal(bearer(**overrides))


def test_untrusted_scope_claim_cannot_elevate_client():
    oidc,bearer=world()
    user=oidc.principal(bearer(scope="ur:shell ur:screen ur:input"))
    assert user.scopes==frozenset({"ur:read","ur:devices"})


def test_invalid_capability_grants_fail_configuration():
    oidc,bearer=world()
    with pytest.raises(ValueError):
        SupabaseOIDC(oidc.settings,client_capabilities={"approved-client":{"ur:root"}})
    with pytest.raises(ValueError):
        SupabaseOIDC(oidc.settings,client_capabilities={})



def test_supabase_mcp_discovery_uses_only_supported_oauth_scopes(tmp_path):
    from fastapi.testclient import TestClient
    from cloud.app import create_app
    from cloud.storage import Store
    oidc,_=world()
    store=Store(tmp_path/"queue.sqlite3",bytes(range(32)))
    client=TestClient(create_app(oidc.settings,store,oidc,provider_mode="supabase"))
    r=client.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
    assert r.status_code==200
    tools=r.json()["result"]["tools"]
    assert len(tools)>3
    assert all(t["securitySchemes"]==[{"type":"oauth2","scopes":["openid"]}] for t in tools)
    assert all(t["_meta"]["securitySchemes"]==t["securitySchemes"] for t in tools)
    metadata=client.get("/.well-known/oauth-protected-resource").json()
    assert metadata["resource"]==ORIGIN+"/mcp"
    assert metadata["scopes_supported"]==["openid","profile"]
    assert "ur:shell" not in metadata["scopes_supported"]


def test_supabase_token_without_client_shell_grant_cannot_queue_shell(tmp_path):
    from fastapi.testclient import TestClient
    from cloud.app import create_app
    from cloud.storage import Store
    oidc,bearer=world()
    store=Store(tmp_path/"queue.sqlite3",bytes(range(32)))
    client=TestClient(create_app(oidc.settings,store,oidc,provider_mode="supabase"))
    r=client.post("/mcp",headers={"Authorization":"Bearer "+bearer()},
       json={"jsonrpc":"2.0","id":1,"method":"tools/call",
             "params":{"name":"request_windows_powershell","arguments":{
                 "device_id":"00000000-0000-4000-8000-000000000000",
                 "command":"whoami",
                 "confirmation":"I understand this requires local Windows approval"}}})
    result=r.json()["result"]
    assert result["isError"] is True
    assert "structuredContent" not in result
    assert "mcp/www_authenticate" not in result.get("_meta",{})



def test_production_factory_refuses_supabase_without_signed_client_allowlist(tmp_path,monkeypatch):
    from cloud import app as gateway
    from cloud.storage import Store
    import base64
    monkeypatch.setenv("UR_REMOTE_CONTROL_ENABLED","true")
    monkeypatch.setenv("UR_AUTH_PROVIDER","supabase")
    monkeypatch.setenv("UR_QUEUE_KEY",base64.b64encode(bytes(range(32))).decode())
    monkeypatch.setenv("UR_OIDC_ISSUER",ISSUER)
    monkeypatch.setenv("UR_OIDC_AUDIENCE","authenticated")
    monkeypatch.setenv("UR_OIDC_JWKS_URL",ISSUER+"/.well-known/jwks.json")
    monkeypatch.setenv("UR_PUBLIC_ORIGIN",ORIGIN)
    monkeypatch.setenv("UR_GATEWAY_DB","/state/queue.sqlite3")
    monkeypatch.delenv("UR_SUPABASE_CLIENT_GRANTS_JSON",raising=False)
    monkeypatch.setattr(gateway,"Store",lambda path,key: Store(tmp_path/"queue.sqlite3",key))
    with pytest.raises((RuntimeError,ValueError,KeyError)):
        gateway.production_app()


def test_production_factory_accepts_only_explicitly_approved_clients(tmp_path,monkeypatch):
    from cloud import app as gateway
    from cloud.storage import Store
    from fastapi.testclient import TestClient
    import base64,json
    monkeypatch.setenv("UR_REMOTE_CONTROL_ENABLED","true")
    monkeypatch.setenv("UR_AUTH_PROVIDER","supabase")
    monkeypatch.setenv("UR_QUEUE_KEY",base64.b64encode(bytes(range(32))).decode())
    monkeypatch.setenv("UR_OIDC_ISSUER",ISSUER)
    monkeypatch.setenv("UR_OIDC_AUDIENCE","authenticated")
    monkeypatch.setenv("UR_OIDC_JWKS_URL",ISSUER+"/.well-known/jwks.json")
    monkeypatch.setenv("UR_PUBLIC_ORIGIN",ORIGIN)
    monkeypatch.setenv("UR_GATEWAY_DB","/state/queue.sqlite3")
    monkeypatch.setenv("UR_SUPABASE_CLIENT_GRANTS_JSON",json.dumps({"approved-client":["ur:read","ur:devices"]}))
    monkeypatch.setattr(gateway,"Store",lambda path,key: Store(tmp_path/"queue.sqlite3",key))
    app=gateway.production_app()
    client=TestClient(app)
    assert client.get("/healthz").status_code==200
    assert client.get("/.well-known/oauth-protected-resource").json()["scopes_supported"]==["openid","profile"]
