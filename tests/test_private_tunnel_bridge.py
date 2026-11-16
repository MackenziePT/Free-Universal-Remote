"""Security and transport contracts for the owner-approved private tunnel bridge."""
import asyncio
import base64
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from mcp.server.fastmcp import FastMCP

from device_pairing import PairingRegistry, PairingError, pairing_signature_message
from private_tunnel_bridge import configure_signed_private_tunnel, _transport_verified


class PrivateTunnelBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_signed_and_locally_approved_identity_allows_read(self):
        with tempfile.TemporaryDirectory(prefix="urm-bridge-auth-") as temp:
            with patch.dict(os.environ, {"LOCALAPPDATA": temp}):
                state=Path(temp)/"UniversalRemote"/"security"
                registry=PairingRegistry(state)
                signer=Ed25519PrivateKey.generate()
                public=signer.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw)
                request=registry.begin(base64.b64encode(public).decode(), "Unit-test device")
                signature=signer.sign(pairing_signature_message(
                    request["request_id"], request["challenge"]))
                registry.finish(request["request_id"], base64.b64encode(signature).decode())
                enrolled=registry.approve_local(request["request_id"], {"read"},
                                               presence_confirmed=True)
                server=FastMCP("private-bridge-qa")

                @server.tool()
                def ping() -> dict:
                    return {"alive": True}

                @server.tool()
                def agent_policy() -> dict:
                    return {"roots": [str(Path(temp)/"workspace")]}

                @server.tool()
                def run_powershell(command: str, operation_id: str) -> dict:
                    return {"executed": True}

                configure_signed_private_tunnel(server, signer, enrolled["client_id"])
                manager=server._tool_manager
                visible={t.name:t for t in manager.list_tools()}
                self.assertEqual(set(visible), {"ping", "agent_policy", "run_powershell"})
                self.assertNotIn("device_proof", visible["agent_policy"].parameters["properties"])
                self.assertNotIn("pairing_begin", visible)
                self.assertNotIn("pairing_finish", visible)

                read=await manager.call_tool("agent_policy", {}, context=None)
                self.assertTrue(read)
                with self.assertRaises(PairingError):
                    await manager.call_tool("run_powershell",
                                            {"command":"Write-Output X",
                                             "operation_id":"unit-qa"}, context=None)
                with self.assertRaises(PairingError):
                    await manager.call_tool("agent_policy", {"device_proof":{}}, context=None)
                with self.assertRaises(PairingError):
                    await manager.call_tool("pairing_begin", {}, context=None)

                registry.revoke_local(enrolled["client_id"])
                with self.assertRaises(PairingError):
                    await manager.call_tool("agent_policy", {}, context=None)

    def test_private_tunnel_parent_must_be_verified(self):
        with patch.dict(os.environ, {"CONTROL_PLANE_API_KEY": ""}):
            self.assertFalse(_transport_verified())
        with patch.dict(os.environ, {"CONTROL_PLANE_API_KEY":"sk-qa-test-only-key-not-a-real-token"}):
            self.assertFalse(_transport_verified())


if __name__ == "__main__":
    unittest.main()
