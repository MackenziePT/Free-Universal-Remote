"""Public Windows binaries must ship their registered, non-secret OAuth client."""
from pathlib import Path
from cloud.public_link import LinkConfig

def test_registered_provider_configuration(monkeypatch):
    for key in ("UR_PUBLIC_ORIGIN","UR_OIDC_ISSUER","UR_WINDOWS_OAUTH_CLIENT_ID"):
        monkeypatch.delenv(key,raising=False)
    cfg=LinkConfig.from_env()
    assert cfg.gateway=="https://universal-remote-free-production.up.railway.app"
    assert cfg.issuer=="https://hsztpgfgwlmnocealhcm.supabase.co/auth/v1"
    assert cfg.client_id=="d37e9704-e390-4c1d-be70-57743eeec0ed"

def test_pyinstaller_bundles_public_oauth_client():
    text=(Path(__file__).parents[1]/"tools"/"build_public_prototype.py").read_text(encoding="utf-8")
    assert '"--add-data"' in text
    assert 'public_link_settings.json' in text
    assert '"--hidden-import","cloud.oauth_pkce"' in text
