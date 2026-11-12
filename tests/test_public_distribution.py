"""First-run product installation boundaries (all storage disposable)."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from public_paths import config_for_root,write_initial_config,product_home,config_path

class PublicDistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="universal-public-test-")
        self.addCleanup(self.tmp.cleanup)
        env=patch.dict(os.environ,{"LOCALAPPDATA":self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.selected=Path(self.tmp.name)/"documents"/"workspace"

    @unittest.skipUnless(os.name=="nt","Requires Tk desktop")
    @unittest.skipIf(os.environ.get("URM_CI_HEADLESS")=="1",
                     "Real Tk desktop required; test separately on an interactive Windows runner")
    def test_five_step_first_run_consent_is_default_deny(self):
        from public_gui import Onboarding
        wizard=Onboarding()
        try:
            wizard.withdraw()
            self.assertEqual(wizard.step,0)
            self.assertTrue(wizard.prepare_powershell.get(),
                            'Latest stable PowerShell check should be selected by default')
            wizard.prepare_powershell.set(False)
            self.assertFalse(wizard.prepare_powershell.get(),
                             'A user must be able to opt out of optional downloads')
            wizard._next();self.assertEqual(wizard.step,1)
            wizard.selection.set(str(self.selected))
            wizard._next();self.assertEqual(wizard.step,2)
            self.assertFalse(any(value.get() for value in wizard.options.values()))
            wizard._next();self.assertEqual(wizard.step,3)
            wizard._next();self.assertEqual(wizard.step,4)
            wizard._next()
            self.assertTrue(wizard.completed)
            self.assertTrue(config_path().is_file())
            self.assertFalse((product_home()/"grants.json").exists())
        finally:
            from tkinter import TclError
            try:
                wizard.destroy()
            except TclError:
                pass

    def test_first_run_is_local_default_deny_and_exclusive(self):
        config=write_initial_config(self.selected)
        self.assertTrue(config.is_file())
        payload=json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual(payload["allowed_roots"],[str(self.selected.resolve())])
        self.assertTrue(self.selected.is_dir())
        for name in ("writes","shell","screen","input"):
            self.assertIs(payload["enable_"+name],False)
        self.assertFalse((product_home()/"grants.json").exists())
        data=config.read_bytes()
        with self.assertRaises(FileExistsError):
            write_initial_config(self.selected)
        self.assertEqual(config.read_bytes(),data)

    def test_preexisting_config_is_never_deleted_even_if_same_size(self):
        from public_paths import config_for_root
        contents=json.dumps(config_for_root(self.selected),ensure_ascii=False,indent=2)+"\n"
        file=config_path()
        file.parent.mkdir(parents=True)
        payload=b"Z"*len(contents.encode("utf-8"))
        file.write_bytes(payload)
        with self.assertRaises(FileExistsError):
            write_initial_config(self.selected)
        self.assertEqual(file.read_bytes(),payload)

    def test_first_run_creation_race_never_deletes_other_config(self):
        from pathlib import Path
        policy=config_for_root(self.selected)
        contents=json.dumps(policy,ensure_ascii=False,indent=2)+"\n"
        target=config_path()
        competitor=b"R"*len(contents.encode("utf-8"))
        def concurrent_create(src,dst,*args,**kwargs):
            if Path(dst)==target:
                target.write_bytes(competitor)
                raise FileExistsError("Concurrent configuration was created")
            raise AssertionError("Unexpected hardlink operation")
        with patch("public_paths.os.link",side_effect=concurrent_create):
            with self.assertRaises(FileExistsError):
                write_initial_config(self.selected)
        self.assertEqual(target.read_bytes(),competitor)

    def test_only_explicit_known_boolean_policies_are_accepted(self):
        with self.assertRaises(ValueError):config_for_root(self.selected,{"shell":"true"})
        with self.assertRaises(ValueError):config_for_root(self.selected,{"unknown":True})
        policy=config_for_root(self.selected,{"writes":True})
        self.assertIs(policy["enable_writes"],True)
        self.assertIs(policy["enable_shell"],False)

    def test_private_app_root_cannot_be_exposed_as_workspace(self):
        with self.assertRaises(ValueError):config_for_root(product_home())
        with self.assertRaises(ValueError):config_for_root(Path(self.tmp.name))

if __name__=="__main__":unittest.main()
