"""Bound retention of signed gateway operations and purge data on revoke."""
import hashlib
import sqlite3
import time

import pytest
from cloud.storage import Denied
from cloud_tests.test_cloud import world


def _owner(world, sub="alice"):
    s=world["settings"]
    return hashlib.sha256((s.issuer+"\0"+sub).encode()).hexdigest()


def test_revoke_clears_completed_sensitive_results_and_arguments(world):
    device,_=world["enroll"]()
    store=world["store"]
    owner=_owner(world)
    job=store.submit(owner,device,"read_text_file",{"path":"D:/sensitive.txt"})
    lease=store.poll(device)
    assert lease["operation_id"]==job
    store.complete(device,job,{"content":"sensitive user data"},True)
    assert store.operation(owner,job)["result"]["content"]=="sensitive user data"
    store.revoke(owner,device)
    status=store.operation(owner,job)
    assert status["status"]=="revoked"
    assert "result" not in status
    with sqlite3.connect(store.db) as conn:
        args,result=conn.execute("SELECT args,result FROM jobs WHERE id=?",(job,)).fetchone()
        assert args == b""
        assert result is None


def test_operation_history_expires_after_one_day_and_is_physically_pruned(world):
    device,_=world["enroll"]()
    store=world["store"]
    owner=_owner(world)
    now=int(time.time())
    timebox=[now]
    store.clock=lambda: timebox[0]
    job=store.submit(owner,device,"windows_diagnostic",{"name":"cpu"})
    lease=store.poll(device)
    store.complete(device,job,{"data":"old result"},True)
    assert store.operation(owner,job)["result"]["data"]=="old result"
    timebox[0]=now + 25*3600
    with pytest.raises(Denied):
        store.operation(owner,job)
    # GC happens during the next write, not on a read-only MCP operation.
    store.submit(owner,device,"windows_diagnostic",{"name":"cpu"})
    with sqlite3.connect(store.db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs WHERE id=?",(job,)).fetchone()[0]==0
