"""Regression: emergency stop must see active tasks hidden by 100 newer historical rows."""
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from native_jobs import TaskManager


class ActiveInventoryTests(unittest.TestCase):
    def test_active_job_older_than_100_completed_jobs_is_visible(self):
        with tempfile.TemporaryDirectory(prefix="urm-active-inventory-") as directory:
            manager = TaskManager(Path(directory) / "jobs")
            older_id = str(uuid.uuid4())
            with manager._db() as db:
                db.execute(
                    "INSERT INTO tasks(job_id,label,executable,cwd,pid,create_time,created_at,state,exit_code,log_path) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (older_id, "active old", "python", directory, 123456, 2.0, 1.0, "running", None, "test.log"))
                for i in range(125):
                    db.execute(
                        "INSERT INTO tasks(job_id,label,executable,cwd,pid,create_time,created_at,state,exit_code,log_path) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), "finished", "python", directory,
                         123456, 2.0, 2.0 + i, "exited", 0, "test.log"))
            self.assertNotIn(older_id, {x["job_id"] for x in manager.list_jobs(limit=100)})
            with patch.object(TaskManager, "_same_process", return_value=True):
                active = manager.running_jobs()
            self.assertEqual([x["job_id"] for x in active], [older_id])
            manager.close()


if __name__ == "__main__":
    unittest.main()
