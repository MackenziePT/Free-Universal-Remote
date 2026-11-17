"""Supabase supports Authorization Code + PKCE, NOT OAuth device-code grant."""
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock
import pytest

from cloud.oauth_pkce import PKCEError, create_request, exchange_code, authorize

ISSUER = "https://hsztpgfgwlmnocealhcm.supabase.co/auth/v1"
ORIGIN = "https://hsztpgfgwlmnocealhcm.supabase.co"


def test_pkce_request_uses_random_state_and_s256():
    a = create_request(ISSUER, "windows-client", "http://127.0.0.1:8765/oauth/callback")
    b = create_request(ISSUER, "windows-client", "http://127.0.0.1:8765/oauth/callback")
    q = parse_qs(urlsplit(a.authorization_url).query)
    assert urlsplit(a.authorization_url).path == "/auth/v1/oauth/authorize"
    assert q["response_type"] == ["code"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["scope"] == ["openid profile"]
    assert q["state"] == [a.state] and a.state != b.state
    assert a.verifier != b.verifier
    assert "client_secret" not in q


def test_require_loopback_callback_and_https_provider():
    with pytest.raises(PKCEError):
        create_request(ISSUER, "windows-client", "https://evil.example/callback")
    with pytest.raises(PKCEError):
        create_request("http://auth.example.com", "windows-client", "http://127.0.0.1:8765/oauth/callback")


def test_exchange_requires_verified_token_response():
    mock = Mock()
    response = Mock(status_code=200)
    response.json.return_value = {"access_token":"a"*32,"token_type":"Bearer"}
    mock.post.return_value = response
    request = create_request(ISSUER, "windows-client", "http://127.0.0.1:8765/oauth/callback")
    token = exchange_code(request,"sample-code",mock)
    assert token == "a"*32
    args = mock.post.call_args
    assert args.kwargs["data"]["code_verifier"] == request.verifier
    assert args.kwargs["data"]["grant_type"] == "authorization_code"
    assert "client_secret" not in args.kwargs["data"]
    response.json.return_value = {"access_token":"a"*32,"token_type":"token"}
    with pytest.raises(PKCEError):
        exchange_code(request,"sample-code",mock)


def test_authorize_aborts_when_issuer_discovery_mismatch():
    mock = Mock()
    mock.get.return_value.json.return_value={"issuer":"https://evil.example.org"}
    mock.get.return_value.raise_for_status.return_value = None
    with pytest.raises(PKCEError):
        authorize(ISSUER,"windows-client",http=mock,open_browser=lambda _:True,
                  wait_callback=lambda _: "sample-code")
    mock.post.assert_not_called()


def test_authorize_rejects_bad_state():
    mock = Mock()
    mock.get.return_value.json.return_value={
        "issuer":ISSUER,
        "authorization_endpoint":ISSUER+"/oauth/authorize",
        "token_endpoint":ISSUER+"/oauth/token",
        "grant_types_supported":["authorization_code","refresh_token"],
    }
    mock.get.return_value.raise_for_status.return_value = None
    with pytest.raises(PKCEError):
        authorize(ISSUER,"windows-client",http=mock,open_browser=lambda _:True,
                  wait_callback=lambda request: {"state":"incorrect","code":"code"})
    mock.post.assert_not_called()


def test_authorize_exchanges_code_with_callback_state():
    mock = Mock()
    mock.get.return_value.json.return_value = {
        "issuer":ISSUER,
        "authorization_endpoint":ISSUER+"/oauth/authorize",
        "token_endpoint":ISSUER+"/oauth/token",
        "grant_types_supported":["authorization_code","refresh_token"],
    }
    mock.get.return_value.raise_for_status.return_value = None
    response = Mock(status_code=200)
    response.json.return_value={"access_token":"v"*32,"token_type":"bearer"}
    mock.post.return_value=response
    browser=[]
    result=authorize(ISSUER,"windows-client",http=mock,
                     open_browser=lambda url: browser.append(url) or True,
                     wait_callback=lambda req:{"state":req.state,"code":"short-lived-code"})
    assert result=="v"*32
    assert browser and "/auth/v1/oauth/authorize?" in browser[0]



def test_connect_windows_uses_pkce_not_unsupported_device_grant(tmp_path, monkeypatch):
    import cloud.public_link as link
    import cloud.oauth_pkce as pkce
    import cloud.windows_identity as identity
    from cloud.public_link import LinkConfig
    cfg=LinkConfig("https://remote.example.org",ISSUER,"windows-client")
    monkeypatch.setattr(identity,"default_identity_path",lambda:tmp_path/"identity.json")
    monkeypatch.setattr(identity,"save_identity",lambda *args: None)
    monkeypatch.setattr(link,"device_authorize",
                        lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("Unsupported device grant")))
    attempts=[]
    monkeypatch.setattr(pkce,"authorize",lambda issuer,client_id,**kwargs:
                        attempts.append((issuer,client_id)) or "valid-token-"+("x"*32))
    monkeypatch.setattr(link,"enroll_windows",lambda cfg,token,label,**kw: "device-enrolled")
    assert link.connect_windows(cfg,"My PC")=="device-enrolled"
    assert attempts==[(ISSUER,"windows-client")]



def test_real_browser_is_opened_only_after_loopback_receiver_is_ready(monkeypatch):
    import cloud.oauth_pkce as pkce
    mock=Mock()
    mock.get.return_value.json.return_value={
        "issuer":ISSUER,"authorization_endpoint":ISSUER+"/oauth/authorize",
        "token_endpoint":ISSUER+"/oauth/token",
        "grant_types_supported":["authorization_code","refresh_token"]
    }
    mock.get.return_value.raise_for_status.return_value=None
    response=Mock(status_code=200)
    response.json.return_value={"access_token":"b"*32,"token_type":"Bearer"}
    mock.post.return_value=response
    events=[]
    def pretend_receiver(req,*,open_browser):
        events.append("listening")
        open_browser(req.authorization_url)
        return {"state":req.state,"code":"ok"}
    monkeypatch.setattr(pkce,"_loopback_callback",pretend_receiver)
    result=pkce.authorize(ISSUER,"windows-client",http=mock,
                          open_browser=lambda _:events.append("browser") or True)
    assert result=="b"*32
    assert events==["listening","browser"]
