import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import public_update_cli as updater
from release_security import ReleaseError

class TrustAnchorTests(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate()
        self.key_b64=base64.b64encode(self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)).decode('ascii')
        self.temp=tempfile.TemporaryDirectory(prefix='urm-anchor-test-')
        self.addCleanup(self.temp.cleanup)
        self.store=Path(self.temp.name)/'test-keyring.json'
        self.store.write_text(json.dumps({'format':1,'product':'universal-remote',
                                          'keys':{'testonly':self.key_b64}}))

    def test_private_qa_accepts_explicit_disposable_key(self):
        with patch.object(updater,'RELEASE_CHANNEL','PRIVATE_QA'):
            self.assertEqual(updater.trusted_keys(self.store),{'testonly':self.key_b64})

    def test_private_qa_missing_store_is_denied(self):
        with patch.object(updater,'RELEASE_CHANNEL','PRIVATE_QA'):
            with self.assertRaises(ReleaseError):
                updater.trusted_keys(None)

    def test_production_ignores_caller_and_embeds_only_pinned_key(self):
        with patch.object(updater,'RELEASE_CHANNEL','PRODUCTION'),patch.object(
                updater,'PUBLISHER_KEYRING',{'legitimate':self.key_b64}):
            self.assertEqual(updater.trusted_keys(None),{'legitimate':self.key_b64})
            with self.assertRaises(ReleaseError):
                updater.trusted_keys(self.store)

    def test_production_missing_anchor_fails_closed(self):
        with patch.object(updater,'RELEASE_CHANNEL','PRODUCTION'),patch.object(
                updater,'PUBLISHER_KEYRING',{}):
            with self.assertRaises(ReleaseError):
                updater.trusted_keys(None)

    def test_unknown_build_channel_is_denied(self):
        with patch.object(updater,'RELEASE_CHANNEL','UNVERIFIED'):
            with self.assertRaises(ReleaseError):
                updater.trusted_keys(self.store)

    def test_key_integrity_malformed_rejected(self):
        with patch.object(updater,'RELEASE_CHANNEL','PRODUCTION'):
            for bad in ('!', base64.b64encode(b'X'*31).decode(), 43):
                with self.subTest(bad=bad):
                    with patch.object(updater,'PUBLISHER_KEYRING',{'x':bad}):
                        with self.assertRaises(ReleaseError):
                            updater.trusted_keys(None)

if __name__=='__main__':
    unittest.main()
