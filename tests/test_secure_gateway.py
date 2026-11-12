import asyncio
import base64
from pathlib import Path
import tempfile
import unittest
import uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from mcp.server.fastmcp import FastMCP
from device_pairing import PairingError,client_signature_message,pairing_signature_message
from secure_gateway import attach_secure_gateway


class SecureGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.mcp=FastMCP("test")
        @self.mcp.tool()
        def get_system_metrics() -> dict:
            return {"ok":True}
        @self.mcp.tool()
        def run_powershell(command: str, operation_id: str) -> dict:
            return {"executed":command}
        self.registry=attach_secure_gateway(self.mcp,Path(self.temp.name))
        self.key=Ed25519PrivateKey.generate()
        self.pub=base64.b64encode(self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)).decode()
        begin=self.registry.begin(self.pub,"test client")
        signature=base64.b64encode(self.key.sign(
            pairing_signature_message(begin["request_id"],begin["challenge"]))).decode()
        self.registry.finish(begin["request_id"],signature)
        self.client=self.registry.approve_local(begin["request_id"],{"read"},
                                                presence_confirmed=True)["client_id"]

    def signed_args(self,method,args):
        nonce=str(uuid.uuid4())
        from time import time
        timestamp=int(time())
        signature=base64.b64encode(self.key.sign(
            client_signature_message(self.client,method,args,nonce,timestamp))).decode()
        return {**args,"device_proof":{"client_id":self.client,"nonce":nonce,
                                      "timestamp":timestamp,"signature":signature}}

    def call(self,method,args):
        return asyncio.run(self.mcp._tool_manager.call_tool(method,args))

    def test_denies_unpaired_read(self):
        with self.assertRaises(PairingError):
            self.call("get_system_metrics",{})

    def test_allows_signed_read(self):
        result=self.call("get_system_metrics",self.signed_args("get_system_metrics",{}))
        self.assertTrue(result)

    def test_rejects_shell_even_with_correct_signature_without_scope(self):
        args={"command":"echo hello","operation_id":str(uuid.uuid4())}
        with self.assertRaises(PairingError):
            self.call("run_powershell",self.signed_args("run_powershell",args))

    def test_schema_exposes_proof_and_unknown_tool_fails_closed(self):
        t=next(t for t in self.mcp._tool_manager.list_tools()
               if t.name=="get_system_metrics")
        self.assertIn("device_proof",t.parameters["properties"])
        with self.assertRaises(PairingError):
            self.call("unknown",{})

    def test_replay_at_mcp_boundary(self):
        args=self.signed_args("get_system_metrics",{})
        self.call("get_system_metrics",args)
        with self.assertRaises(PairingError):
            self.call("get_system_metrics",args)


if __name__=="__main__":
    unittest.main()
