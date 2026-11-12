"""Journal behavior across actual process death and competing server processes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from remote_core import load_config, operation_status

ROOT = Path(__file__).resolve().parents[1]


class JournalProcessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.root = base/'data'
        self.root.mkdir()
        self.config = base/'config.json'
        self.config.write_text(json.dumps({'allowed_roots':[str(self.root)],
            'backup_root':str(base/'backups'),'grants_path':str(base/'grants.json')}))
        self.operation = str(uuid.uuid4())

    def command(self, crash=False):
        code = '''import os,sys,time
from pathlib import Path
from remote_core import load_config, execute_once, PolicyError
cfg = load_config(sys.argv[1])
def action():
    Path(sys.argv[3]).write_text('executed')
    if sys.argv[4] == 'crash': os._exit(17)
    time.sleep(0.05)
try:
    execute_once(cfg, sys.argv[2], 'test', 'same-operation', action)
except PolicyError:
    sys.exit(23)
'''
        return [sys.executable,'-c',code,str(self.config),self.operation,
                str(self.root/'effect.txt'),'crash' if crash else 'normal']

    def test_process_death_retains_uncertain_claim_and_refuses_retry(self):
        first = subprocess.run(self.command(crash=True), cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(first.returncode,17)
        self.assertEqual(operation_status(load_config(self.config),self.operation)['state'],'uncertain')
        repeated = subprocess.run(self.command(), cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(repeated.returncode,23)
        self.assertEqual((self.root/'effect.txt').read_text(),'executed')
        self.assertEqual(operation_status(load_config(self.config),self.operation)['state'],'uncertain')

    def test_six_processes_cannot_execute_the_same_id_twice(self):
        processes = [subprocess.Popen(self.command(),cwd=ROOT,stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE) for _ in range(6)]
        try:
            codes = []
            for process in processes:
                _, error = process.communicate(timeout=10)
                self.assertIn(process.returncode,(0,23),error.decode())
                codes.append(process.returncode)
        finally:
            for process in processes:
                if process.poll() is None: process.kill()
                process.wait()
        self.assertEqual(codes.count(0),1)
        self.assertEqual(codes.count(23),5)
        self.assertEqual(operation_status(load_config(self.config),self.operation)['state'],'completed')


if __name__ == '__main__':
    unittest.main()
