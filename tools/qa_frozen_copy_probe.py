"""Run isolated frozen agent from clean copied folder, without installing."""
from pathlib import Path
import os,subprocess,shutil,tempfile,sys,time
root=Path(__file__).resolve().parents[1]
source=root/"evidence"/"qa"/"public-portable-prototype"/"UniversalRemoteAgent-Preview"
with tempfile.TemporaryDirectory(prefix="UR-FROZEN-TEST-") as tmp:
    target=Path(tmp)/"Agent"
    print("SOURCE",str(source))
    print("DEST",str(target))
    shutil.copytree(source,target)
    exe=target/"UniversalRemoteAgent-Preview.exe"
    internal=target/"_internal"/"base_library.zip"
    for file in (exe,internal):
        print("FILE",file.name,"SIZE",file.stat().st_size,"READABLE",os.access(file,os.R_OK))
    try:
        run=subprocess.run([str(exe),"--health-probe"],cwd=str(target),
                           capture_output=True,text=True,errors="replace",
                           timeout=40,check=False)
        print("HEALTH_EXIT",run.returncode)
        print("HEALTH_STDOUT",run.stdout[-1000:])
        print("HEALTH_STDERR",run.stderr[-1000:])
    except Exception as ex:
        print("HEALTH_EXCEPTION",type(ex).__name__,str(ex)[:300])
