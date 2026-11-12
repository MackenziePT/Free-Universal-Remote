"""Full subprocess stdio handshake using disposable unpaired/pairing state."""
import asyncio
import base64
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from device_pairing import PairingRegistry,pairing_signature_message,client_signature_message

ROOT=Path(__file__).resolve().parents[1]


class SecureStdioTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_paired_server_stdio(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            state=base/"UniversalRemote"
            workspace=base/"workspace"
            workspace.mkdir()
            state.mkdir()
            (state/"config.json").write_text(json.dumps({
                "allowed_roots":[str(workspace)],
                "backup_root":str(state/"backups"),
                "grants_path":str(state/"grants.json"),
                "enable_writes":False,"enable_shell":False,
                "enable_screen":False,"enable_input":False
            }),encoding="utf-8")
            env={**os.environ,"LOCALAPPDATA":str(base)}
            params=StdioServerParameters(command=sys.executable,
                           args=[str(ROOT/"public_agent.py"),"--paired"],env=env)
            with (base/"stderr.log").open("w",encoding="utf-8") as log:
                async with stdio_client(params,errlog=log) as (reader,writer):
                    async with ClientSession(reader,writer,
                        read_timeout_seconds=timedelta(seconds=35)) as session:
                        await session.initialize()
                        tools=(await session.list_tools()).tools
                        self.assertEqual(len(tools),29)
                        self.assertFalse((await session.call_tool("ping",{})).isError)
                        self.assertTrue((await session.call_tool("agent_policy",{})).isError)
                        key=Ed25519PrivateKey.generate()
                        pub=base64.b64encode(key.public_key().public_bytes(
                            encoding=serialization.Encoding.Raw,
                            format=serialization.PublicFormat.Raw)).decode()
                        begin=await session.call_tool("pairing_begin",
                                                 {"public_key":pub,"label":"CI-device"})
                        self.assertFalse(begin.isError,str(begin))
                        request=json.loads(next(x.text for x in begin.content if x.type=="text"))
                        signature=base64.b64encode(key.sign(
                            pairing_signature_message(request["request_id"],
                                                      request["challenge"]))).decode()
                        finished=await session.call_tool("pairing_finish",
                                 {"request_id":request["request_id"],"signature":signature})
                        self.assertFalse(finished.isError,str(finished))
                        registry=PairingRegistry(state/"security")
                        approved=registry.approve_local(request["request_id"],
                                  {"read"},presence_confirmed=True)
                        client_id=approved["client_id"]
                        nonce=str(uuid.uuid4())
                        now=int(time.time())
                        message=client_signature_message(client_id,"agent_policy",{},nonce,now)
                        proof={"client_id":client_id,"nonce":nonce,"timestamp":now,
                          "signature":base64.b64encode(key.sign(message)).decode()}
                        call=await session.call_tool("agent_policy",{"device_proof":proof})
                        self.assertFalse(call.isError,str(call))
                        payload=json.loads(next(x.text for x in call.content if x.type=="text"))
                        self.assertEqual(payload["roots"],[str(workspace)])
                        second=await session.call_tool("agent_policy",{"device_proof":proof})
                        self.assertTrue(second.isError,"replayed proof must be rejected")
                        registry.revoke_local(client_id)
                        proof["nonce"]=str(uuid.uuid4())
                        proof["signature"]=base64.b64encode(key.sign(
                            client_signature_message(client_id,"agent_policy",{},
                                                     proof["nonce"],now))).decode()
                        revoked=await session.call_tool("agent_policy",{"device_proof":proof})
                        self.assertTrue(revoked.isError)


if __name__=="__main__":
    unittest.main()
