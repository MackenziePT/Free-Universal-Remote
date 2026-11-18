"""Fail-closed public agent heartbeat and single-instance lifetime control.

Heartbeat proves a recent signed HTTPS polling response, not authorization
to execute commands. The file never contains OAuth credentials or private keys.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import time


class AgentAlreadyRunning(RuntimeError):
    """A live agent already owns the current user-session lock."""


def heartbeat_path(identity_path: Path) -> Path:
    return Path(identity_path).with_name("connection_status.json")


def update_heartbeat(identity_path: Path, device_id: str, *,
                     connected: bool, now: float | None = None) -> None:
    from .device_client import _id
    device_id = _id(device_id)
    stamp = time.time() if now is None else float(now)
    if not 0 < stamp < 99999999999:
        raise ValueError("Invalid heartbeat time")
    record = {"version": 1, "device_id": device_id, "connected": bool(connected),
              "last_contact_utc": stamp if connected else 0}
    target = heartbeat_path(identity_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".connection-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def recent_contact(identity_path: Path, device_id: str, *,
                   now: float | None = None, window: float = 15.0) -> tuple[bool, float | None]:
    stamp = time.time() if now is None else float(now)
    try:
        info = json.loads(heartbeat_path(identity_path).read_text(encoding="utf-8"))
        if (not isinstance(info, dict) or info.get("version") != 1 or
                info.get("device_id") != device_id or
                type(info.get("connected")) is not bool):
            return False, None
        last = info.get("last_contact_utc")
        if not isinstance(last, (int, float)) or isinstance(last, bool):
            return False, None
        fresh = bool(info["connected"]) and 0 <= stamp - last <= window
        return fresh, last if last > 0 else None
    except (OSError, ValueError, TypeError):
        return False, None


@contextmanager
def single_agent_lock(path: Path):
    """Exclusive byte-range lock, automatically released if the process exits."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise AgentAlreadyRunning("Public agent is already active") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise AgentAlreadyRunning("Public agent is already active") from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
