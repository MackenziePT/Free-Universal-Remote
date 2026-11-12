"""Release tests: reject absent/corrupted or wrong-architecture embedded runtimes."""
import os
from pathlib import Path
import struct
import tempfile
import unittest

from dependency_preflight import BUNDLED_PYTHON_FILES
from tools.audit_bundled_runtime import audit_one, audit_all, pe_machine

def fake_pe(path:Path,machine:int=0x8664):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=bytearray(134)
    data[:2]=b"MZ"
    struct.pack_into("<I",data,0x3C,128)
    data[128:132]=b"PE\x00\x00"
    struct.pack_into("<H",data,132,machine)
    path.write_bytes(data)

class BundledRuntimeReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="urm-release-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"UniversalRemote-Preview"
        self.inner=self.root/"_internal"
        self.inner.mkdir(parents=True)
        fake_pe(self.root/"UniversalRemote-Preview.exe")
        for name in BUNDLED_PYTHON_FILES:
            (self.inner/name).write_bytes(b"test")
        fake_pe(self.inner/"python314.dll")

    def test_all_required_python_and_windows_runtime_files_detected(self):
        report=audit_one(self.root,"UniversalRemote-Preview.exe")
        self.assertTrue(report["embedded_python"])
        self.assertTrue(report["embedded_vc_runtime"])

    def test_missing_python_or_vc_runtime_blocks_release(self):
        for name in ("python314.dll","VCRUNTIME140.dll","ucrtbase.dll","base_library.zip"):
            file=self.inner/name
            value=file.read_bytes()
            try:
                file.unlink()
                with self.assertRaisesRegex(ValueError,"missing required"):
                    audit_one(self.root,"UniversalRemote-Preview.exe")
            finally:
                file.write_bytes(value)

    def test_wrong_architecture_blocks_release(self):
        fake_pe(self.inner/"python314.dll",0xAA64)
        with self.assertRaisesRegex(ValueError,"Wrong architecture"):
            audit_one(self.root,"UniversalRemote-Preview.exe")

    def test_corrupt_pe_blocked(self):
        (self.root/"UniversalRemote-Preview.exe").write_bytes(b"not executable")
        with self.assertRaisesRegex(ValueError,"Missing DOS/PE"):
            audit_one(self.root,"UniversalRemote-Preview.exe")

if __name__=="__main__":
    unittest.main()
