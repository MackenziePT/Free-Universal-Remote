"""Disposable NTFS ACL test: compare default mkdir and restrictive mkdir."""
from pathlib import Path
import os,shutil,subprocess,sys,tempfile,zipfile
root=Path(__file__).resolve().parents[1]/"evidence"/"qa"
source=root/"public-portable-prototype"/"UniversalRemoteAgent-Preview"/"_internal"/"base_library.zip"
print("CURRENT_USER",subprocess.check_output(["whoami"],text=True).strip(),flush=True)
with tempfile.TemporaryDirectory(prefix="urm-permission-probe-",dir=root) as td:
    for name,mode in (("default",None),("700",0o700),("777",0o777)):
        stage=Path(td)/name
        if mode is None:stage.mkdir()
        else:stage.mkdir(mode=mode)
        dest=stage/"Agent"/"_internal"
        dest.mkdir(parents=True)
        output=dest/"base_library.zip"
        shutil.copy2(source,output)
        print("ACL_CASE",name,"STAGE",str(stage),flush=True)
        for item in (stage,output):
            a=subprocess.run(["icacls.exe",str(item)],capture_output=True,text=True,errors="replace")
            print("ICACLS",a.stdout[-1100:],flush=True)
        probe=subprocess.run([sys.executable,"-c", "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); print('ZIP_OK',z.testzip())",str(output)],capture_output=True,text=True,errors="replace",timeout=15)
        print("READ_RESULT",name,probe.returncode,probe.stdout.strip(),probe.stderr[-500:],flush=True)
