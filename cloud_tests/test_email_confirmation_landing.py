"""Email verification can redirect to SITE_URL even if the OTP was consumed."""
from fastapi.testclient import TestClient
from cloud.app import preflight_app
from cloud.auth import Settings
from cloud.storage import Store
from cloud.app import create_app

ORIGIN = "https://universal-remote-free-production.up.railway.app"
ISSUER = "https://hsztpgfgwlmnocealhcm.supabase.co/auth/v1"

def test_preflight_root_guides_confirmed_user_after_expired_link():
    client = TestClient(preflight_app())
    response = client.get("/?error=access_denied&error_code=otp_expired")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Universal Remote Free Unlimited" in response.text
    assert "otp_expired" in response.text
    assert "iniciar sessão" in response.text.lower()
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_landing_does_not_reflect_attacker_query_or_expired_link_tokens():
    client = TestClient(preflight_app())
    evil = "<img src=x onerror=alert(1)>"
    response = client.get("/", params={
        "error_description":evil,
        "access_token":"DO_NOT_EXPOSE_TOKEN",
        "error_code":"otp_expired",
    })
    assert response.status_code == 200
    assert evil not in response.text
    assert "DO_NOT_EXPOSE_TOKEN" not in response.text
    assert "Referrer-Policy".lower() in {k.lower() for k in response.headers}
    assert response.headers["referrer-policy"] == "no-referrer"


def test_confirmation_route_available_without_oauth_or_windows_privileges():
    client = TestClient(preflight_app())
    assert client.get("/auth/confirmed").status_code == 200
    assert client.post("/mcp",json={}).status_code == 503
    assert client.post("/v1/device/enrollment/begin",json={}).status_code == 404


def test_real_gateway_also_handles_email_confirmation(tmp_path):
    class RejectAll:
        def principal(self, token):
            raise AssertionError("Landing route must not attempt auth")
    settings = Settings(ISSUER,"authenticated", ISSUER+"/.well-known/jwks.json", ORIGIN)
    store = Store(tmp_path/"queue.sqlite3",bytes(range(32)))
    client=TestClient(create_app(settings,store,RejectAll(),provider_mode="supabase"))
    assert client.get("/?error_code=otp_expired").status_code == 200
    assert client.get("/auth/confirmed").status_code == 200
