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
from process_runner import clean_child_environment
QA=ROOT/"evidence"/"qa"
DIST=QA/"public-portable-prototype"
UI=DIST/"UniversalRemote-Preview"/"UniversalRemote-Preview.exe"
AGENT=DIST/"UniversalRemoteAgent-Preview"/"UniversalRemoteAgent-Preview.exe"
BRIDGE=DIST/"UniversalRemoteBridge-Preview"/"UniversalRemoteBridge-Preview.exe"
TUNNEL=DIST/"UniversalRemoteTunnel-Preview"/"UniversalRemoteTunnel-Preview.exe"
UPDATER=DIST/"UniversalRemoteUpdater-Preview"/"UniversalRemoteUpdater-Preview.exe"

def env_for_user(state:Path)->dict:
    env=clean_child_environment()
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
    # A stale success report must never survive a failed executable verification.
    (QA/"standalone-acceptance.json").unlink(missing_ok=True)
    for executable in (UI,AGENT,BRIDGE,TUNNEL,UPDATER):
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
        # Verify every independently bundled executable starts without Python on PATH.
        for label, executable, arguments, marker in (
                ("agent_health", AGENT, ["--health-probe"], "UNIVERSAL_REMOTE_AGENT_HEALTH_OK"),
                ("bridge_health", BRIDGE, ["--health-probe"], "UNIVERSAL_REMOTE_TUNNEL_BRIDGE_HEALTH_OK"),
                ("tunnel_health", TUNNEL, ["--self-test"], "UNIVERSAL_REMOTE_TUNNEL_SELFTEST_OK"),
                ("updater_health", UPDATER, ["trust-profile"], '"channel": "PRIVATE_QA"')):
            probe=subprocess.run([str(executable),*arguments],env=env,
                                 capture_output=True,text=True,timeout=60)
            assert probe.returncode==0 and marker in probe.stdout, (
                label,probe.returncode,probe.stdout[-500:],probe.stderr[-500:])
            results[label]=True
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
