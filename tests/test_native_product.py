"""Native Universal Remote product regression tests: disposable files and jobs only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from remote_core import Config, PolicyError


class NativeFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="urm-product-files-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.allowed = self.root / "work"
        self.allowed.mkdir()
        self.grant = self.root / "grants.json"
        self.cfg = Config(
            allowed_roots=(self.allowed.resolve(),),
            enable_writes=True,
            grants_path=self.grant,
            backup_root=self.root / "backups",
        )
        self.grant.write_text(json.dumps({
            "expires_at": int(time.time()) + 180,
            "capabilities": ["writes", "shell", "input"]
        }), encoding="utf-8")

    def test_mkdir_and_copy_are_exclusive_and_respect_roots(self):
        from native_files import create_folder, copy_file
        folder = self.allowed / "sub"
        data = self.allowed / "original.txt"
        data.write_text("olá 🌿", encoding="utf-8")
        result = create_folder(self.cfg, str(folder))
        self.assertEqual(Path(result["created"]), folder)
        copied = folder / "copia.txt"
        copy_result = copy_file(self.cfg, str(data), str(copied))
        self.assertEqual(copied.read_text(encoding="utf-8"), "olá 🌿")
        self.assertEqual(copy_result["bytes"], data.stat().st_size)
        with self.assertRaises((FileExistsError, PolicyError)):
            copy_file(self.cfg, str(data), str(copied))
        with self.assertRaises((FileExistsError, PolicyError)):
            create_folder(self.cfg, str(folder))
        with self.assertRaises(PolicyError):
            create_folder(self.cfg, str(self.root / "outside"))

    def test_move_only_within_volume_without_clobber(self):
        from native_files import move_file
        source = self.allowed / "first.txt"
        source.write_text("data", encoding="utf-8")
        target = self.allowed / "second.txt"
        moved = move_file(self.cfg, str(source), str(target))
        self.assertEqual(moved["moved"], str(target))
        self.assertFalse(source.exists())
        self.assertEqual(target.read_text(), "data")
        source.write_text("new")
        with self.assertRaises((FileExistsError, PolicyError)):
            move_file(self.cfg, str(source), str(target))
        self.assertEqual(target.read_text(), "data")

    def test_revocation_blocks_mutations(self):
        from native_files import create_folder
        self.grant.unlink()
        with self.assertRaises(PolicyError):
            create_folder(self.cfg, str(self.allowed / "denied"))
        self.assertFalse((self.allowed / "denied").exists())

    def test_recycle_bin_backend_receives_only_validated_regular_file(self):
        from native_files import recycle_file
        p = self.allowed / "delete-me.txt"
        p.write_text("scratch")
        with patch("native_files.send2trash") as recycle:
            result = recycle_file(self.cfg, str(p))
        recycle.assert_called_once_with(str(p))
        self.assertEqual(result["recycle_requested"], str(p))


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="urm-product-jobs-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        from native_jobs import TaskManager
        self.jobs = TaskManager(self.root / "state", max_running=3)
        self.addCleanup(self.jobs.close)

    def test_background_job_output_status_and_listing(self):
        code = "import time; print('START_OK_🌿',flush=True); time.sleep(0.4); print('END_OK',flush=True)"
        record = self.jobs.start(sys.executable, ["-c", code], str(self.work), label="Unit scratch")
        self.assertIn("job_id", record)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            data = self.jobs.status(record["job_id"])
            if data["status"] in {"exited", "exited_unobserved", "stopped"}:
                break
            time.sleep(0.1)
        self.assertEqual(data["status"], "exited", data)
        self.assertEqual(data["exit_code"], 0)
        output = self.jobs.output(record["job_id"], offset=0, limit=2000)
        self.assertIn("START_OK_🌿", output["text"])
        self.assertIn("END_OK", output["text"])
        self.assertTrue(any(x["job_id"] == record["job_id"] for x in self.jobs.list_jobs()))

    def test_running_job_can_be_stopped_without_touching_other_processes(self):
        code = "import time;time.sleep(40)"
        record = self.jobs.start(sys.executable, ["-c", code], str(self.work), label="Stoppable test")
        result = self.jobs.stop(record["job_id"])
        self.assertIn(result["status"], {"stopped", "exited"})
        self.assertNotEqual(result["status"], "running")

    def test_unknown_job_and_bad_arguments_are_rejected(self):
        from native_jobs import JobPolicyError
        with self.assertRaises(JobPolicyError):
            self.jobs.start(sys.executable, "not a list", str(self.work), label="invalid")
        with self.assertRaises(KeyError):
            self.jobs.status("0" * 32)

    def test_closing_manager_joins_monitors_without_killing_jobs(self):
        from native_jobs import TaskManager
        record = self.jobs.start(sys.executable, ["-c", "import time;time.sleep(5)"],
                                 str(self.work), label="Detached monitor")
        try:
            self.jobs.close()
            reopened = TaskManager(self.root / "state", max_running=3)
            try:
                self.assertIn(reopened.status(record["job_id"])["state"],
                              {"running", "exited", "exited_unobserved"})
                reopened.stop(record["job_id"])
            finally:
                reopened.close()
        finally:
            # Terminate on any assertion failure; never leave an orphan in the suite.
            from native_jobs import TaskManager
            cleanup = TaskManager(self.root / "state", max_running=3)
            try:
                cleanup.stop(record["job_id"])
                # Reap the original Python Popen handle after external stop;
                # prevent ResourceWarning from an intentionally detached job.
                self.jobs.status(record["job_id"])
            finally:
                cleanup.close()

    def test_stopped_task_reaps_original_popen_handle(self):
        from native_jobs import TaskManager
        record = self.jobs.start(sys.executable, ["-c", "import time;time.sleep(20)"],
                                 str(self.work), label="Externally stopped")
        handle = self.jobs._live[record["job_id"]]
        second = TaskManager(self.root / "state", max_running=3)
        try:
            second.stop(record["job_id"])
            self.jobs.status(record["job_id"])
            self.assertIsNotNone(handle.returncode, "Original Popen must be reaped")
        finally:
            second.stop(record["job_id"])
            second.close()
            handle.poll()

    def test_job_state_persists_across_manager_instances(self):
        from native_jobs import TaskManager
        rec = self.jobs.start(sys.executable, ["-c", "print('persist')"], str(self.work), label="Durable")
        copy = TaskManager(self.root / "state", max_running=3)
        self.assertEqual(copy.status(rec["job_id"])["job_id"], rec["job_id"])
        # Clean up a potentially still-running child before deleting its Windows log file.
        self.jobs.stop(rec["job_id"])


class NativeWindowTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Win32 desktop required")
    def test_window_enumeration_bounded_and_invalid_focus_rejected(self):
        from native_windows import window_list, focus_window
        rows = window_list(10)
        self.assertLessEqual(len(rows), 10)
        for item in rows:
            self.assertIn("handle", item)
            self.assertIn("pid", item)
            self.assertLessEqual(len(item["title"]), 256)
        with self.assertRaises(PolicyError):
            focus_window(0, 0)


if __name__ == "__main__":
    unittest.main()
