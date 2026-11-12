"""New-user readiness must never be confused with an active privileged grant."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import public_gui
from public_paths import PRIVILEGED, write_initial_config

class InitialControlPolicyTests(unittest.TestCase):
    def test_single_initial_consent_prepares_all_four_capabilities(self):
        proposal=getattr(public_gui,"recommended_first_run_permissions",None)
        self.assertTrue(callable(proposal),"First-run control preset must exist")
        self.assertEqual(proposal(),{name:True for name in PRIVILEGED})

    def test_prepared_policy_never_creates_an_active_session(self):
        proposal=getattr(public_gui,"recommended_first_run_permissions",None)
        self.assertTrue(callable(proposal))
        with tempfile.TemporaryDirectory(prefix="ur-consent-") as tmp:
            with patch.dict(os.environ,{"LOCALAPPDATA":tmp}):
                path=write_initial_config(Path(tmp)/"MyWork",proposal())
                saved=json.loads(path.read_text(encoding="utf-8"))
                for name in PRIVILEGED:
                    self.assertTrue(saved["enable_"+name])
                self.assertFalse(Path(saved["grants_path"]).exists(),
                    "An enabled capability is not consent to a remote session")

if __name__=="__main__":
    unittest.main()
