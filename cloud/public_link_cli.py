"""Windows user-session companion for the public Universal Remote gateway."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from .public_link import LinkConfig,LinkError,connect_windows,current_link_status,run_agent

STARTUP_NAME="UniversalRemoteFreePublicAgent"

def agent_command():
    if getattr(sys,"frozen",False):
        return '"'+str(Path(sys.executable).resolve())+'" --public-serve'
    return '"'+str(Path(sys.executable).resolve())+'" -m cloud.public_link_cli serve'

def configure_startup(enabled:bool, *, agreed:bool):
    if not agreed:raise LinkError("Owner must approve Windows startup")
    if sys.platform!="win32":raise LinkError("Only Windows supports this startup mode")
    if enabled and not getattr(sys,"frozen",False):
        raise LinkError("Startup requires an installed executable")
    import winreg
    key=r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_SET_VALUE) as reg:
        if enabled:winreg.SetValueEx(reg,STARTUP_NAME,0,winreg.REG_SZ,agent_command())
        else:
            try:winreg.DeleteValue(reg,STARTUP_NAME)
            except FileNotFoundError:pass

def main(argv=None):
    parser=argparse.ArgumentParser(prog="universal-remote-public-link")
    parser.add_argument("action",choices=["status","pair","serve","enable-startup","disable-startup"])
    parser.add_argument("--label",default=os.environ.get("COMPUTERNAME","Windows PC"))
    args=parser.parse_args(argv)
    if sys.platform!="win32":parser.error("Windows user session required")
    from .windows_identity import default_identity_path
    if args.action=="status":
        print(json.dumps(current_link_status(default_identity_path())))
    elif args.action=="pair":
        ident=connect_windows(LinkConfig.from_env(),args.label,note=print)
        print("Paired device:",ident)
    elif args.action=="serve":
        run_agent()
    elif args.action=="enable-startup":
        configure_startup(True,agreed=True)
    elif args.action=="disable-startup":
        configure_startup(False,agreed=True)
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except LinkError as ex:
        print(str(ex),file=sys.stderr)
        raise SystemExit(2)
