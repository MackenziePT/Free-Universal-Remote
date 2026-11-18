"""Standalone public agent must use the owner's existing Windows policy.

No policy creation and no grant escalation. The Task Scheduler process does
not inherit HARMONY_MCP_CONFIG from the private MCP or the GUI process.
"""
import os
from pathlib import Path
import pytest
from cloud.public_link import LinkError, ensure_native_policy


def test_public_agent_resolves_canonical_existing_user_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.delenv("HARMONY_MCP_CONFIG",raising=False)
    target=tmp_path/"UniversalRemote"/"config.json"
    target.parent.mkdir()
    target.write_text('{"allowed_roots":[]}',encoding="utf-8")
    assert ensure_native_policy()==target
    assert os.environ["HARMONY_MCP_CONFIG"]==str(target)
    assert target.read_text(encoding="utf-8")=='{"allowed_roots":[]}'


def test_missing_policy_never_bootstraps_or_grants(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.delenv("HARMONY_MCP_CONFIG",raising=False)
    with pytest.raises(LinkError):
        ensure_native_policy()
    assert not list(tmp_path.glob("**/*"))
    assert "HARMONY_MCP_CONFIG" not in os.environ


def test_foreign_process_override_does_not_replace_canonical_policy(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    fake=tmp_path/"other.json"
    fake.write_text("{}",encoding="utf-8")
    monkeypatch.setenv("HARMONY_MCP_CONFIG",str(fake))
    with pytest.raises(LinkError):
        ensure_native_policy()
    assert os.environ["HARMONY_MCP_CONFIG"]==str(fake)
