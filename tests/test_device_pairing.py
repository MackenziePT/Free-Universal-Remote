import base64
from pathlib import Path
import tempfile
import unittest
import time
import uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from device_pairing import (PairingRegistry,PairingError,client_signature_message,
                            pairing_signature_message,TOOL_SCOPES)


class DevicePairingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now=1_800_000_000
        self.registry=PairingRegistry(Path(self.temp.name),clock=lambda:self.now)
        self.key=Ed25519PrivateKey.generate()
        self.pub=base64.b64encode(self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)).decode()

    def enroll(self, scopes=None):
        started=self.registry.begin(self.pub,"Test computer")
        with self.assertRaises(PairingError):
            self.registry.approve_local(started["request_id"],{"read"})
        sig=base64.b64encode(self.key.sign(
            pairing_signature_message(started["request_id"],started["challenge"]))).decode()
        self.registry.finish(started["request_id"],sig)
        return self.registry.approve_local(started["request_id"],set(scopes or {"read"}),
                                           presence_confirmed=True)["client_id"]

    def proof(self, client_id, method="read_text_file", args=None, nonce=None, timestamp=None):
        args={"path":"C:\\test"} if args is None else args
        nonce=nonce or str(uuid.uuid4())
        timestamp=self.now if timestamp is None else timestamp
        msg=client_signature_message(client_id,method,args,nonce,timestamp)
        return {"client_id":client_id,"nonce":nonce,"timestamp":timestamp,
                "signature":base64.b64encode(self.key.sign(msg)).decode()}

    def test_pairing_requires_key_proof_and_local_confirmation(self):
        started=self.registry.begin(self.pub,"My laptop")
        self.assertEqual(len(self.registry.list_pending_local()),1)
        with self.assertRaises(PairingError):
            self.registry.finish(started["request_id"],base64.b64encode(b"0"*64).decode())
        self.assertFalse(self.registry.list_pending_local()[0]["proved"])
        with self.assertRaises(PairingError):
            self.registry.approve_local(started["request_id"],{"read"},presence_confirmed=True)

    def test_positive_call_and_replay_rejected(self):
        client=self.enroll()
        args={"path":"C:\\test"}
        proof=self.proof(client,args=args)
        self.registry.verify_call("read_text_file",args,proof)
        with self.assertRaises(PairingError):
            self.registry.verify_call("read_text_file",args,proof)

    def test_scope_and_payload_binding(self):
        client=self.enroll()
        args={"path":"C:\\test"}
        with self.assertRaises(PairingError):
            self.registry.verify_call("write_text_file",args,self.proof(client,"write_text_file",args))
        with self.assertRaises(PairingError):
            self.registry.verify_call("read_text_file",{"path":"C:\\other"},self.proof(client,args=args))

    def test_revocation_and_expiry(self):
        client=self.enroll()
        args={"path":"C:\\test"}
        with self.assertRaises(PairingError):
            self.registry.verify_call("read_text_file",args,self.proof(client,timestamp=self.now-61))
        self.registry.revoke_local(client)
        with self.assertRaises(PairingError):
            self.registry.verify_call("read_text_file",args,self.proof(client))

    def test_pending_rate_and_expiry(self):
        for i in range(5):
            k=Ed25519PrivateKey.generate()
            pub=base64.b64encode(k.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)).decode()
            self.registry.begin(pub,f"device {i}")
        k=Ed25519PrivateKey.generate()
        pub=base64.b64encode(k.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)).decode()
        with self.assertRaises(PairingError):self.registry.begin(pub,"sixth")
        self.now+=121
        self.assertEqual(len(self.registry.list_pending_local()),0)
        self.registry.begin(pub,"new request")

    def test_every_existing_tool_classified(self):
        self.assertEqual(TOOL_SCOPES["run_powershell"],"shell")
        self.assertEqual(TOOL_SCOPES["desktop_action"],"input")
        self.assertEqual(TOOL_SCOPES["agent_policy"],"read")
        with self.assertRaises(PairingError):
            self.registry.verify_call("unknown_action",{},{})


if __name__=="__main__":
    unittest.main()
