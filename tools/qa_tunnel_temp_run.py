"""Isolate frozen sidecar execution in Windows Temp, without bypassing security."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
base=Path(__file__).resolve().parents[1]/"evidence"/"qa"/"public-portable-prototype"
a=base/"UniversalRemoteTunnel-Preview"
with tempfile.TemporaryDirectory(prefix="urm-frozen-tunnel-") as temp:
    b=Path(temp)/"Tunnel"
    shutil.copytree(a,b)
    exe=b/"UniversalRemoteTunnel-Preview.exe"
    for where,program in (("original",a/"UniversalRemoteTunnel-Preview.exe"),
                          ("temp",exe)):
        try:
            proc=subprocess.run([str(program),"--self-test"],cwd=str(program.parent),
                   capture_output=True,text=True,errors="replace",timeout=35)
            print(where,"EXIT",proc.returncode,"OUT",proc.stdout[-250:],"ERR",proc.stderr[-750:],flush=True)
        except (OSError,subprocess.TimeoutExpired) as err:
            print(where,type(err).__name__,str(err)[:120],flush=True)
