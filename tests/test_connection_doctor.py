import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connection_doctor import check_local_engine

class ConnectionDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="ur-doc-")
        self.addCleanup(self.tmp.cleanup)
        self.agent=Path(self.tmp.name)/"agent.py"
        self.agent.write_text("# dummy")
        self.py=Path(self.tmp.name)/"python.exe"

    def test_needs_configuration(self):
        with patch("connection_doctor.subprocess.run") as run:
            result=check_local_engine(agent=self.agent,python_exe=self.py,configured=False)
        self.assertEqual(result.code,"SETUP")
        run.assert_not_called()

    def test_missing_agent_no_subprocess(self):
        with patch("connection_doctor.subprocess.run") as run:
            result=check_local_engine(agent=self.agent.with_name("absent"),python_exe=self.py)
        self.assertEqual(result.code,"MISSING")
        run.assert_not_called()

    def test_valid_probes(self):
        with patch("connection_doctor.subprocess.run",side_effect=[
          subprocess.CompletedProcess([],0,b"UNIVERSAL_REMOTE_AGENT_HEALTH_OK",b""),
          subprocess.CompletedProcess([],0,b"{'agent': 'Universal Remote MCP'}",b"")
        ]) as run:
            result=check_local_engine(agent=self.agent,python_exe=self.py)
        self.assertEqual(result.code,"READY")
        self.assertIn("Ainda falta",result.detail)
        self.assertEqual(run.call_count,2)
        for args,kwargs in [c for c in run.call_args_list]:
            self.assertIn("stdin",kwargs)
            self.assertEqual(kwargs["stdin"],subprocess.DEVNULL)
            self.assertNotIn("shell",kwargs)

    def test_failed_health_probe(self):
        with patch("connection_doctor.subprocess.run",
                   return_value=subprocess.CompletedProcess([],1,b"",b"password=fake")) as run:
            result=check_local_engine(agent=self.agent,python_exe=self.py)
        self.assertEqual(result.code,"ERROR")
        self.assertNotIn("password",str(result))
        self.assertEqual(run.call_count,1)

    def test_timeout_and_antivirus_block(self):
        for error,code in [(subprocess.TimeoutExpired("agent",1),"TIMEOUT"),
                           (PermissionError("sensitive path"),"BLOCKED")]:
            with patch("connection_doctor.subprocess.run",side_effect=error):
                result=check_local_engine(agent=self.agent,python_exe=self.py)
            self.assertEqual(result.code,code)
            self.assertNotIn("sensitive path",str(result))

if __name__=="__main__":unittest.main()
