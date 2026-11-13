"""Run frozen release probes from normal Windows Temp, not source ACL folder."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/"evidence"/"qa"/"public-portable-prototype"
PARTS=(
 ("GUI","UniversalRemote-Preview","--self-test",""),
 ("AGENT","UniversalRemoteAgent-Preview","--health-probe","UNIVERSAL_REMOTE_AGENT_HEALTH_OK"),
 ("BRIDGE","UniversalRemoteBridge-Preview","--health-probe","UNIVERSAL_REMOTE_TUNNEL_BRIDGE_HEALTH_OK"),
 ("TUNNEL","UniversalRemoteTunnel-Preview","--self-test","UNIVERSAL_REMOTE_TUNNEL_SELFTEST_OK"),
 ("UPDATER","UniversalRemoteUpdater-Preview","trust-profile",'"channel": "PRIVATE_QA"'),
)
with tempfile.TemporaryDirectory(prefix="URM-FROZEN-ACCEPTANCE-") as dest:
    for label,name,argument,expected in PARTS:
        package=DIST/name
        if not package.is_dir():raise FileNotFoundError(str(package))
        runtime=Path(dest)/name
        shutil.copytree(package,runtime)
        exe=runtime/(name+".exe")
        result=subprocess.run([str(exe),argument],cwd=str(runtime),capture_output=True,
                              text=True,errors="replace",timeout=110,check=False)
        if result.returncode or expected not in result.stdout:
            print("FROZEN_PROBE_FAIL",label,result.returncode,result.stderr[-400:],flush=True)
            raise SystemExit(9)
        print("FROZEN_PROBE_PASS",label,flush=True)
print("ALL_FROZEN_COMPONENTS_PASS")
