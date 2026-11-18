"""Public connection reports real recent signed contact, never fake online state."""
import json
import os
import time
import uuid
import pytest
from cloud.public_link import current_link_status
from cloud.agent_runtime import update_heartbeat, single_agent_lock, AgentAlreadyRunning


def _identity(path, device):
    path.write_text(json.dumps({"version":1,"origin":"https://remote.example.org",
        "device_id":device,"dpapi_key":"encrypted-placeholder"}),encoding="utf-8")


def test_recent_signed_contact_reports_connected(tmp_path):
    device=str(uuid.uuid4())
    path=tmp_path/"device_identity.json"
    _identity(path,device)
    stamp=time.time()
    update_heartbeat(path,device,connected=True,now=stamp)
    result=current_link_status(path)
    assert result["paired"] is True
    assert result["connected"] is True
    assert result["last_contact_utc"] >= stamp - 1


def test_old_contact_must_not_report_online(tmp_path):
    device=str(uuid.uuid4())
    path=tmp_path/"device_identity.json"
    _identity(path,device)
    update_heartbeat(path,device,connected=True,now=time.time()-120)
    assert current_link_status(path)["connected"] is False


def test_failed_poll_and_cross_device_cannot_fake_connection(tmp_path):
    device=str(uuid.uuid4())
    path=tmp_path/"device_identity.json"
    _identity(path,device)
    update_heartbeat(path,device,connected=True)
    update_heartbeat(path,device,connected=False)
    assert current_link_status(path)["connected"] is False
    update_heartbeat(path,str(uuid.uuid4()),connected=True)
    assert current_link_status(path)["connected"] is False


def test_no_plaintext_identity_material_in_heartbeat(tmp_path):
    device=str(uuid.uuid4())
    path=tmp_path/"device_identity.json"
    _identity(path,device)
    update_heartbeat(path,device,connected=True)
    raw=(tmp_path/"connection_status.json").read_text()
    assert "dpapi" not in raw.lower()
    assert "token" not in raw.lower()
    assert "private" not in raw.lower()


def test_single_instance_lock_prevents_multiple_pollers(tmp_path):
    with single_agent_lock(tmp_path/"agent.lock"):
        with pytest.raises(AgentAlreadyRunning):
            with single_agent_lock(tmp_path/"agent.lock"):
                pass
    with single_agent_lock(tmp_path/"agent.lock"):
        pass


def test_identity_absent_cannot_report_connected(tmp_path):
    path=tmp_path/"device_identity.json"
    update_heartbeat(path,str(uuid.uuid4()),connected=True)
    assert current_link_status(path)["connected"] is False
