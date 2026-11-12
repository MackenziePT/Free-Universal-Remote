import base64
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from tools.build_pinned_updater import read_public_keyring,prepare_sources
from release_security import ReleaseError


class PinnedUpdaterBuildTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix="ur-public-trust-build-")
        self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        k=Ed25519PrivateKey.generate()
        self.pub=base64.b64encode(k.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode("ascii")
        self.keyring=self.root/"publisher-keys-public.json"
        self.keyring.write_text(json.dumps({"format":1,"product":"universal-remote",
                    "keys":{"publisher-key-1":self.pub}}),encoding="utf-8")

    def test_valid_external_public_keyring(self):
        ring=read_public_keyring(self.keyring)
        self.assertEqual(ring["publisher-key-1"],self.pub)

    def test_bad_keyring_denied(self):
        self.keyring.write_text(json.dumps({"format":1,"product":"wrong",
                                            "keys":{"publisher-key-1":self.pub}}))
        with self.assertRaises(ReleaseError):
            read_public_keyring(self.keyring)

    def test_publisher_source_contains_only_public_anchor_and_production_mode(self):
        dest=self.root/"generated-src"
        prepare_sources(dest,read_public_keyring(self.keyring))
        anchor=(dest/"release_trust_anchor.py").read_text()
        self.assertIn('RELEASE_CHANNEL = "PRODUCTION"',anchor)
        self.assertIn(self.pub,anchor)
        self.assertIn("PUBLISHER_KEYRING",anchor)
        self.assertFalse(any(x in anchor for x in ("PRIVATE KEY", "BEGIN RSA", "BEGIN OPENSSH")))
        with self.assertRaises(FileExistsError):
            prepare_sources(dest,read_public_keyring(self.keyring))

if __name__=="__main__":
    unittest.main()
