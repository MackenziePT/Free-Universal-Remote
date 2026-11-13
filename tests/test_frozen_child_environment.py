"""Launching applications from a frozen Universal Remote must not leak bootloader state."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from process_runner import run_limited_process
from native_jobs import TaskManager
from tools.accept_public_prototype import env_for_user


_INTERNAL = {
    "_PYI_ARCHIVE_FILE": r"C:\Program Files\OtherFrozenBridge\Bridge.exe",
    "_PYI_APPLICATION_HOME_DIR": r"C:\Program Files\OtherFrozenBridge\_internal",
    "_PYI_PARENT_PROCESS_LEVEL": "1",
    "PYINSTALLER_RESET_ENVIRONMENT": "1",
    "URM_CHILD_SAFE_TEST_MARKER": "preserved",
}
_PROBE = (
    'import json,os; print(json.dumps({'
    '"archive":os.getenv("_PYI_ARCHIVE_FILE"),'
    '"home":os.getenv("_PYI_APPLICATION_HOME_DIR"),'
    '"level":os.getenv("_PYI_PARENT_PROCESS_LEVEL"),'
    '"reset":os.getenv("PYINSTALLER_RESET_ENVIRONMENT"),'
    '"custom":os.getenv("URM_CHILD_SAFE_TEST_MARKER")}))'
)


class FrozenChildEnvironmentTests(unittest.TestCase):
    def assert_clean(self, record):
        self.assertIsNone(record["archive"])
        self.assertIsNone(record["home"])
        self.assertIsNone(record["level"])
        self.assertIsNone(record["reset"])
        self.assertEqual(record["custom"], "preserved")

    def test_bounded_shell_resets_frozen_parent_environment(self):
        with patch.dict(os.environ, _INTERNAL):
            result = run_limited_process([sys.executable, "-c", _PROBE], timeout=12)
        self.assertEqual(result["exit_code"], 0, result)
        self.assert_clean(json.loads(result["stdout"]))

    def test_persistent_job_resets_frozen_parent_environment(self):
        with tempfile.TemporaryDirectory() as scratch:
            manager = TaskManager(Path(scratch) / "state")
            try:
                with patch.dict(os.environ, _INTERNAL):
                    job = manager.start(sys.executable, ["-c", _PROBE], scratch, "Frozen env")
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if manager.status(job["job_id"])["status"] != "running":
                        break
                    time.sleep(0.05)
                self.assertEqual(manager.status(job["job_id"])["exit_code"], 0)
                self.assert_clean(json.loads(manager.output(job["job_id"])["text"]))
            finally:
                manager.close()

    def test_packaged_acceptance_clears_frozen_parent_environment(self):
        with tempfile.TemporaryDirectory() as scratch:
            with patch.dict(os.environ, _INTERNAL):
                env = env_for_user(Path(scratch))
        for var in ("_PYI_ARCHIVE_FILE", "_PYI_APPLICATION_HOME_DIR",
                    "_PYI_PARENT_PROCESS_LEVEL", "PYINSTALLER_RESET_ENVIRONMENT"):
            self.assertFalse(var in env, "Frozen variable leaked: " + var)
        self.assertEqual(env["URM_CHILD_SAFE_TEST_MARKER"], "preserved")


if __name__ == "__main__":
    unittest.main()
