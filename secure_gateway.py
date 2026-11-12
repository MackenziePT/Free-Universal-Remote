"""Fail-closed opt-in MCP gateway for individually signed device requests.

SDK integration is intentionally pinned and checked against MCP Python 1.30.0.
This does not authorize port exposure or the OpenAI tunnel automatically.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from device_pairing import PairingError, PairingRegistry, TOOL_SCOPES


def attach_secure_gateway(mcp, folder: Path) -> PairingRegistry:
    """Extend tools/list schemas and intercept *all* tools/call before dispatch."""
    manager = getattr(mcp, "_tool_manager", None)
    if manager is None or not hasattr(manager, "call_tool") or not hasattr(manager, "list_tools"):
        raise RuntimeError("Unsupported MCP SDK; secure gateway refuses startup")
    if getattr(manager, "_universal_secure_gateway_installed", False):
        raise RuntimeError("Secure gateway already installed")
    registry = PairingRegistry(folder)

    @mcp.tool(annotations={"readOnlyHint": True})
    def pairing_begin(public_key: str, label: str) -> dict:
        """Request device pairing; a local owner must separately approve."""
        return registry.begin(public_key, label)

    @mcp.tool(annotations={"readOnlyHint": True})
    def pairing_finish(request_id: str, signature: str) -> dict:
        """Demonstrate possession of a device private key; never grants access."""
        return registry.finish(request_id, signature)

    tools = manager.list_tools()
    names = {t.name for t in tools}
    unknown = names - set(TOOL_SCOPES)
    if unknown:
        raise RuntimeError("Unclassified tools fail closed: " + ",".join(sorted(unknown)))
    for t in tools:
        if TOOL_SCOPES[t.name] is None:
            continue
        schema = t.parameters
        if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
            raise RuntimeError("Unexpected SDK tool schema")
        if "device_proof" in schema["properties"]:
            raise RuntimeError("Proof property name collision")
        # Extra schema argument is verified and removed BEFORE Pydantic tool binding.
        schema["properties"]["device_proof"] = {
            "type": "object",
            "description": "Ed25519 client signature over canonical tool arguments, nonce and time.",
            "properties": {
                "client_id": {"type": "string"},
                "nonce": {"type": "string"},
                "timestamp": {"type": "integer"},
                "signature": {"type": "string"}},
            "required": ["client_id","nonce","timestamp","signature"],
            "additionalProperties": False}

    original_call = manager.call_tool

    async def checked_call(name: str, arguments: dict[str, Any],
                           context=None, convert_result: bool = False):
        if name not in TOOL_SCOPES:
            raise PairingError("Unregistered tool denied")
        if not isinstance(arguments, dict):
            raise PairingError("Tool arguments must be an object")
        clean = dict(arguments)
        proof = clean.pop("device_proof", None)
        registry.verify_call(name, clean, proof)
        return await original_call(name, clean, context=context,
                                   convert_result=convert_result)

    manager.call_tool = checked_call
    manager._universal_secure_gateway_installed = True
    return registry
