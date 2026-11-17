"""Production startup must fail closed until the actual OAuth integration is ready."""
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cloud.app import production_app


def test_preflight_serves_health_without_activating_control():
    with patch.dict(os.environ, {}, clear=True):
        client = TestClient(production_app())
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {
            "service": "universal-remote",
            "status": "awaiting-oauth",
            "ready": False,
            "remote_control": False,
        }
        assert response.headers["cache-control"] == "no-store"


def test_preflight_never_exposes_mcp_or_enrollment():
    with patch.dict(os.environ, {}, clear=True):
        client = TestClient(production_app())
        for method in ("GET", "POST", "DELETE"):
            assert client.request(method, "/mcp").status_code == 503
        assert client.get("/.well-known/oauth-protected-resource").status_code == 503
        assert client.post("/v1/device/enrollment/begin").status_code == 404
        assert client.get("/v1/agent/00000000-0000-4000-8000-000000000000/poll").status_code == 404


def test_domain_challenge_only_when_explicitly_configured():
    with patch.dict(os.environ, {}, clear=True):
        assert TestClient(production_app()).get("/.well-known/openai-apps-challenge").status_code == 404
    with patch.dict(os.environ, {"UR_DOMAIN_CHALLENGE": "owner-generated-verification-token"}, clear=True):
        r = TestClient(production_app()).get("/.well-known/openai-apps-challenge")
        assert r.status_code == 200
        assert r.text == "owner-generated-verification-token"


def test_enabled_remote_control_requires_real_production_secrets():
    with patch.dict(os.environ, {"UR_REMOTE_CONTROL_ENABLED": "true"}, clear=True):
        with pytest.raises(KeyError):
            production_app()
