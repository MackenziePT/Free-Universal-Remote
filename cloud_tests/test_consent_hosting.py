from fastapi.testclient import TestClient
from cloud.app import preflight_app

def test_preflight_serves_usable_consent_html():
    c=TestClient(preflight_app())
    r=c.get("/oauth/consent?authorization_id=example-authorization-id")
    assert r.status_code==200
    assert r.headers["content-type"].startswith("text/html")
    assert "getAuthorizationDetails" in r.text
    assert "approveAuthorization" in r.text
    assert "denyAuthorization" in r.text
    assert "sb_secret_" not in r.text
    assert "service_role" not in r.text
    assert "sandbox" not in r.headers["content-security-policy"]
    assert r.headers["cache-control"]=="no-store"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]

def test_public_control_stays_blocked_while_consent_page_is_available():
    c=TestClient(preflight_app())
    assert c.post("/mcp",json={}).status_code==503
    assert c.get("/.well-known/oauth-protected-resource").status_code==503