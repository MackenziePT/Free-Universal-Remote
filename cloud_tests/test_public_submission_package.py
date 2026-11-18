"""Verify public package does not accidentally ship owner's private MCP."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"distribution"/"chatgpt_public"

def test_portable_manifest_is_named_and_versioned():
    manifest=json.loads((DIR/"plugin.json").read_text(encoding="utf-8"))
    assert manifest["$schema"]=="https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"]=="universal-remote-free-unlimited"
    assert manifest["version"].startswith("1.1.0-rc.")
    assert manifest["extensions"]["com.openai"]["onboardingSkill"]=="./skills/setup-universal-remote/SKILL.md"
    assert manifest["extensions"]["com.openai"]["interface"]["displayName"]=="Universal Remote Free Unlimited"
    assert (DIR/"skills"/"setup-universal-remote"/"SKILL.md").is_file()

def test_remote_mcp_is_public_https_and_oauth_only():
    config=json.loads((DIR/"mcp.json").read_text(encoding="utf-8"))
    assert config["$schema"]=="https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    servers=config["mcpServers"]
    assert len(servers)==1
    server=next(iter(servers.values()))
    assert server["type"]=="streamable-http"
    assert server["url"]=="https://universal-remote-free-production.up.railway.app/mcp"
    auth=server["extensions"]["com.openai"]["auth"]
    assert auth["type"]=="oauth"
    # Current Supabase metadata advertises DCR and OIDC scopes, not CIMD/ur:read.
    assert auth["client"]["mode"]=="dcr"
    assert auth["baseScopes"]==["openid","profile"]
    assert "headers" not in server
    assert not any(s in (DIR/"plugin.json").read_text(encoding="utf-8") for s in ("private", "dev-6af", "plugin_asdk_app", ".app.json"))

def test_package_has_no_private_connections_or_secrets():
    assert not (DIR/".app.json").exists()
    for f in DIR.rglob("*"):
        if f.is_file():
            s=f.read_text(encoding="utf-8")
            for forbidden in ("sk-proj-", "tunnel_6ad", "key_NwAe", "private_tunnel_bridge", "C:\\Users\\shirt"):
                assert forbidden not in s, (str(f),forbidden)
