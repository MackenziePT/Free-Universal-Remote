"""Standalone Secure MCP Tunnel runtime for explicit user-approved setups.

Usage: UniversalRemoteTunnel-Preview.exe run | stop | status
No command-line keys, admin privileges or inbound Internet listeners.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

from public_paths import product_home
from tunnel_manager import read_status, request_stop, run_supervisor

def component_paths() -> tuple[Path,Path]:
    root=(Path(sys.executable).resolve().parent.parent if getattr(sys,"frozen",False)
          else Path(__file__).resolve().parent)
    return (root/"bin"/"tunnel-client.exe",
            root/"Agent"/"UniversalRemoteAgent-Preview.exe")

def main()->int:
    if sys.argv[1:] not in (["run"],["stop"],["status"],["--self-test"]):
        print("Use: run | stop | status | --self-test")
        return 2
    state=product_home()/"tunnel"
    if sys.argv[1:]==["--self-test"]:
        import cryptography
        import tunnel_manager
        print("UNIVERSAL_REMOTE_TUNNEL_SELFTEST_OK")
        return 0
    if sys.argv[1:]==["status"]:
        print(json.dumps(read_status(state),sort_keys=True))
        return 0
    if sys.argv[1:]==["stop"]:
        request_stop(state)
        print("STOP_REQUESTED")
        return 0
    client,agent=component_paths()
    return run_supervisor(state,client,agent)

if __name__=="__main__":
    raise SystemExit(main())
