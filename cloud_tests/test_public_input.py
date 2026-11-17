"""Remote desktop input stays behind owner OAuth and local Windows grants."""
import json
import uuid
from cloud_tests.test_cloud import world
from cloud.native_dispatch import NativeDispatcher,NativeDenied

CONFIRM="I understand this requires local Windows approval"

def test_public_input_requires_separate_oauth_scope(world):
    device,_=world["enroll"]()
    c=world["client"]
    tools=c.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"tools/list"}).json()["result"]["tools"]
    item=next(t for t in tools if t["name"]=="request_windows_input")
    assert "ur:input" in item["securitySchemes"][0]["scopes"]
    assert item["annotations"]["destructiveHint"] is True
    args={"device_id":device,"action":"click","x":200,"y":150,
          "confirmation":CONFIRM}
    result=world["call"]("request_windows_input",args).json()["result"]
    assert result["isError"] is True
    assert "insufficient_scope" in result["_meta"]["mcp/www_authenticate"][0]
    auth=world["auth"]("alice",scope="ur:read ur:input")
    allowed=c.post("/mcp",headers=auth,json={"jsonrpc":"2.0","id":2,"method":"tools/call",
           "params":{"name":"request_windows_input","arguments":args}}).json()["result"]
    assert allowed["isError"] is False
    assert uuid.UUID(allowed["structuredContent"]["operation_id"]).version==4

def test_public_input_rejects_out_of_policy_actions(world):
    device,_=world["enroll"]()
    c=world["client"]
    auth=world["auth"]("alice",scope="ur:read ur:input")
    for action,text in (("hotkey","alt+f4"),("press","super"),("type","x"*501)):
        result=c.post("/mcp",headers=auth,json={"jsonrpc":"2.0","id":3,"method":"tools/call",
             "params":{"name":"request_windows_input","arguments":{
                 "device_id":device,"action":action,"text":text,
                 "confirmation":CONFIRM}}}).json()["result"]
        assert result["isError"] is True

def test_windows_dispatch_denies_input_without_owner_local_grant():
    class Native:
        def agent_policy(self):
            return json.dumps({"requires_restart":False,
                               "effective_permissions":{"input":False}})
        def desktop_action(self,*args):
            raise AssertionError("Desktop must not be touched")
    dispatcher=NativeDispatcher(native_server=Native())
    assert dispatcher.has_local_permission("desktop_action") is False
    try:
        dispatcher.dispatch_local("desktop_action",
           {"action":"click","x":300,"y":180,"text":"","operation_id":str(uuid.uuid4())})
    except NativeDenied:
        pass
    else:
        raise AssertionError("Missing local grant should reject desktop action")


def test_windows_native_input_preserves_one_unique_operation_id():
    calls=[]
    class Native:
        def agent_policy(self):
            return json.dumps({"requires_restart":False,
                "effective_permissions":{"input":True}})
        def desktop_action(self,*args):
            calls.append(args)
            return json.dumps({"ok":True})
    d=NativeDispatcher(native_server=Native())
    operation=str(uuid.uuid4())
    result=d.dispatch_local("desktop_action",
        {"action":"click","operation_id":operation,"x":150,"y":200,"text":""})
    assert result=={"ok":True}
    assert calls==[("click",operation,150,200,"")]
