"""A second publisher-controlled switch keeps privileged remote work disabled."""
import uuid
from fastapi.testclient import TestClient
from cloud.app import create_app
from cloud.auth import Principal, Settings
from cloud.storage import Store

ORIGIN="https://universal-remote-free-production.up.railway.app"
ISSUER="https://hsztpgfgwlmnocealhcm.supabase.co/auth/v1"

class GrantedUser:
    def principal(self, token):
        return Principal("a"*64, frozenset({"ur:read","ur:devices","ur:control","ur:shell","ur:screen","ur:input"}))


def test_privileged_jobs_fail_closed_even_with_valid_high_privilege_token(tmp_path,monkeypatch):
    monkeypatch.delenv("UR_AGENT_COMMANDS_ENABLED",raising=False)
    settings=Settings(ISSUER,"authenticated",ISSUER+"/.well-known/jwks.json",ORIGIN)
    store=Store(tmp_path/"queue.sqlite3",bytes(range(32)))
    attempts=[]
    store.submit=lambda *args: attempts.append(args) or str(uuid.uuid4())
    client=TestClient(create_app(settings,store,GrantedUser(),provider_mode="supabase"))
    for name,args in [
        ("request_windows_powershell",{"command":"whoami","confirmation":"I understand this requires local Windows approval"}),
        ("request_windows_diagnostic",{"diagnostic":"cpu"}),
        ("request_windows_input",{"action":"click","x":10,"y":10,"confirmation":"I understand this requires local Windows approval"}),
    ]:
        args["device_id"]="00000000-0000-4000-8000-000000000000"
        result=client.post("/mcp",headers={"Authorization":"Bearer signed-placeholder"},
            json={"jsonrpc":"2.0","id":42,"method":"tools/call",
                  "params":{"name":name,"arguments":args}}).json()["result"]
        assert result["isError"] is True, (name,result)
    assert attempts==[], "Publisher must enable privileged jobs explicitly"