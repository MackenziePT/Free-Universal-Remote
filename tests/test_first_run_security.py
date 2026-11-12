"""Security regressions for first-run path validation and crash-safe publication."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from public_paths import config_for_root,write_initial_config,product_home,config_path
from remote_core import PolicyError

class FirstRunSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="urm-config-security-")
        self.addCleanup(self.tmp.cleanup)
        env=patch.dict(os.environ,{"LOCALAPPDATA":self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.work=Path(self.tmp.name)/"work"

    @unittest.skipUnless(os.name=="nt","Windows symlink handling")
    def test_workspace_symlink_is_rejected_before_resolution(self):
        real=Path(self.tmp.name)/"real"
        real.mkdir()
        alias=Path(self.tmp.name)/"alias"
        try:
            alias.symlink_to(real,target_is_directory=True)
        except OSError as exc:
            self.skipTest("Windows symlink unavailable: "+str(exc))
        with self.assertRaises((PolicyError,ValueError)):
            config_for_root(alias)
        with self.assertRaises((PolicyError,ValueError)):
            config_for_root(alias/"nested")
        self.assertFalse((real/"nested").exists())

    @unittest.skipUnless(os.name=="nt","Windows paths only")
    def test_rejects_windows_reserved_names_and_ads(self):
        for invalid in (str(self.work)+":stream","C:\\CON\\data","C:\\NUL.txt",
                        "C:\\workspace\\trailing."):
            with self.subTest(path=invalid):
                with self.assertRaises((PolicyError,ValueError)):
                    config_for_root(invalid)

    def test_atomic_creation_does_not_publish_invalid_config(self):
        with patch("remote_core.load_config",side_effect=PolicyError("simulated reject")):
            with self.assertRaises(PolicyError):
                write_initial_config(self.work)
        self.assertFalse(config_path().exists())

    def test_competing_creation_preserves_the_competitor(self):
        target=config_path()
        original_link=os.link
        def concurrent_copy(src,dst,*a,**kw):
            assert Path(dst)==target
            target.write_bytes(b"CONCURRENT CONFIG, PRESERVE THIS FILE")
            raise FileExistsError("Second instance already created config")
        with patch("public_paths.os.link",side_effect=concurrent_copy):
            with self.assertRaises(FileExistsError):
                write_initial_config(self.work)
        self.assertEqual(target.read_bytes(),b"CONCURRENT CONFIG, PRESERVE THIS FILE")

    def test_config_is_atomically_published_without_remaining_stage(self):
        config=write_initial_config(self.work)
        self.assertTrue(config.is_file())
        self.assertEqual(list(config.parent.glob(".init-*.tmp")),[])
        self.assertFalse((product_home()/"grants.json").exists())

if __name__=="__main__":
    unittest.main()
