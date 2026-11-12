"""Private tunnel supervision: contracts for safe, user-approved recovery."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from tunnel_manager import (
    TunnelConfigError, next_retry_seconds, summarize_transport,
    provision_profile, store_private_key, load_private_key,
    write_status, read_status, verify_tunnel_client
)

FAKE_ID="tunnel_"+"1"*32
FAKE_KEY="sk-"+"testOnly_"*6

class TunnelManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="urm-tunnel-supervisor-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_bounded_backoff_and_reset(self):
        self.assertEqual([next_retry_seconds(n,jitter=lambda:0) for n in (1,2,3,4)],
                         [5,10,20,40])
        self.assertLessEqual(next_retry_seconds(25,jitter=lambda:1),360)
        self.assertEqual(next_retry_seconds(4,stable_seconds=130,jitter=lambda:0),5)

    def test_invalid_tunnel_id_and_key_never_launch_client(self):
        with patch("tunnel_manager.subprocess.run") as call:
            with self.assertRaises(TunnelConfigError):
                provision_profile("invalid", FAKE_KEY, self.root, self.root/"agent.exe",self.root/"tunnel-client.exe")
            with self.assertRaises(TunnelConfigError):
                provision_profile(FAKE_ID,"123",self.root,self.root/"agent.exe",self.root/"tunnel-client.exe")
        call.assert_not_called()

    def test_signed_binary_pinned_hash_is_required(self):
        client=self.root/"tunnel-client.exe"
        client.write_bytes(b"not a real verified client")
        with self.assertRaises(TunnelConfigError):
            verify_tunnel_client(client)

    def test_bundled_official_client_integrity(self):
        client=Path(__file__).resolve().parents[1]/"bin"/"tunnel-client.exe"
        self.assertTrue(client.is_file())
        verify_tunnel_client(client)

    @unittest.skipUnless(__import__("os").name=="nt","Windows DPAPI only")
    def test_key_is_encrypted_per_windows_user(self):
        secret="sk-DO_NOT_DISCLOSE_1234567890_"
        state=self.root/"state"
        store_private_key(state,secret)
        encoded=(state/"tunnel-key.dpapi").read_bytes()
        self.assertNotIn(secret.encode(),encoded)
        self.assertEqual(load_private_key(state),secret)

    def test_local_ready_must_not_impersonate_chatgpt_connection(self):
        status=summarize_transport({"state":"RUNNING_LOCAL","updated_at":int(time.time()),"attempt":0})
        self.assertEqual(status["code"],"LOCAL_READY")
        self.assertFalse(status["chatgpt_confirmed"])
        self.assertIn("ChatGPT",status["detail"])
        retry=summarize_transport({"state":"RETRYING","updated_at":int(time.time()),
                                   "attempt":2,"retry_in":10})
        self.assertEqual(retry["code"],"RECONNECTING")
        self.assertFalse(retry["chatgpt_confirmed"])

    def test_stale_status_never_claims_running(self):
        folder=self.root/"state"
        write_status(folder,"RUNNING_LOCAL",attempt=0)
        m=(folder/"tunnel-status.json")
        original=json.loads(m.read_text())
        original["updated_at"]=int(time.time())-500
        m.write_text(json.dumps(original))
        self.assertEqual(read_status(folder)["code"],"UNKNOWN")

    @unittest.skipUnless(__import__("os").name=="nt","Windows DPAPI only")
    def test_windows_command_with_spaces_is_quoted_for_tunnel_client(self):
        import subprocess
        import tunnel_manager as tm
        folder=self.root/"Program Files"/"Universal Remote"
        folder.mkdir(parents=True)
        agent=folder/"UniversalRemoteAgent-Preview.exe"
        agent.write_bytes(b"placeholder")
        client=self.root/"tunnel-client.exe"
        client.write_bytes(b"placeholder")
        profile=self.root/"universal-remote-preview.yaml"
        def init(args,**kwargs):
            value=args[args.index("--mcp-command")+1]
            self.assertEqual(value,subprocess.list2cmdline([str(agent)]))
            profile.write_text("tunnel_id: "+FAKE_ID+"\\n"
                "api_key: env:CONTROL_PLANE_API_KEY\\n"
                "command: "+str(agent)+"\\n",encoding="utf-8")
            return subprocess.CompletedProcess(args,0)
        with (patch.object(tm,"profile_path",return_value=profile),
              patch.object(tm,"verify_tunnel_client"),
              patch.object(tm.subprocess,"run",side_effect=init)):
            tm.provision_profile(FAKE_ID,FAKE_KEY,self.root/"key_state",agent,client)

    def test_one_time_setup_never_includes_token_in_client_arguments(self):
        import subprocess
        import tunnel_manager as tm
        agent=self.root/"UniversalRemoteAgent-Preview.exe"
        agent.write_bytes(b"test executable placeholder")
        client=self.root/"tunnel-client.exe"
        client.write_bytes(b"fake pinned binary")
        profile=self.root/"universal-remote-preview.yaml"
        def fake_init(args,**kwargs):
            self.assertNotIn(FAKE_KEY," ".join(args))
            self.assertIs(kwargs["stdin"],subprocess.DEVNULL)
            self.assertIs(kwargs["stdout"],subprocess.DEVNULL)
            profile.write_text("tunnel_id: "+FAKE_ID+"\\n"+
                 "api_key: env:CONTROL_PLANE_API_KEY\\n"+
                 "command: "+str(agent)+"\\n",encoding="utf-8")
            return subprocess.CompletedProcess(args,0)
        with (patch.object(tm,"profile_path",return_value=profile),
              patch.object(tm,"verify_tunnel_client"),
              patch.object(tm.subprocess,"run",side_effect=fake_init)):
            created=tm.provision_profile(FAKE_ID,FAKE_KEY,self.root/"state",agent,client)
        self.assertEqual(created,profile)
        self.assertTrue((self.root/"state"/"tunnel-profile.json").is_file())
        self.assertNotIn(FAKE_KEY,(self.root/"state"/"tunnel-profile.json").read_text())
        self.assertNotIn(FAKE_KEY,profile.read_text())
        self.assertEqual(load_private_key(self.root/"state"),FAKE_KEY)

if __name__=="__main__":
    unittest.main()
