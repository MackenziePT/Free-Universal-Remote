"""Client MCP configuration must reference installed, bundled agent (not developer Python)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import universal_remote_ui as ui

class PublicMcpConfigTests(unittest.TestCase):
    def test_frozen_gui_exports_sibling_agent_executable_without_python(self):
        with tempfile.TemporaryDirectory(prefix="urm-gui-bind-") as tmp:
            app=Path(tmp)/"application"
            ui_dir=app/"GUI"
            agent_dir=app/"Agent"
            ui_dir.mkdir(parents=True)
            agent_dir.mkdir()
            exe=agent_dir/"UniversalRemoteAgent-Preview.exe"
            exe.write_bytes(b"test fake only")
            with patch.object(sys,"frozen",True,create=True), \
                 patch.object(sys,"executable",str(ui_dir/"UniversalRemote-Preview.exe")):
                config=ui.local_mcp_config()
            definition=config["mcpServers"]["universal-remote"]
            self.assertEqual(definition["command"],str(exe))
            self.assertEqual(definition["args"],[])
            self.assertNotIn(".venv",str(config))
            self.assertNotIn("launch_server.py",str(config))
            self.assertNotIn("config.json",str(config))

    def test_frozen_gui_refuses_missing_agent_binary(self):
        with tempfile.TemporaryDirectory(prefix="urm-gui-noagent-") as tmp:
            with patch.object(sys,"frozen",True,create=True), \
                 patch.object(sys,"executable",str(Path(tmp)/"GUI"/"UniversalRemote-Preview.exe")):
                with self.assertRaises(FileNotFoundError):
                    ui.local_mcp_config()

    def test_development_config_uses_public_agent_not_legacy_launcher(self):
        with patch.object(sys,"frozen",False,create=True):
            config=ui.local_mcp_config()
        definition=config["mcpServers"]["universal-remote"]
        self.assertEqual(definition["command"],sys.executable)
        self.assertEqual(Path(definition["args"][0]).name,"public_agent.py")
        self.assertNotIn("HARMONY_MCP_CONFIG",str(definition))

if __name__=="__main__":unittest.main()
