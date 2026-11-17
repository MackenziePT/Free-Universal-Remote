"""Public MCP auth discovery; no user data without a verified bearer token."""
import json
from cloud_tests.test_cloud import world


def test_public_method_discovery_without_bearer(world):
    c=world["client"]
    for method in ("initialize", "ping", "tools/list"):
        response=c.post("/mcp", json={"jsonrpc":"2.0","id":3,"method":method,"params":{}})
        assert response.status_code==200, (method,response.text)
    tools=c.post("/mcp",json={"jsonrpc":"2.0","id":4,"method":"tools/list"}).json()["result"]["tools"]
    assert any(t["name"]=="get_profile" for t in tools)
    for t in tools:
        assert t["securitySchemes"][0]["type"]=="oauth2", t["name"]
        assert t["_meta"]["securitySchemes"]==t["securitySchemes"], t["name"]
    profile=next(t for t in tools if t["name"]=="get_profile")
    assert profile["_meta"]["openai/profile"] is True
    assert profile["outputSchema"]["required"]==["id"]
    shell=next(t for t in tools if t["name"]=="request_windows_powershell")
    assert "ur:shell" in shell["securitySchemes"][0]["scopes"]
    assert "ur:shell" not in profile["securitySchemes"][0]["scopes"]


def test_missing_bearer_prompts_chatgpt_oauth_not_data(world):
    c=world["client"]
    response=c.post("/mcp",json={"jsonrpc":"2.0","id":5,"method":"tools/call",
                                  "params":{"name":"list_windows_devices","arguments":{}}})
    assert response.status_code==200
    result=response.json()["result"]
    assert result["isError"] is True
    challenge=result["_meta"]["mcp/www_authenticate"][0]
    assert "resource_metadata=" in challenge and 'error="invalid_token"' in challenge
    assert "structuredContent" not in result


def test_missing_scope_prompts_reauthorization(world):
    c=world["client"]
    h=world["auth"]("alice",scope="ur:read")
    response=c.post("/mcp",headers=h,json={"jsonrpc":"2.0","id":6,"method":"tools/call",
                      "params":{"name":"request_windows_powershell","arguments":{
                      "device_id":"00000000-0000-4000-8000-000000000000","command":"whoami",
                      "confirmation":"I understand this requires local Windows approval"}}})
    result=response.json()["result"]
    assert result["isError"] is True
    assert "insufficient_scope" in result["_meta"]["mcp/www_authenticate"][0]


def test_stable_profile_is_from_signed_subject(world):
    c=world["client"]
    first=world["call"]("get_profile",user="alice").json()["result"]["structuredContent"]
    second=world["call"]("get_profile",user="alice").json()["result"]["structuredContent"]
    other=world["call"]("get_profile",user="bob").json()["result"]["structuredContent"]
    assert first==second
    assert first["id"] != other["id"]
    assert len(first["id"])==64
    assert "email" not in first

def test_chunked_mcp_payload_exceeding_limit_rejected(world):
    def chunks():
        yield b'{"jsonrpc":"2.0","id":7,"method":"ping"}'
        yield b' ' * 151000
    response=world["client"].post("/mcp",headers=world["auth"](),content=chunks())
    assert response.status_code==413


def test_chunked_agent_result_exceeding_limit_rejected(world):
    def chunks():
        yield b'{"operation_id":'
        yield b' ' * 2500100
    response=world["client"].post(
        "/v1/agent/00000000-0000-4000-8000-000000000000/result",
        content=chunks())
    assert response.status_code==413