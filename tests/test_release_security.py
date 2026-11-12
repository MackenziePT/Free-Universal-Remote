import base64
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from release_security import (ReleaseError, verify_signed_release,
                              verify_payload, apply_signed_update,
                              recover_update, _canonical)


class SignedUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = Ed25519PrivateKey.generate()
        pub = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
        self.keys = {"publisher-2026": base64.b64encode(pub).decode()}
        self.target = self.root / "installed"
        self.state = self.root / "state"

    def candidate(self, files=None, sequence=10):
        if files is None: files = {"main.txt": b"updated"}
        archive = self.root / f"candidate-{sequence}.zip"
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
            for name,data in files.items():
                z.writestr(name,data)
        data = archive.read_bytes()
        now = int(time.time())
        metadata = {"format": 1, "product": "universal-remote",
            "key_id":"publisher-2026", "sequence": sequence,
            "issued_at":now-60,"expires_at":now+3600,
            "version":f"1.0.{sequence}","platform":"windows-x64",
            "archive_sha256":hashlib.sha256(data).hexdigest(),"archive_bytes":len(data),
            "files":{k:{"sha256":hashlib.sha256(v).hexdigest(),"bytes":len(v)}
                     for k,v in files.items()}}
        signature = base64.b64encode(self.private.sign(_canonical(metadata))).decode()
        return archive, _canonical(metadata), signature

    def test_good_signed_release_and_payload(self):
        archive, metadata, sig = self.candidate()
        m=verify_signed_release(metadata,sig,self.keys,minimum_sequence=0)
        verify_payload(archive,m)

    def test_signature_and_trust_rejections(self):
        archive, metadata, sig = self.candidate()
        with self.assertRaises(ReleaseError):
            verify_signed_release(metadata,sig,{"untrusted":next(iter(self.keys.values()))},minimum_sequence=0)
        with self.assertRaises(ReleaseError):
            verify_signed_release(metadata,sig,self.keys,minimum_sequence=10)
        mutated=json.loads(metadata)
        mutated["version"]="1.0.evil"
        with self.assertRaises(ReleaseError):
            verify_signed_release(_canonical(mutated),sig,self.keys,minimum_sequence=0)

    def test_payload_tampering_rejected_before_install(self):
        archive, metadata, sig = self.candidate()
        with zipfile.ZipFile(archive,"w") as z: z.writestr("main.txt",b"tampered")
        with self.assertRaises(ReleaseError):
            verify_payload(archive,verify_signed_release(metadata,sig,self.keys,minimum_sequence=0))
        self.assertFalse(self.target.exists())

    def test_zip_traversal_rejected(self):
        archive, metadata, sig = self.candidate({"../outside.txt":b"bad"})
        with self.assertRaises(ReleaseError):
            verify_signed_release(metadata,sig,self.keys,minimum_sequence=0)

    def test_success_switch_and_no_downgrade(self):
        self.target.mkdir()
        (self.target/"main.txt").write_text("old",encoding="utf-8")
        archive, metadata, sig=self.candidate()
        outcome=apply_signed_update(target=self.target,state_dir=self.state,archive=archive,
            metadata_bytes=metadata,signature_b64=sig,trusted_keys=self.keys,
            platform="windows-x64",health_check=lambda t:(t/"main.txt").read_text()=="updated")
        self.assertTrue(outcome["ok"])
        self.assertEqual((self.target/"main.txt").read_text(),"updated")
        self.assertEqual((Path(outcome["backup"])/"main.txt").read_text(),"old")
        with self.assertRaises(ReleaseError):
            apply_signed_update(target=self.target,state_dir=self.state,archive=archive,
                metadata_bytes=metadata,signature_b64=sig,trusted_keys=self.keys,
                platform="windows-x64",health_check=lambda t:True)

    def test_failed_health_rolls_back(self):
        self.target.mkdir()
        (self.target/"main.txt").write_text("old",encoding="utf-8")
        archive, metadata, sig=self.candidate()
        with self.assertRaises(ReleaseError):
            apply_signed_update(target=self.target,state_dir=self.state,archive=archive,
                metadata_bytes=metadata,signature_b64=sig,trusted_keys=self.keys,
                platform="windows-x64",health_check=lambda t:False)
        self.assertEqual((self.target/"main.txt").read_text(),"old")
        self.assertFalse((self.state/"update.pending.json").exists())

    def test_first_install_failed_health_not_left_active(self):
        archive, metadata, sig=self.candidate()
        with self.assertRaises(ReleaseError):
            apply_signed_update(target=self.target,state_dir=self.state,archive=archive,
                metadata_bytes=metadata,signature_b64=sig,trusted_keys=self.keys,
                platform="windows-x64",health_check=lambda t:False)
        self.assertFalse(self.target.exists(), "Failed first install must not be promoted")

    def test_interruption_before_backup_preserves_previous_version(self):
        # Regression: journal fsync succeeds; process crashes BEFORE old dir is moved.
        self.target.mkdir()
        (self.target/"main.txt").write_text("old")
        self.state.mkdir()
        txn="b"*32
        (self.state/"update.pending.json").write_text(
            json.dumps({"transaction":txn,"sequence":12,"had_previous":True}))
        stage=self.root/(".ur-stage-"+txn)
        stage.mkdir()
        (stage/"main.txt").write_text("candidate")
        self.assertTrue(recover_update(self.target,self.state))
        self.assertEqual((self.target/"main.txt").read_text(),"old")
        self.assertFalse(stage.exists())
        self.assertFalse((self.state/"update.pending.json").exists())

    def test_recovery_after_interrupted_switch(self):
        self.target.mkdir()
        (self.target/"main.txt").write_text("old")
        transaction="a"*32
        backup=self.root/(".ur-backup-"+transaction)
        self.target.rename(backup)
        self.target.mkdir()
        (self.target/"main.txt").write_text("bad")
        self.state.mkdir()
        (self.state/"update.pending.json").write_text(json.dumps({"transaction":transaction,"sequence":11}))
        self.assertTrue(recover_update(self.target,self.state))
        self.assertEqual((self.target/"main.txt").read_text(),"old")
        self.assertTrue((self.root/(".ur-failed-"+transaction)).is_dir())


if __name__=="__main__":
    unittest.main()
