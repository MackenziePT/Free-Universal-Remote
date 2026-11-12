import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import tunnel_manager as tm

@unittest.skipUnless(os.name=="nt","Windows supervisor locking")
class TunnelSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="urm-supervisor-ci-")
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.client=self.folder/"tunnel-client.exe"
        self.agent=self.folder/"UniversalRemoteAgent-Preview.exe"
        self.profile=self.folder/"config.yaml"

    def test_stop_exits_without_exposing_key_or_killing_unowned_process(self):
        child=Mock()
        child.poll.return_value=None
        child.wait.return_value=0
        def create_child(*args,**kwargs):
            self.assertEqual(args[0],[str(self.client),"run","--profile-file",str(self.profile)])
            self.assertEqual(kwargs["env"]["CONTROL_PLANE_API_KEY"],"sk-test-only-ABCDE")
            self.assertEqual(kwargs["stdout"],subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"],subprocess.DEVNULL)
            tm.request_stop(self.folder)
            return child
        with (patch.object(tm,"_validate_provisioned",return_value=self.profile),
              patch.object(tm,"load_private_key",return_value="sk-test-only-ABCDE"),
              patch.object(tm.subprocess,"Popen",side_effect=create_child)):
            result=tm.run_supervisor(self.folder,self.client,self.agent)
        self.assertEqual(result,0)
        child.terminate.assert_called_once()
        self.assertEqual(tm.read_status(self.folder)["code"],"STOPPED")
        self.assertFalse((self.folder/"stop.request").exists())

    def test_persistent_client_crash_slows_and_obeys_owner_stop(self):
        attempts={"number":0}
        codes=[]
        def fails(*args,**kwargs):
            attempts["number"]+=1
            raise OSError("simulated connection failure")
        def acknowledge_stop(_):
            if attempts["number"]>=tm.MAX_ATTEMPTS:
                codes.append(tm.read_status(self.folder)["code"])
                tm.request_stop(self.folder)
        with (patch.object(tm,"_validate_provisioned",return_value=self.profile),
              patch.object(tm,"load_private_key",return_value="sk-test-only-ABCDE"),
              patch.object(tm.subprocess,"Popen",side_effect=fails),
              patch.object(tm.time,"sleep",side_effect=acknowledge_stop),
              patch.object(tm,"next_retry_seconds",return_value=2)):
            result=tm.run_supervisor(self.folder,self.client,self.agent)
        self.assertEqual(result,0)
        self.assertEqual(attempts["number"],tm.MAX_ATTEMPTS)
        self.assertEqual(codes,["ATTENTION"])
        self.assertEqual(tm.read_status(self.folder)["code"],"STOPPED")
