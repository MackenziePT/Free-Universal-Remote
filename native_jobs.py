"""First-party durable task sessions, implemented without Desktop Commander.

Tasks are started without a shell, journaled in local SQLite and identified by
UUID plus process creation time to avoid terminating recycled PIDs.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import subprocess
import threading
import time
import uuid

import psutil
from process_runner import clean_child_environment

MAX_LOG_BYTES = 16 * 1024 * 1024
MAX_TASKS_IN_HISTORY = 500


class JobPolicyError(ValueError):
    pass


class TaskManager:
    def __init__(self, state_dir: str | Path, max_running: int = 8):
        self.root = Path(state_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.logs = self.root / "task-logs"
        self.logs.mkdir(exist_ok=True)
        self.database = self.root / "tasks.sqlite3"
        self.max_running = max_running
        self._live: dict[str, subprocess.Popen] = {}
        self._lock = threading.RLock()
        self._watcher_stop = threading.Event()
        self._watchers: dict[str, threading.Thread] = {}
        self._closed = False
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks(
                job_id TEXT PRIMARY KEY, label TEXT NOT NULL,
                executable TEXT NOT NULL, cwd TEXT NOT NULL, pid INTEGER NOT NULL,
                create_time REAL NOT NULL, created_at REAL NOT NULL,
                state TEXT NOT NULL, exit_code INTEGER, log_path TEXT NOT NULL)""")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.database, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout = 10000")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _validate_args(executable, arguments, cwd, label):
        if not isinstance(executable, str) or not os.path.isabs(executable):
            raise JobPolicyError("Executable must be an absolute path")
        if not os.path.isfile(executable):
            raise FileNotFoundError(executable)
        if not isinstance(arguments, list) or len(arguments) > 48:
            raise JobPolicyError("Arguments must be a list of at most 48 strings")
        if any(not isinstance(x, str) or "\x00" in x or len(x) > 4096 for x in arguments):
            raise JobPolicyError("Arguments must be bounded strings without NUL bytes")
        if sum(len(x) for x in arguments) > 32768:
            raise JobPolicyError("Combined arguments are too long")
        if not isinstance(cwd, str) or not os.path.isabs(cwd) or not os.path.isdir(cwd):
            raise JobPolicyError("Working directory must exist and be absolute")
        if not isinstance(label, str) or not 1 <= len(label) <= 80 or "\n" in label:
            raise JobPolicyError("Label must contain 1-80 printable characters")

    def _row(self, job_id: str):
        try:
            uuid.UUID(job_id)
        except (TypeError, ValueError, AttributeError):
            raise KeyError(job_id) from None
        with self._db() as db:
            row = db.execute("SELECT * FROM tasks WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return dict(row)

    @staticmethod
    def _same_process(row) -> bool:
        try:
            proc = psutil.Process(row["pid"])
            return abs(proc.create_time() - row["create_time"]) < 1.5 and proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            return False

    def _update(self, job_id, state, exit_code=None):
        with self._db() as db:
            db.execute("""UPDATE tasks SET state=?, exit_code=?
                           WHERE job_id=? AND state='running'""",
                       (state, exit_code, job_id))

    def _refresh(self, row):
        if row["state"] != "running":
            # An external TaskManager may have stopped this process. Reap the
            # original Popen handle to release Windows resources and suppress
            # warnings without rewriting the persisted terminal state.
            previous = self._live.get(row["job_id"])
            if previous is not None and previous.poll() is not None:
                self._live.pop(row["job_id"], None)
            return row
        process = self._live.get(row["job_id"])
        if process is not None:
            code = process.poll()
            if code is not None:
                self._update(row["job_id"], "exited", code)
                row["state"], row["exit_code"] = "exited", code
                self._live.pop(row["job_id"], None)
                return row
        if not self._same_process(row):
            # The process may have just exited between poll() and PID validation.
            # Popen still carries the actual exit code; prefer it to "unobserved".
            if process is not None:
                code = process.poll()
                if code is not None:
                    self._update(row["job_id"], "exited", code)
                    row["state"], row["exit_code"] = "exited", code
                    self._live.pop(row["job_id"], None)
                    return row
            # A watcher may have committed a precise exit state concurrently.
            current = self._row(row["job_id"])
            if current["state"] != "running":
                return current
            self._update(row["job_id"], "exited_unobserved")
            row["state"] = "exited_unobserved"
        return row

    def _watch(self, job_id, process, log):
        # Monitor output size while the agent is alive; do not silently truncate output.
        try:
            while process.poll() is None:
                try:
                    if log.exists() and log.stat().st_size > MAX_LOG_BYTES:
                        self._terminate_tree(process.pid, psutil.Process(process.pid).create_time())
                        self._update(job_id, "output_limit")
                        break
                except (psutil.NoSuchProcess, OSError):
                    pass
                if self._watcher_stop.wait(0.3):
                    return
            if self._watcher_stop.is_set():
                return
            code = process.wait()
            with self._lock:
                self._update(job_id, "exited", code)
        except Exception:
            # A later status call will use PID and process-creation validation.
            pass
        finally:
            with self._lock:
                self._watchers.pop(job_id, None)

    @staticmethod
    def _terminate_tree(pid, create_time):
        proc = psutil.Process(pid)
        if abs(proc.create_time() - create_time) >= 1.5:
            raise JobPolicyError("PID identity changed, termination refused")
        children = proc.children(recursive=True)
        for child in reversed(children):
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
        _, alive = psutil.wait_procs(children + [proc], timeout=2)
        for child in alive:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def start(self, executable: str, arguments: list[str], cwd: str, label: str = "Remote task") -> dict:
        self._validate_args(executable, arguments, cwd, label)
        job_id = str(uuid.uuid4())
        log = self.logs / (job_id + ".log")
        with self._lock:
            if self._closed:
                raise JobPolicyError("TaskManager is closed")
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                running = db.execute("SELECT * FROM tasks WHERE state='running'").fetchall()
                count = sum(1 for row in running if self._same_process(row))
                if count >= self.max_running:
                    raise JobPolicyError("Maximum concurrent tasks reached")
                # stdout redirected directly to a file: the job can outlive an MCP subprocess.
                with log.open("xb") as handle:
                    flags = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) |
                             getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    environment = clean_child_environment()
                    environment.setdefault("PYTHONIOENCODING", "utf-8")
                    proc = subprocess.Popen([executable, *arguments],
                                            cwd=cwd, stdin=subprocess.DEVNULL,
                                            stdout=handle, stderr=subprocess.STDOUT,
                                            shell=False, creationflags=flags, env=environment)
                try:
                    creation = psutil.Process(proc.pid).create_time()
                    db.execute("""INSERT INTO tasks(job_id,label,executable,cwd,pid,create_time,
                                  created_at,state,exit_code,log_path) VALUES (?,?,?,?,?,?,?,'running',NULL,?)""",
                               (job_id, label, os.path.basename(executable), cwd, proc.pid,
                                creation, time.time(), str(log)))
                except Exception:
                    self._terminate_tree(proc.pid, psutil.Process(proc.pid).create_time())
                    log.unlink(missing_ok=True)
                    raise
            self._live[job_id] = proc
            watcher = threading.Thread(target=self._watch, args=(job_id, proc, log),
                                       name="urm-job-" + job_id[:8], daemon=True)
            self._watchers[job_id] = watcher
            watcher.start()
        return self.status(job_id)

    def close(self) -> None:
        """Release monitor/SQLite activity without terminating persistent jobs.

        A fresh TaskManager may reconnect to these processes after MCP restarts.
        """
        with self._lock:
            self._closed = True
            self._watcher_stop.set()
            workers = list(self._watchers.values())
        for worker in workers:
            if worker is not threading.current_thread():
                worker.join(timeout=12)

    def status(self, job_id: str) -> dict:
        with self._lock:
            row = self._refresh(self._row(job_id))
        return {key: row[key] for key in ("job_id", "label", "executable",
                                          "cwd", "pid", "created_at", "state", "exit_code")} | {"status": row["state"]}

    def list_jobs(self, limit=50) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise JobPolicyError("List limit must be 1-100")
        with self._db() as db:
            rows = db.execute("SELECT job_id FROM tasks ORDER BY created_at DESC LIMIT ?",
                              (limit,)).fetchall()
        return [self.status(row["job_id"]) for row in rows]

    def running_jobs(self) -> list[dict]:
        """Inventory ALL registered running jobs, including older history entries.

        Do not reuse list_jobs(limit=100): the most recent hundred jobs can all
        have finished while an older long-running job remains active.
        """
        with self._db() as db:
            rows = db.execute(
                "SELECT job_id FROM tasks WHERE state='running' ORDER BY created_at ASC"
            ).fetchall()
        results = [self.status(row["job_id"]) for row in rows]
        return [row for row in results if row["status"] == "running"]

    def output(self, job_id: str, offset=0, limit=16384) -> dict:
        if type(offset) is not int or not 0 <= offset < (1 << 63):
            raise JobPolicyError("Output offset must be nonnegative")
        if type(limit) is not int or not 1 <= limit <= 65536:
            raise JobPolicyError("Output limit must be between 1 and 65536")
        row = self._row(job_id)
        # File name is derived from validated UUID, not arbitrary user input.
        with Path(row["log_path"]).open("rb") as source:
            source.seek(offset)
            data = source.read(limit + 1)
        chunk = data[:limit]
        return {"job_id": job_id, "offset": offset, "next_offset": offset + len(chunk),
                "truncated": len(data) > limit,
                "text": chunk.decode("utf-8", errors="replace")}

    def stop(self, job_id: str) -> dict:
        with self._lock:
            row = self._refresh(self._row(job_id))
            if row["state"] != "running":
                return self.status(job_id)
            if not self._same_process(row):
                self._update(job_id, "exited_unobserved")
                return self.status(job_id)
            self._terminate_tree(row["pid"], row["create_time"])
            own = self._live.get(job_id)
            if own is not None:
                try:
                    own.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
            self._update(job_id, "stopped")
        return self.status(job_id)
