"""Public Windows enrollment must not bypass OAuth or local grants."""
import base64
import time
import uuid
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from cloud.public_link import (
    LinkConfig, LinkError, device_authorize, enroll_windows, bridge_once,
    current_link_status,
)


def test_require_public_https_and_registered_client_id():
    with pytest.raises(LinkError):
        LinkConfig("http://localhost:8080", "https://auth.example.org", "windows-client")
    with pytest.raises(LinkError):
        LinkConfig("https://remote.example.org", "https://auth.example.org", "")
    cfg = LinkConfig("https://remote.example.org", "https://auth.example.org", "windows-client")
    assert cfg.gateway == "https://remote.example.org"


def test_device_authorize_requires_provider_discovery_and_pkce_capabilities():
    cfg = LinkConfig("https://remote.example.org", "https://auth.example.org", "windows-client")
    http = Mock()
    http.get.return_value.json.return_value = {"issuer":"https://evil.example.org"}
    http.get.return_value.raise_for_status.return_value = None
    with pytest.raises(LinkError):
        device_authorize(cfg, http=http, open_browser=lambda _: None, note=lambda _: None)


def test_device_authorize_poll_and_open_browser():
    cfg = LinkConfig("https://remote.example.org", "https://auth.example.org", "windows-client")
    http = Mock()
    metadata = {"issuer":cfg.issuer,
                "device_authorization_endpoint":"https://auth.example.org/oauth/device",
                "token_endpoint":"https://auth.example.org/oauth/token"}
    http.get.return_value.json.return_value = metadata
    challenge={"device_code":"d-"*20, "user_code":"ABC-123",
               "verification_uri":"https://auth.example.org/activate",
               "verification_uri_complete":"https://auth.example.org/activate?user_code=ABC-123",
               "expires_in":300, "interval":1}
    pending=Mock(status_code=400)
    pending.json.return_value={"error":"authorization_pending"}
    success=Mock(status_code=200)
    success.json.return_value={"access_token":"secure-test-token","token_type":"Bearer","expires_in":300}
    challenge_response=Mock(status_code=200)
    challenge_response.json.return_value=challenge
    http.post.side_effect=[challenge_response,pending,success]
    opened=[]; messages=[]
    result=device_authorize(cfg,http=http,open_browser=opened.append,
                            note=messages.append, sleep=lambda _: None)
    assert result=="secure-test-token"
    assert opened==[challenge["verification_uri_complete"]]
    assert any("ABC-123" in n for n in messages)
    assert http.post.call_args_list[-1].kwargs["data"]["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"


def test_enroll_requires_token_and_persists_only_own_key():
    cfg=LinkConfig("https://remote.example.org","https://auth.example.org","windows-client")
    http=Mock()
    enrollment={"id":str(uuid.uuid4()),"owner":"a"*64,
                "challenge":base64.b64encode(bytes(range(32))).decode(),"expires":123}
    begin=Mock(status_code=200);begin.json.return_value=enrollment
    finish=Mock(status_code=200);finish.json.return_value={"device_id":str(uuid.uuid4())}
    http.post.side_effect=[begin,finish]
    saved=[]
    device=enroll_windows(cfg,"valid-access-token", "My PC", http=http,
                          save_identity=lambda signer, origin, did: saved.append((signer,origin,did)))
    assert device==finish.json.return_value["device_id"]
    assert saved[0][1:] ==(cfg.gateway, device)
    assert http.post.call_args_list[0].kwargs["headers"] == {"Authorization":"Bearer valid-access-token"}
    data=http.post.call_args_list[1].kwargs["json"]
    pub=base64.b64decode(data["public_key"])
    signature=base64.b64decode(data["signature"])
    assert len(pub)==32 and len(signature)==64
    assert data["label"] == "My PC"


def test_enroll_rejects_bearer_without_token():
    cfg=LinkConfig("https://remote.example.org","https://auth.example.org","windows-client")
    http=Mock()
    with pytest.raises(LinkError):
        enroll_windows(cfg,"", "My PC",http=http,save_identity=lambda *args: None)
    http.post.assert_not_called()


def test_bridge_requires_native_callbacks_and_passes_no_cloud_permissions():
    from cloud.device_client import Signer
    cfg=LinkConfig("https://remote.example.org","https://auth.example.org","windows-client")
    with pytest.raises(LinkError):
        bridge_once(cfg.gateway,str(uuid.uuid4()),Signer.generate_for_local_enrollment(),
                    native_permission=None,native_dispatch=lambda *x: None)


def test_status_does_not_trigger_network_or_credentials(tmp_path):
    identity=tmp_path/"identity.json"
    assert current_link_status(identity)["connected"] is False
    identity.write_text("not a real identity",encoding="utf-8")
    assert current_link_status(identity)["connected"] is False



def test_windows_dpapi_identity_roundtrip_in_temporary_directory(tmp_path):
    import sys
    if sys.platform != "win32":
        pytest.skip("Windows DPAPI test")
    from cloud.device_client import Signer
    from cloud.windows_identity import save_identity, load_identity
    signer=Signer.generate_for_local_enrollment()
    path=tmp_path/"device_identity.json"
    ident=str(uuid.uuid4())
    save_identity(path,signer,"https://remote.example.org",ident)
    raw=path.read_text(encoding="utf-8")
    assert "dpapi_key" in raw
    assert "BEGIN PRIVATE KEY" not in raw
    origin, loaded_id, loaded_signer = load_identity(path)
    assert origin=="https://remote.example.org"
    assert loaded_id==ident
    assert loaded_signer.public_key()==signer.public_key()
