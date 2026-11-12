import base64
import json
from pathlib import Path
import tempfile
import time
import unittest
import zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from release_security import ReleaseError,verify_payload,verify_signed_release,UpdateLock,recover_update
from tools.sign_release_package import make_signed_package


class PublisherPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/"payload"
        self.source.mkdir()
        (self.source/"GUI").mkdir()
        (self.source/"Agent").mkdir()
        (self.source/"GUI"/"app.txt").write_text("hello",encoding="utf-8")
        (self.source/"Agent"/"agent.exe").write_bytes(bytes(range(256)))
        self.key=Ed25519PrivateKey.generate()
        pub=self.key.public_key().public_bytes(encoding=serialization.Encoding.Raw,
                                               format=serialization.PublicFormat.Raw)
        self.trust={"local-test-2026":base64.b64encode(pub).decode()}

    def publish(self, name):
        return make_signed_package(self.source,self.root/name,self.key,
             "local-test-2026","1.0.0-test.1",29,"windows-x64",now=int(time.time()))

    def test_package_is_verifiable_and_deterministic(self):
        a=self.publish("first")
        b=self.publish("second")
        first=Path(a["archive"]).read_bytes()
        second=Path(b["archive"]).read_bytes()
        self.assertEqual(first,second)
        m=verify_signed_release(Path(a["manifest"]).read_bytes(),
             Path(a["signature"]).read_text().strip(),self.trust,minimum_sequence=28)
        verify_payload(Path(a["archive"]),m)
        self.assertEqual(len(m["files"]),2)

    def test_invalid_symlink_refused(self):
        try:
            (self.source/"Agent"/"alias.txt").symlink_to(self.source/"GUI"/"app.txt")
        except (OSError,NotImplementedError):
            self.skipTest("OS does not permit test symlink")
        with self.assertRaises(ReleaseError):
            self.publish("unsafe")

    def test_concurrent_update_rejected(self):
        state=self.root/"state"
        with UpdateLock(state):
            with self.assertRaises(ReleaseError):
                with UpdateLock(state):
                    pass
        with UpdateLock(state):
            pass

    def test_committed_crash_cleanup_does_not_rollback(self):
        install=self.root/"installed"
        install.mkdir()
        (install/"app.txt").write_text("new",encoding="utf-8")
        state=self.root/"state"
        state.mkdir()
        txn="c"*32
        backup=self.root/(".ur-backup-"+txn)
        backup.mkdir()
        (backup/"app.txt").write_text("old",encoding="utf-8")
        (state/"update.pending.json").write_text(json.dumps({"transaction":txn,"sequence":29}))
        (state/"update-state.json").write_text(json.dumps({"sequence":29}))
        self.assertTrue(recover_update(install,state))
        self.assertEqual((install/"app.txt").read_text(),"new")
        self.assertEqual((backup/"app.txt").read_text(),"old")


if __name__=="__main__":
    unittest.main()
