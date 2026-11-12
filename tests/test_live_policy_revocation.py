"""Policy changes made after MCP connection must revoke prior permissions immediately.

Test is fully disposable, uses only synthetic files and no Windows privileges.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import timedelta
import json,sys,tempfile,time,unittest,uuid
from pathlib import Path

from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]

class LiveConfigRevocationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(prefix="urm-live-config-")
        self.addCleanup(self.t.cleanup)
        self.home=Path(self.t.name)
        self.old=self.home/"old"
        self.new=self.home/"new"
        self.old.mkdir();self.new.mkdir()
        self.old_file=self.old/"old.txt";self.old_file.write_text("SECRET_OLD_ONLY",encoding="utf-8")
        self.new_file=self.new/"new.txt";self.new_file.write_text("NEW_ONLY",encoding="utf-8")
        self.cfg=self.home/"config.json"
        self.grants=self.home/"grants.json"
        self.config_template={
            "allowed_roots":[str(self.old)],
            "backup_root":str(self.home/"backups"),
            "grants_path":str(self.grants),
            "enable_writes":True,"enable_shell":False,"enable_screen":False,"enable_input":False
        }
        self.cfg.write_text(json.dumps(self.config_template),encoding="utf-8")
        self.grants.write_text(json.dumps({
            "expires_at":time.time()+180,"capabilities":["writes"]
        }),encoding="utf-8")
        self.env={"HARMONY_MCP_CONFIG":str(self.cfg),"LOCALAPPDATA":str(self.home)}

    @asynccontextmanager
    async def session(self):
        params=StdioServerParameters(command=sys.executable,args=[str(ROOT/"launch_server.py")],env=self.env)
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=35)) as client:
                await client.initialize()
                yield client

    @staticmethod
    def value(result):
        return json.loads(next(c.text for c in result.content if c.type=="text"))

    async def test_workspace_and_writes_revoke_without_restarting(self):
        op=str(uuid.uuid4())
        target=self.old/"must-not-write.txt"
        async with self.session() as client:
            initial=await client.call_tool("read_text_file",{"path":str(self.old_file)})
            self.assertFalse(initial.isError)
            self.assertEqual(self.value(initial)["text"],"SECRET_OLD_ONLY")

            changed={**self.config_template,"allowed_roots":[str(self.new)],"enable_writes":False}
            self.cfg.write_text(json.dumps(changed),encoding="utf-8")
            state=await client.call_tool("agent_policy",{})
            self.assertFalse(state.isError)
            self.assertTrue(self.value(state).get("requires_restart"),
                            "UI must be informed current session policy is stale")
            forbidden_read=await client.call_tool("read_text_file",{"path":str(self.old_file)})
            self.assertTrue(forbidden_read.isError,
                            "Old workspace remains readable despite removal from policy")
            forbidden_write=await client.call_tool("write_text_file",{
                "path":str(target),"content":"no","operation_id":op})
            self.assertTrue(forbidden_write.isError,
                            "Revoked capability still permitted in running server")
            journal=self.value(await client.call_tool("check_operation",{"operation_id":op}))
            self.assertEqual(journal["state"],"not_found")
            self.assertFalse(target.exists())
        async with self.session() as client:
            self.assertTrue((await client.call_tool("read_text_file",{"path":str(self.old_file)})).isError)
            fresh=await client.call_tool("read_text_file",{"path":str(self.new_file)})
            self.assertFalse(fresh.isError)
            self.assertEqual(self.value(fresh)["text"],"NEW_ONLY")
            self.assertFalse(self.value(await client.call_tool("agent_policy",{}))["requires_restart"])

if __name__=="__main__":unittest.main()
