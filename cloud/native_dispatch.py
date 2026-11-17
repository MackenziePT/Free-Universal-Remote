"""Windows-specific approved dispatcher backed by existing Universal Remote RC5.1.

Importing this module performs no remote action, grants no permissions, and
never modifies the native MCP policy. The Windows-native `server` module
remains the sole authority for path security, capabilities, and journaled
at-most-once privileged operations.
"""
from __future__ import annotations

import base64
import json
import sys
from typing import Any


class NativeDenied(PermissionError):
    pass


REQUIRED_GRANTS = {
    "windows_diagnostic": None,
    "read_text_file": None,
    "run_powershell": "shell",
    "desktop_screenshot": "screen",
}


class NativeDispatcher:
    def __init__(self, *, native_server=None):
        if native_server is not None:
            self.native = native_server
        else:
            if sys.platform != "win32":
                raise NativeDenied("Universal Remote native dispatcher requires Windows")
            import server
            self.native = server

    def has_local_permission(self, method: str) -> bool:
        if method not in REQUIRED_GRANTS:
            return False
        try:
            policy=json.loads(self.native.agent_policy())
        except (TypeError,ValueError,RuntimeError,KeyError):
            return False
        if policy.get("requires_restart") is True:
            return False
        grant=REQUIRED_GRANTS[method]
        if grant is None:
            return True
        return policy.get("effective_permissions",{}).get(grant) is True

    def dispatch_local(self, method: str, args: dict) -> dict:
        if not self.has_local_permission(method):
            raise NativeDenied("Local Windows authorization absent or expired")
        if method=="windows_diagnostic":
            if not isinstance(args,dict) or set(args)!={"name"}:
                raise NativeDenied("Invalid diagnostics request")
            result=self.native.windows_diagnostic(args["name"])
            return json.loads(result)
        if method=="read_text_file":
            if not isinstance(args,dict) or set(args)!={"path"}:
                raise NativeDenied("Invalid path request")
            result=self.native.read_text_file(args["path"])
            return json.loads(result)
        if method=="run_powershell":
            if not isinstance(args,dict) or set(args)!={"command","operation_id"}:
                raise NativeDenied("Invalid PowerShell request")
            result=self.native.run_powershell(args["command"],args["operation_id"])
            return json.loads(result)
        if method=="desktop_screenshot":
            if not isinstance(args,dict) or set(args)!={"monitor","max_width"}:
                raise NativeDenied("Invalid screenshot request")
            image=self.native.desktop_screenshot(args["monitor"],args["max_width"])
            raw=getattr(image,"data",None)
            if not isinstance(raw,bytes) or len(raw)>1_350_000:
                raise NativeDenied("Screenshot missing or exceeds safe limit")
            return {"mime":"image/jpeg","base64":base64.b64encode(raw).decode("ascii")}
        raise NativeDenied("Unknown or prohibited native operation")
