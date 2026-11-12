"""Subprocess engine verification using a disposable Windows profile."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from connection_doctor import check_current_local_engine

class EngineRealSubprocessTests(unittest.TestCase):
    @unittest.skipUnless(os.name=="nt","Windows-specific standalone agent")
    def test_agent_health_and_policy_version_from_disposable_profile(self):
        with tempfile.TemporaryDirectory(prefix="urm-engine-e2e-") as temp:
            with patch.dict(os.environ,{"LOCALAPPDATA":temp}):
                from public_paths import write_initial_config
                write_initial_config(Path(temp)/"workspace")
                outcome=check_current_local_engine()
                self.assertEqual(outcome.code,"READY",
                                 outcome.code+": "+outcome.detail)

if __name__=="__main__":unittest.main()
