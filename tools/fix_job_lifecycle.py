"""RC5.1: deterministic TaskManager shutdown, monitor joining and race-free exit codes."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/"native_jobs.py"
s=p.read_text(encoding="utf-8")
def rep(a,b):
 global s
 assert a in s, repr(a[:100])
 s=s.replace(a,b)
rep('        self._lock = threading.RLock()\n',
    '        self._lock = threading.RLock()\n        self._watcher_stop = threading.Event()\n        self._watchers: dict[str, threading.Thread] = {}\n        self._closed = False\n')
rep('''        if not self._same_process(row):
            self._update(row["job_id"], "exited_unobserved")
            row["state"] = "exited_unobserved"
        return row''',
    '''        if not self._same_process(row):
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
        return row''')
rep('''                time.sleep(0.3)
            code = process.wait()
            self._update(job_id, "exited", code)
        except Exception:
            # A later status call will use PID and process-creation validation.
            pass''',
    '''                if self._watcher_stop.wait(0.3):
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
                self._watchers.pop(job_id, None)''')
rep('''        with self._lock:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")''',
    '''        with self._lock:
            if self._closed:
                raise JobPolicyError("TaskManager is closed")
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")''')
rep('''            threading.Thread(target=self._watch, args=(job_id, proc, log), daemon=True).start()
        return self.status(job_id)''',
    '''            watcher = threading.Thread(target=self._watch, args=(job_id, proc, log),
                                       name="urm-job-" + job_id[:8], daemon=True)
            self._watchers[job_id] = watcher
            watcher.start()
        return self.status(job_id)''')
needle='    def status(self, job_id: str) -> dict:\n'
assert needle in s
s=s.replace(needle,'''    def close(self) -> None:
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

'''+needle)
p.write_text(s,encoding="utf-8",newline="\n")
t=root/"tests"/"test_native_product.py"
s=t.read_text(encoding="utf-8")
old='        self.jobs = TaskManager(self.root / "state", max_running=3)\n'
assert old in s
s=s.replace(old,old+'        self.addCleanup(self.jobs.close)\n')
t.write_text(s,encoding="utf-8",newline="\n")
print("FIXED_TASK_LIFECYCLE_AND_TEST_TEARDOWN")
