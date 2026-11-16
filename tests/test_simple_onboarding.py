"""First-run guidance smoke test on local Windows GUI (no policy is saved)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

@unittest.skipUnless(os.name=="nt" and os.environ.get("URM_CI_HEADLESS")!="1",
                      "Requires interactive Windows GUI")
class SimpleOnboardingTests(unittest.TestCase):
    def test_three_screens_and_no_hidden_permissions(self):
        with tempfile.TemporaryDirectory(prefix="urm-wizard-test-") as tmp:
            with patch.dict(os.environ,{"LOCALAPPDATA":tmp}):
                from public_gui import Onboarding
                app=Onboarding()
                try:
                    app.withdraw()
                    app.selection.set(str(Path(tmp)/"workspace"))
                    self.assertEqual(app.step,0)
                    app._next()
                    self.assertEqual(app.step,1)
                    self.assertFalse(app.show_advanced.get())
                    self.assertTrue(all(v.get() for v in app.options.values()))
                    app._next()
                    self.assertEqual(app.step,2)
                    self.assertFalse((Path(tmp)/"UniversalRemote"/"config.json").exists())
                finally:
                    app.destroy()
if __name__=="__main__": unittest.main()
