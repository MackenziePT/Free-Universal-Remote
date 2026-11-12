"""Installer and first-run dependency readiness; no system Python downloads."""
from __future__ import annotations
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import dependency_preflight as dp

class DependencyReadinessTests(unittest.TestCase):
    def test_source_developer_runtime_is_not_required_in_public_binary(self):
        with patch.object(sys,"frozen",False,create=True):
            row=dp.bundled_runtime_check()
        self.assertTrue(row.ok)
        self.assertTrue(row.required)

    def test_complete_portable_runtime_is_independent_of_global_python(self):
        with tempfile.TemporaryDirectory(prefix="urm-deps-") as tmp:
            base=Path(tmp)/"_internal";base.mkdir()
            for name in dp.BUNDLED_PYTHON_FILES:
                (base/name).write_bytes(b"fake only for test")
            with patch.object(sys,"frozen",True,create=True), \
                 patch.object(sys,"_MEIPASS",str(base),create=True), \
                 patch.dict(os.environ,{"PATH":str(Path(tmp)/"empty-bin")},clear=False):
                self.assertTrue(dp.bundled_runtime_check().ok)
                (base/"python314.dll").unlink()
                result=dp.bundled_runtime_check()
                self.assertFalse(result.ok)
                self.assertTrue(result.required)
                self.assertIn("Reparar",result.detail)

    def test_frozen_agent_is_checked_next_to_gui(self):
        with tempfile.TemporaryDirectory(prefix="urm-install-") as tmp:
            p=Path(tmp); (p/"GUI").mkdir(); (p/"Agent").mkdir()
            agent=p/"Agent"/"UniversalRemoteAgent-Preview.exe"
            with patch.object(sys,"frozen",True,create=True), \
                 patch.object(sys,"executable",str(p/"GUI"/"UniversalRemote-Preview.exe")):
                self.assertFalse(dp.local_agent_check().ok)
                agent.write_bytes(b"fake binary for fixture")
                self.assertTrue(dp.local_agent_check().ok)

    def test_unconfigured_first_run_is_not_missing_runtime(self):
        with tempfile.TemporaryDirectory(prefix="urm-config-") as tmp, \
             patch.dict(os.environ,{"LOCALAPPDATA":tmp}):
            row=dp.configuration_check()
            self.assertFalse(row.ok)
            self.assertFalse(row.required)
            self.assertFalse(dp.has_missing_required_dependencies([row]))

    def test_powershell_optional_not_blocking_or_installing(self):
        with tempfile.TemporaryDirectory(prefix="urm-power-") as tmp:
            env={"LOCALAPPDATA":tmp,"ProgramFiles":str(Path(tmp)/"Programs"),
                 "PATH":str(Path(tmp)/"other")}
            with patch.dict(os.environ,env):
                result=dp.powershell_check()
            self.assertFalse(result.ok)
            self.assertFalse(result.required)
            self.assertFalse(dp.has_missing_required_dependencies([result]))
            self.assertIn("Opcional",result.detail)

    def test_cannot_silently_install_python_or_edit_system_path(self):
        import inspect
        source=inspect.getsource(dp)
        self.assertNotIn("pip install",source)
        self.assertNotIn("setx",source.lower())
        self.assertNotIn("Invoke-WebRequest",source)

if __name__=="__main__":
    unittest.main()
