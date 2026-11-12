"""Prove unsigned private Windows portable binaries run without Python on PATH."""
from __future__ import annotations
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
# The test harness is in tools/ while first-run policy lives in the source root.
# This import is for synthetic test configuration only; neither EXE uses Python on PATH.
import sys
sys.path.insert(0,str(ROOT))
QA=ROOT/"evidence"/"qa"
DIST=QA/"public-portable-prototype"
UI=DIST/"UniversalRemote-Preview"/"UniversalRemote-Preview.exe"
AGENT=DIST/"UniversalRemoteAgent-Preview"/"UniversalRemoteAgent-Preview.exe"

def env_for_user(state:Path)->dict:
    env=os.environ.copy()
    env["LOCALAPPDATA"]=str(state)
    env["PYTHONNOUSERSITE"]="1"
    env["PATH"]=os.pathsep.join([str(Path(os.environ["SystemRoot"])/"System32"),os.environ["SystemRoot"]])
    for name in ("PYTHONPATH","PYTHONHOME","HARMONY_MCP_CONFIG","UNIVERSAL_REMOTE_DATA_HOME",
                 "CONTROL_PLANE_API_KEY"):
        env.pop(name,None)
    return env

async def test_mcp(exe:Path,env:dict)->int:
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    args=StdioServerParameters(command=str(exe),args=[],env=env)
    async with stdio_client(args) as (reader,writer):
        async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=45)) as session:
            await session.initialize()
            ping=await session.call_tool("ping",{})
            assert not ping.isError,str(ping)
            doc=json.loads(next(item.text for item in ping.content if item.type=="text"))
            assert doc["version"]=="1.0.0-rc5.1-dev",doc
            listing=await session.list_tools()
            assert len(listing.tools)==27,len(listing.tools)
            return len(listing.tools)

def main():
    for executable in (UI,AGENT):
        assert executable.is_file(),executable
    results={}
    with tempfile.TemporaryDirectory(prefix="urm-selfcontained-") as raw:
        state=Path(raw)
        env=env_for_user(state)
        started=time.monotonic()
        no_config=subprocess.run([str(AGENT),"--version"],env=env,
                                 capture_output=True,text=True,timeout=75)
        assert no_config.returncode==12,(no_config.returncode,no_config.stderr[-1000:])
        results["unconfigured_agent_denied"]=True
        gui=subprocess.run([str(UI),"--self-test"],env=env,
                           capture_output=True,text=True,timeout=120)
        assert gui.returncode==0,(gui.returncode,gui.stderr[-1000:])
        results["bundled_ui_six_pages"]=True
        assert not (state/"UniversalRemote"/"grants.json").exists()
        # Create policy with only the developer's QA Python process, NOT with the
        # frozen agent. The frozen agent itself must run without Python on PATH.
        from unittest.mock import patch
        from public_paths import write_initial_config
        with patch.dict(os.environ,{"LOCALAPPDATA":str(state)}):
            path=write_initial_config(state/"workspace")
            record=json.loads(path.read_text(encoding="utf-8"))
            assert all(record["enable_"+n] is False for n in ("writes","shell","screen","input"))
        version=subprocess.run([str(AGENT),"--version"],env=env,
                               capture_output=True,text=True,timeout=75)
        assert version.returncode==0,(version.returncode,version.stderr[-1000:])
        results["version"]=json.loads(version.stdout.strip())["version"]
        results["stdio_tools"]=asyncio.run(test_mcp(AGENT,env))
        assert not (state/"HarmonyRemoteMCP").exists(), "Legacy installation state was touched"
        assert (state/"UniversalRemote"/"logs").is_dir()
        results["legacy_data_untouched"]=True
        results["seconds"]=round(time.monotonic()-started,3)
    (QA/"standalone-acceptance.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    print("STANDALONE_ACCEPTANCE_PASS",json.dumps(results),flush=True)

if __name__=="__main__":
    main()
