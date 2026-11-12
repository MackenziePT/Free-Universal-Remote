"""Private installer/uninstaller E2E, installed into disposable Windows folder.

No changes to the running RC5.0 or developer profile. Does not disable antivirus.
"""
from __future__ import annotations
import asyncio
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import winreg

PROJECT = Path(__file__).resolve().parents[1]
QA = PROJECT / "evidence" / "qa"
SETUP = QA / "installer-build" / "UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe"
RESULTS = QA / "installer-e2e-results.json"
APP_REGKEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{D1E2CF25-D0C1-4C63-90A6-7D2C40AAAD3B}_is1"

def ensure_no_previous_preview():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_REGKEY):
            raise RuntimeError("Existing preview installation detected: refusing to override its registration")
    except FileNotFoundError:
        return

def restricted_env(folder: Path) -> dict[str,str]:
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(folder)
    env["PYTHONNOUSERSITE"] = "1"
    env["PATH"] = os.pathsep.join((str(Path(os.environ["SystemRoot"]) / "System32"),
                                  os.environ["SystemRoot"]))
    for k in ("PYTHONHOME", "PYTHONPATH", "HARMONY_MCP_CONFIG",
              "UNIVERSAL_REMOTE_DATA_HOME", "CONTROL_PLANE_API_KEY"):
        env.pop(k, None)
    return env

def run(name: str, args: list[str], env: dict[str,str], limit: int = 140):
    start=time.monotonic()
    result=subprocess.run(args,capture_output=True,text=True,errors="replace",env=env,timeout=limit)
    elapsed=round(time.monotonic()-start,2)
    print(name,"exit",result.returncode,"seconds",elapsed,flush=True)
    if result.returncode not in (0,12):
        print("STDERR_TAIL",result.stderr[-1200:],flush=True)
    return result

async def verify_stdio(exe: Path, env: dict[str,str]) -> int:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params=StdioServerParameters(command=str(exe),args=[],env=env)
    async with stdio_client(params) as (stream_in,stream_out):
        async with ClientSession(stream_in,stream_out,read_timeout_seconds=timedelta(seconds=50)) as session:
            await session.initialize()
            ping=await session.call_tool("ping",{})
            assert not ping.isError,str(ping)
            body=json.loads(next(part.text for part in ping.content if part.type=="text"))
            assert body["version"]=="1.0.0-rc5.1-dev"
            tools=await session.list_tools()
            assert len(tools.tools)==27,len(tools.tools)
            return len(tools.tools)

def main():
    assert os.name=="nt", "Windows only"
    assert SETUP.is_file(),"Release candidate installer missing"
    ensure_no_previous_preview()
    report={"package_sha256":hashlib.sha256(SETUP.read_bytes()).hexdigest(),
            "package_size_mb":round(SETUP.stat().st_size/(1024*1024),2),
            "certification":"Private engineering acceptance; NOT a signed public release"}
    completed=False
    with tempfile.TemporaryDirectory(prefix="URM-PUBLIC-QA-") as temporary:
        path=Path(temporary)
        install=path/"Application"
        state=path/"PrivateUserState"
        state.mkdir()
        env=restricted_env(state)
        installer_log=QA/"installer-install-detail.log"
        uninstall_log=QA/"installer-uninstall-detail.log"
        try:
            # Test the actual one-click installer in per-user scope with no desktop shortcuts.
            result=run("INSTALL",[
                str(SETUP),"/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART",
                "/SP-","/NOICONS",f"/DIR={install}",f"/LOG={installer_log}",
            ],env,limit=180)
            assert result.returncode==0,("INSTALL_FAILED",result.stderr[-400:])
            gui=install/"GUI"/"UniversalRemote-Preview.exe"
            # The URL scheme is registered in HKCU without admin permissions.
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                  r"Software\Classes\universal-remote\shell\open\command") as url_key:
                actual,_=winreg.QueryValueEx(url_key,"")
            assert actual==f'"{gui}" "%1"', "Deep link must open the exact installed GUI"
            report["safe_one_link_activation"]=True
            agent=install/"Agent"/"UniversalRemoteAgent-Preview.exe"
            updater=install/"Updater"/"UniversalRemoteUpdater-Preview.exe"
            tunnel=install/"Tunnel"/"UniversalRemoteTunnel-Preview.exe"
            tunnel_client=install/"bin"/"tunnel-client.exe"
            uninstall=install/"unins000.exe"
            runtime_script=install/"scripts"/"Prepare-PowerShell.ps1"
            resolver=install/"scripts"/"Resolve-PowerShell.ps1"
            independent_probe=install/"scripts"/"Test-Independent-PC.ps1"
            for f in (gui,agent,updater,tunnel,tunnel_client,uninstall,runtime_script,resolver,independent_probe):
                assert f.is_file(),str(f)
            report["private_powershell_bootstrap_included"]=True
            report["installed_files_present"]=True
            assert not (state/"UniversalRemote"/"config.json").exists()
            denied=run("DENY_UNCONFIGURED",[str(agent),"--version"],env,limit=60)
            assert denied.returncode==12,denied.stderr[-300:]
            report["unconfigured_denied"]=True
            health=run("AGENT_HEALTH_PROBE",[str(agent),"--health-probe"],env,limit=40)
            assert health.returncode==0 and "UNIVERSAL_REMOTE_AGENT_HEALTH_OK" in health.stdout
            updater_help=run("UPDATER_HELP",[str(updater),"--help"],env,limit=40)
            assert updater_help.returncode==0 and "recover" in updater_help.stdout
            report["security_updater_present"]=True
            tunnel_health=run("TUNNEL_SELFTEST",[str(tunnel),"--self-test"],env,limit=45)
            assert tunnel_health.returncode==0 and "UNIVERSAL_REMOTE_TUNNEL_SELFTEST_OK" in tunnel_health.stdout
            report["private_tunnel_sidecar_present"]=True
            before=run("GUI_SELFTEST",[str(gui),"--self-test"],env,limit=120)
            assert before.returncode==0,before.stderr[-500:]
            report["gui_six_pages"]=True
            sys.path.insert(0,str(PROJECT))
            from unittest.mock import patch
            from public_paths import write_initial_config
            with patch.dict(os.environ,{"LOCALAPPDATA":str(state)}):
                user_config=write_initial_config(state/"Workspace")
            initial_bytes=user_config.read_bytes()
            output=run("AGENT_CONFIGURED",[str(agent),"--version"],env,limit=70)
            assert output.returncode==0,output.stderr[-500:]
            report["agent_stdio_tools"]=asyncio.run(verify_stdio(agent,env))
            assert user_config.read_bytes()==initial_bytes
            # Same-version repair/upgrade in the same disposable installation.
            repair=run("REPAIR",[str(SETUP),"/VERYSILENT","/SUPPRESSMSGBOXES",
                                 "/NORESTART","/SP-","/NOICONS",
                                 f"/DIR={install}",f"/LOG={QA/'installer-repair-detail.log'}"],
                       env,limit=200)
            assert repair.returncode==0,repair.stderr[-500:]
            assert agent.is_file() and gui.is_file()
            assert user_config.read_bytes()==initial_bytes
            report["repair_preserved_personal_config"]=True
            completed=True
        finally:
            uninstaller=install/"unins000.exe"
            if uninstaller.exists():
                command=[
                    str(uninstaller),"/VERYSILENT","/SUPPRESSMSGBOXES",
                    "/NORESTART",f"/LOG={uninstall_log}"
                ]
                ended=run("UNINSTALL",command,env,limit=150)
                report["uninstaller_exit"]=ended.returncode
                report["uninstaller_removed_exe"]=not (install/"GUI"/"UniversalRemote-Preview.exe").exists()
                if ended.returncode!=0:
                    print("UNINSTALL_FAILURE_NEEDS_MANUAL_QA_INSPECTION",str(install),flush=True)
            if "user_config" in locals() and user_config.exists():
                report["user_private_state_preserved_on_uninstall"]=user_config.read_bytes()==initial_bytes
        assert completed,"Installation E2E did not pass"
        assert report.get("uninstaller_exit")==0 and report.get("uninstaller_removed_exe"),report
        assert report.get("user_private_state_preserved_on_uninstall"),report
    RESULTS.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("INSTALLER_E2E_PASS",json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
