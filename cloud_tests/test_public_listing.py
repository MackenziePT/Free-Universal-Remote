"""Public listing must link to truthful public documents and supported OAuth."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from cloud.app import preflight_app, create_app
from cloud.auth import Settings
from cloud.storage import Store

ORIGIN="https://universal-remote-free-production.up.railway.app"
ISSUER="https://hsztpgfgwlmnocealhcm.supabase.co/auth/v1"


def test_public_pages_suitable_for_directory_links():
    app=TestClient(preflight_app())
    for path in ("/about","/privacy","/terms","/support"):
        result=app.get(path)
        assert result.status_code==200, path
        assert result.headers["content-type"].startswith("text/html")
        assert result.headers["cache-control"]=="no-store"
        assert "frame-ancestors 'none'" in result.headers["content-security-policy"]
        assert "Universal Remote Free Unlimited" in result.text
        assert "password" not in result.text.lower()
        assert "<script" not in result.text.lower()


def test_privacy_notice_describes_real_data_categories():
    result=TestClient(preflight_app()).get("/privacy")
    for term in ("Supabase","Railway","DPAPI","24 horas","cinco minutos","revogação"):
        assert term in result.text


def test_prod_public_pages_require_no_oauth(tmp_path):
    class NoPrincipal:
        def principal(self,token):
            raise AssertionError("Listing pages must remain public")
    settings=Settings(ISSUER,"authenticated",ISSUER+"/.well-known/jwks.json",ORIGIN)
    storage=Store(tmp_path/"queue.sqlite3",bytes(range(32)))
    client=TestClient(create_app(settings,storage,NoPrincipal(),provider_mode="supabase"))
    for path in ("/about","/privacy","/terms","/support"):
        assert client.get(path).status_code == 200
    assert client.post("/v1/device/enrollment/begin",json={}).status_code==401


def test_submission_manifest_uses_supported_dcr_and_only_supported_scopes():
    root=Path(__file__).resolve().parents[1]/"distribution"/"chatgpt_public"
    mcp=json.loads((root/"mcp.json").read_text(encoding="utf-8"))
    entry=mcp["mcpServers"]["universal-remote-free"]
    auth=entry["extensions"]["com.openai"]["auth"]
    assert entry["url"]==ORIGIN+"/mcp"
    assert auth["type"]=="oauth"
    assert auth["client"]["mode"]=="dcr"
    assert auth["baseScopes"]==["openid","profile"]
    assert "ur:read" not in json.dumps(auth)
    meta=json.loads((root/"plugin.json").read_text(encoding="utf-8"))
    ui=meta["extensions"]["com.openai"]["interface"]
    for key,route in (("websiteURL","/about"),("privacyPolicyURL","/privacy"),
                      ("termsOfServiceURL","/terms"),("supportURL","/support")):
        assert ui[key]==ORIGIN+route
    assert ".app.json" not in [p.name for p in root.iterdir()]
