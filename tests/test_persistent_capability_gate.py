"""Regression: a temporary grant never overrides a permanently disabled capability.

This test imports the real server with synthetic MCP types and disposable config.
No privileged Windows operations, desktop input, or shell commands are invoked.
"""
from __future__ import annotations
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
import uuid
from unittest.mock import Mock,patch

class FakeFastMCP:
    def __init__(self,*args,**kwargs):self.tools={}
    def tool(self,annotations=None):
        def apply(call):self.tools[call.__name__]=call;return call
        return apply

class PersistentFlagTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="urm-permission-gate-")
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        work=base/"workspace"
        work.mkdir()
        self.cfg=base/"config.json"
        self.cfg.write_text(json.dumps({
            "allowed_roots":[str(work)],
            "backup_root":str(base/"backup"),
            "grants_path":str(base/"grants.json"),
            "enable_writes":False,
            "enable_shell":False,
            "enable_screen":False,
            "enable_input":False,
        }),encoding="utf-8")
        (base/"grants.json").write_text(json.dumps({
            "expires_at":time.time()+300,
            "capabilities":["writes","shell","screen","input"]
        }),encoding="utf-8")
        fake=types.ModuleType("mcp")
        srv=types.ModuleType("mcp.server")
        fast=types.ModuleType("mcp.server.fastmcp")
        fast.FastMCP=FakeFastMCP
        fast.Image=type("Image",(),{})
        spec=importlib.util.spec_from_file_location(
            "isolated_capability_checks_"+uuid.uuid4().hex,
            Path(__file__).resolve().parents[1]/"server.py")
        mod=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{"mcp":fake,"mcp.server":srv,"mcp.server.fastmcp":fast}),\
             patch.dict(os.environ,{"HARMONY_MCP_CONFIG":str(self.cfg),"LOCALAPPDATA":self.temp.name}),\
             patch("logging.handlers.RotatingFileHandler",return_value=logging.NullHandler()):
            spec.loader.exec_module(mod)
        self.server=mod

    def test_temporary_grant_cannot_activate_disabled_mutating_capability(self):
        from remote_core import PolicyError
        for name in ("writes","shell","input"):
            with self.subTest(capability=name):
                callback=Mock(return_value={"unexpected":"side-effect"})
                with patch.object(self.server,"execute_once",side_effect=lambda *args:callback()):
                    with self.assertRaises(self.server.PolicyError):
                        self.server._guarded(name,str(uuid.uuid4()),"synthetic",callback)
                callback.assert_not_called()

    def test_disabled_shell_cannot_list_task_metadata_with_stale_grant(self):
        fake_tasks=Mock()
        fake_tasks.list_jobs.return_value=[]
        fake_tasks.status.return_value={"status":"running"}
        fake_tasks.output.return_value={"text":"private"}
        with patch.object(self.server,"_tasks",return_value=fake_tasks):
            for name,args in (
                ("list_tasks",{"limit":1}),
                ("task_status",{"job_id":str(uuid.uuid4())}),
                ("task_output",{"job_id":str(uuid.uuid4()),"limit":64})
            ):
                with self.subTest(tool=name):
                    with self.assertRaises(self.server.PolicyError):
                        getattr(self.server,name)(**args)
        fake_tasks.list_jobs.assert_not_called()
        fake_tasks.status.assert_not_called()
        fake_tasks.output.assert_not_called()

    def test_unknown_capabilities_are_not_executable(self):
        from remote_core import PolicyError
        with self.assertRaises(self.server.PolicyError):
            self.server._guarded("administrator",str(uuid.uuid4()),"x",lambda:None)

if __name__=="__main__":
    unittest.main()
