"""Actual public entrypoint contract, with private fake Windows user profile."""
from __future__ import annotations
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.name=="nt","Windows product build")
class PublicEntrypoints(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="urm-public-entry-")
        self.addCleanup(self.tmp.cleanup)
        self.state=Path(self.tmp.name)
        self.home=self.state/"UniversalRemote"
        self.env=os.environ.copy()
        self.env["LOCALAPPDATA"]=str(self.state)
        self.env.pop("HARMONY_MCP_CONFIG",None)
        self.env.pop("UNIVERSAL_REMOTE_DATA_HOME",None)
        self.env.pop("CONTROL_PLANE_API_KEY",None)

    def make_policy(self):
        from public_paths import write_initial_config
        with patch.dict(os.environ,{"LOCALAPPDATA":str(self.state)}):
            write_initial_config(self.state/"work")

    def test_agent_denies_unconfigured_access(self):
        result=subprocess.run([sys.executable,str(ROOT/"public_agent.py"),"--version"],
                              env=self.env,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,12,result.stdout+result.stderr)
        self.assertFalse((self.home/"config.json").exists())

    async def test_agent_starts_standalone_stdio_after_first_run(self):
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        self.make_policy()
        args=StdioServerParameters(command=sys.executable,
            args=[str(ROOT/"public_agent.py")],env=self.env)
        async with stdio_client(args) as (input_,output):
            async with ClientSession(input_,output,
                 read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize()
                result=await session.call_tool("ping",{})
                self.assertFalse(result.isError,str(result))
                payload=json.loads(next(x.text for x in result.content if x.type=="text"))
                self.assertTrue(payload["alive"])
                self.assertEqual(payload["version"],"1.0.0-rc5.1-dev")
                tools=await session.list_tools()
                self.assertEqual(len(tools.tools),27)
        self.assertTrue((self.home/"logs").is_dir())
        self.assertFalse((self.state/"HarmonyRemoteMCP").exists())

    @unittest.skipIf(os.environ.get("URM_CI_HEADLESS")=="1","Needs active Windows desktop")
    def test_gui_selftest_with_temporary_state(self):
        result=subprocess.run([sys.executable,str(ROOT/"public_gui.py"),"--self-test"],
                              env=self.env,capture_output=True,text=True,timeout=75)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse((self.home/"config.json").exists())

if __name__=="__main__":unittest.main()
