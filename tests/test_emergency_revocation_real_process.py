"""Windows integration: owner emergency stop must terminate a disposable child job."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

from native_jobs import TaskManager
from universal_remote_ui import emergency_revoke_and_stop


@unittest.skipUnless(os.name == "nt", "Windows process-tree integration")
class EmergencyRealProcessTests(unittest.TestCase):
    def test_local_emergency_revokes_and_terminates_owned_job(self):
        with tempfile.TemporaryDirectory(prefix="urm-emergency-e2e-") as root:
            root = Path(root)
            grant = root / "grants.json"
            grant.write_text('{"capabilities":["shell"],"expires_at":9999999999}',
                             encoding="utf-8")
            manager = TaskManager(root / "jobs")
            job = None
            try:
                job = manager.start(sys.executable,
                                    ["-c", "import time; time.sleep(25)"],
                                    str(root), "disposable emergency test")
                self.assertEqual(job["status"], "running")
                report = emergency_revoke_and_stop(
                    SimpleNamespace(grants_path=grant), manager)
                self.assertFalse(grant.exists())
                self.assertIn(job["job_id"], report["stopped"])
                self.assertEqual(report["remaining"], [])
                self.assertEqual(report["errors"], [])
                self.assertNotEqual(manager.status(job["job_id"])["status"], "running")
            finally:
                if job is not None:
                    try:
                        manager.stop(job["job_id"])
                    except (OSError, ValueError, KeyError):
                        pass
                manager.close()


if __name__ == "__main__":
    unittest.main()
