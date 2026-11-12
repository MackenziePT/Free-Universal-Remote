"""Server import must not change Python root logging or capture third-party logs."""
from __future__ import annotations
import importlib.util
import json,logging,os,sys,tempfile,types,unittest,uuid
from pathlib import Path
from unittest.mock import patch

class FakeFastMCP:
    def __init__(self,*a,**kw):self.tools={}
    def tool(self,annotations=None):
        def wrap(fn):self.tools[fn.__name__]=fn;return fn
        return wrap

class LogIsolationTest(unittest.TestCase):
    def test_import_does_not_change_global_logger(self):
        with tempfile.TemporaryDirectory(prefix="urm-privacy-log-") as tmp:
            root=Path(tmp)/"work";root.mkdir()
            cfg=Path(tmp)/"config.json"
            cfg.write_text(json.dumps({
                "allowed_roots":[str(root)],
                "grants_path":str(Path(tmp)/"grants.json"),
                "backup_root":str(Path(tmp)/"backups"),
            }),encoding="utf-8")
            fake=types.ModuleType("mcp")
            srv=types.ModuleType("mcp.server")
            fast=types.ModuleType("mcp.server.fastmcp")
            fast.FastMCP=FakeFastMCP
            fast.Image=type("Image",(),{})
            spec=importlib.util.spec_from_file_location(
                "isolated_privacy_logger_"+uuid.uuid4().hex,
                Path(__file__).resolve().parents[1]/"server.py")
            mod=importlib.util.module_from_spec(spec)
            root_logger=logging.getLogger()
            original_handlers=list(root_logger.handlers)
            original_level=root_logger.level
            with patch.dict(sys.modules,{"mcp":fake,"mcp.server":srv,"mcp.server.fastmcp":fast}),\
                 patch.dict(os.environ,{"HARMONY_MCP_CONFIG":str(cfg),
                                        "UNIVERSAL_REMOTE_DATA_HOME":tmp}),\
                 patch("logging.handlers.RotatingFileHandler",return_value=logging.NullHandler()):
                spec.loader.exec_module(mod)
                self.assertEqual(root_logger.level,original_level,
                    "Import must not globally change third-party logging level")
                self.assertEqual(list(root_logger.handlers),original_handlers,
                    "Import must not attach product private logs to global logger")
                self.assertIsInstance(mod.LOGGER,logging.Logger)
                self.assertFalse(mod.LOGGER.propagate,
                    "External SDK logs must not propagate to Universal Remote file")
                self.assertEqual(len(mod.LOGGER.handlers),1)
                self.assertTrue(json.loads(mod.ping())["alive"])

if __name__=="__main__": unittest.main()
