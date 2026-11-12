"""Regression for autonomous recovery and failed first-run profile cleanup."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import tunnel_manager as tm

@unittest.skipUnless(os.name == "nt", "Windows tunnel process supervision")
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ur-self-heal-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.client = self.root/"tunnel-client.exe"
        self.agent = self.root/"UniversalRemoteAgent-Preview.exe"
        self.profile = self.root/"universal-remote-preview.yaml"

    def test_after_multiple_failures_remains_armed_and_can_be_stopped(self):
        attempts = []
        attention = []
        def refused(*a, **kw):
            attempts.append(1)
            raise OSError("simulated transport unavailable")
        def observe_sleep(seconds):
            result = tm.read_status(self.root)
            if result["code"] == "ATTENTION":
                attention.append((result["retry_in"], result["chatgpt_confirmed"]))
                tm.request_stop(self.root)
        with (patch.object(tm, "_validate_provisioned", return_value=self.profile),
              patch.object(tm, "load_private_key", return_value="sk-fake-test"),
              patch.object(tm.subprocess, "Popen", side_effect=refused),
              patch.object(tm.time, "sleep", side_effect=observe_sleep),
              patch.object(tm, "next_retry_seconds", return_value=1)):
            code = tm.run_supervisor(self.root, self.client, self.agent)
        self.assertEqual(code, 0, "Explicit owner stop should shut down controlled retry")
        self.assertGreaterEqual(len(attempts), tm.MAX_ATTEMPTS)
        self.assertTrue(attention, "After repeated failures, supervisor must enter slow self-healing")
        self.assertGreaterEqual(attention[0][0], 600, "Persistent failures need a safe retry rate")
        self.assertFalse(attention[0][1], "Local recovery cannot certify ChatGPT pairing")

    def test_eventually_recovers_and_reports_only_local_readiness(self):
        attempts = [0]
        observed_ready = []
        child = Mock()
        child.poll.return_value = None
        child.wait.return_value = 0
        def connect(*a, **kw):
            attempts[0] += 1
            if attempts[0] <= tm.MAX_ATTEMPTS:
                raise OSError("transient")
            return child
        def fast_sleep(seconds):
            if attempts[0] > tm.MAX_ATTEMPTS:
                observed_ready.append(tm.read_status(self.root))
                tm.request_stop(self.root)
        with (patch.object(tm, "_validate_provisioned", return_value=self.profile),
              patch.object(tm, "load_private_key", return_value="sk-fake-test"),
              patch.object(tm.subprocess, "Popen", side_effect=connect),
              patch.object(tm.time, "sleep", side_effect=fast_sleep),
              patch.object(tm, "next_retry_seconds", return_value=1)):
            code = tm.run_supervisor(self.root, self.client, self.agent)
        self.assertEqual(code, 0)
        self.assertEqual(attempts[0], tm.MAX_ATTEMPTS+1)
        self.assertEqual(observed_ready[0]["code"], "LOCAL_READY")
        self.assertFalse(observed_ready[0]["chatgpt_confirmed"])
        child.terminate.assert_called_once()

    def test_long_cooldown_status_does_not_go_stale(self):
        # Simulated time, not real 15-minute waiting: a silent status file is a UI bug.
        clock = [1700000000]
        attempts = [0]
        observed = []
        def offline(*a, **kw):
            attempts[0] += 1
            raise OSError("network interruption")
        def passage(seconds):
            clock[0] += seconds
            if attempts[0] >= tm.MAX_ATTEMPTS and clock[0] >= 1700000045:
                observed.append(tm.read_status(self.root))
                tm.request_stop(self.root)
        with (patch.object(tm, "_validate_provisioned", return_value=self.profile),
              patch.object(tm, "load_private_key", return_value="sk-fake-test"),
              patch.object(tm.subprocess, "Popen", side_effect=offline),
              patch.object(tm.time, "time", side_effect=lambda: clock[0]),
              patch.object(tm.time, "sleep", side_effect=passage),
              patch.object(tm, "next_retry_seconds", return_value=1)):
            self.assertEqual(tm.run_supervisor(self.root, self.client, self.agent), 0)
        self.assertEqual(observed[0]["code"], "ATTENTION")
        self.assertGreater(observed[0]["retry_in"], 0)

    def test_invalid_new_profile_is_rolled_back_before_retry(self):
        tunnel_id="tunnel_"+("a"*32)
        secret="sk-"+"exampleOnly"*4
        state=self.root/"state"
        self.agent.write_bytes(b"qa agent stub")
        self.client.write_bytes(b"qa client stub")
        def bad_init(args, **kwargs):
            self.profile.write_text("invalid profile", encoding="utf-8")
            return subprocess.CompletedProcess(args, 0)
        with (patch.object(tm, "profile_path", return_value=self.profile),
              patch.object(tm, "verify_tunnel_client", return_value=None),
              patch.object(tm.subprocess, "run", side_effect=bad_init)):
            with self.assertRaises(tm.TunnelConfigError):
                tm.provision_profile(tunnel_id, secret, state, self.agent, self.client)
        self.assertFalse(self.profile.exists(), "Only newly-created bad profile should be removed")
        self.assertFalse((state/"tunnel-key.dpapi").exists())
        self.assertFalse((state/"tunnel-profile.json").exists())

if __name__=="__main__":
    unittest.main()
