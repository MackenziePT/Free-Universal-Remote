"""RC5.1 local revocation tests; no real grants or processes modified."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from universal_remote_ui import emergency_revoke_and_stop


class EmergencyRevocationTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.grant = Path(self.tmp.name) / "grants.json"
        self.grant.write_text('{"capabilities":["shell"],"expires_at":9999999999}')
        self.config = SimpleNamespace(grants_path=self.grant)

    def test_revoke_first_then_stop_running_owned_tasks(self):
        events = []
        alive = {"job1"}
        jobs = Mock()
        def running_jobs():
            events.append("inventory")
            return [{"job_id": item, "status": "running"} for item in sorted(alive)]
        jobs.running_jobs.side_effect = running_jobs
        def stop(job_id):
            events.append("stop")
            self.assertFalse(self.grant.exists())
            alive.remove(job_id)
            return {"status": "stopped"}
        jobs.stop.side_effect = stop
        result = emergency_revoke_and_stop(self.config, jobs)
        self.assertEqual(result["stopped"], ["job1"])
        self.assertEqual(result["remaining"], [])
        self.assertEqual(result["errors"], [])
        jobs.stop.assert_called_once_with("job1")
        self.assertEqual(events[:2], ["inventory", "stop"])

    def test_stop_failure_keeps_grant_revoked_and_reports_failure(self):
        jobs = Mock()
        jobs.running_jobs.return_value = [{"job_id": "one", "status": "running"}]
        jobs.stop.side_effect = RuntimeError("simulated")
        report = emergency_revoke_and_stop(self.config, jobs)
        self.assertFalse(self.grant.exists())
        self.assertEqual(report["remaining"], ["one"])
        self.assertEqual(report["errors"], ["one: RuntimeError"])

    def test_running_inventory_failure_does_not_claim_success(self):
        jobs = Mock()
        jobs.running_jobs.side_effect = OSError("simulated")
        report = emergency_revoke_and_stop(self.config, jobs)
        self.assertFalse(self.grant.exists())
        self.assertIn("Cannot verify", report["errors"][0])

    def test_no_grant_no_jobs_is_safe(self):
        self.grant.unlink()
        jobs = Mock()
        jobs.running_jobs.return_value = []
        report = emergency_revoke_and_stop(self.config, jobs)
        self.assertEqual(report, {"revoked": True, "stopped": [],
                                  "remaining": [], "errors": []})
