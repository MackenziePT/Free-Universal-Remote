"""Exercise the real RC5.1 Windows dispatcher with disposable read-only roots."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Native Universal Remote is Windows-only")
def test_native_bridge_enforces_readonly_sandbox(tmp_path: Path):
    allowed = tmp_path / "approved"
    allowed.mkdir()
    sample = allowed / "probe.txt"
    sample.write_text("NATIVE_BRIDGE_PROBE_2026", encoding="utf-8")
    policy = {
        "allowed_roots": [str(allowed)],
        "enable_writes": False,
        "enable_shell": False,
        "enable_screen": False,
        "enable_input": False,
        "max_read_bytes": 65536,
        "max_write_bytes": 65536,
        "max_command_seconds": 10,
        "backup_root": str(tmp_path / "backups"),
        "grants_path": str(tmp_path / "grants.json"),
    }
    config = tmp_path / "config.json"
    config.write_text(json.dumps(policy), encoding="utf-8")
    env = dict(os.environ, HARMONY_MCP_CONFIG=str(config),
               UNIVERSAL_REMOTE_DATA_HOME=str(tmp_path / "runtime"))
    script = '''
import json,sys
from cloud.native_dispatch import NativeDispatcher, NativeDenied
bridge=NativeDispatcher()
assert bridge.has_local_permission("read_text_file") is True
assert bridge.has_local_permission("run_powershell") is False
answer=bridge.dispatch_local("read_text_file", {"path":sys.argv[1]})
assert "NATIVE_BRIDGE_PROBE_2026" in json.dumps(answer)
try:
    bridge.dispatch_local("run_powershell", {"command":"Write-Output forbidden", "operation_id":"00000000-0000-4000-8000-000000000000"})
except NativeDenied:
    pass
else:
    raise AssertionError("Shell action bypassed local policy")
print("NATIVE_BRIDGE_READ_ONLY_OK")
'''
    run = subprocess.run([sys.executable, "-c", script, str(sample)], cwd=Path(__file__).resolve().parents[1],
                         env=env, timeout=30, capture_output=True, text=True)
    assert run.returncode == 0, f"Exit {run.returncode}: {run.stderr[-1500:]}"
    assert "NATIVE_BRIDGE_READ_ONLY_OK" in run.stdout
