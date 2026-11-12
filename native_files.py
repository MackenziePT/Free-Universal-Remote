"""First-party file operations for Universal Remote, guarded by existing policy.

Only explicitly authorized, non-symlinked approved-root paths are handled.
Operations are exposed through the MCP at-most-once journal in server.py.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile

from remote_core import Config, PolicyError, _approved_read, safe_path

MAX_COPY_BYTES = 128 * 1024 * 1024


def _source(cfg: Config, path: str) -> Path:
    src = safe_path(path, cfg)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    info = src.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise PolicyError("Source must be a regular file without hardlink aliases")
    return src


def _destination(cfg: Config, path: str) -> Path:
    dst = safe_path(path, cfg, writing=True)
    if dst.exists():
        raise FileExistsError(str(dst))
    if not dst.parent.is_dir():
        raise PolicyError("Destination parent directory must already exist")
    return dst


def create_folder(cfg: Config, path: str) -> dict:
    new = _destination(cfg, path)
    new.mkdir(exist_ok=False)
    return {"created": str(new)}


def copy_file(cfg: Config, source: str, destination: str) -> dict:
    src = _source(cfg, source)
    dst = _destination(cfg, destination)
    if src == dst:
        raise PolicyError("Source and destination cannot be the same")
    before = src.stat()
    if before.st_size > MAX_COPY_BYTES:
        raise PolicyError("File exceeds 128 MiB copy limit; use a dedicated transfer")
    fd, tmpname = tempfile.mkstemp(prefix=".urm-copy-", dir=dst.parent)
    temp = Path(tmpname)
    count = 0
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as out, _approved_read(src, cfg) as read:
            while True:
                block = read.read(1024 * 1024)
                if not block:
                    break
                count += len(block)
                if count > MAX_COPY_BYTES:
                    raise PolicyError("File grew beyond copy limit")
                out.write(block)
                digest.update(block)
            out.flush()
            os.fsync(out.fileno())
        after = src.stat()
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or count != before.st_size):
            raise PolicyError("Source changed during copy")
        # Atomic exclusive publish: os.link refuses to overwrite an existing target,
        # including one appearing between pre-validation and publication.
        os.link(temp, dst)
    finally:
        temp.unlink(missing_ok=True)
    return {"copied": str(dst), "bytes": count, "sha256": digest.hexdigest()}


def move_file(cfg: Config, source: str, destination: str) -> dict:
    src = _source(cfg, source)
    dst = _destination(cfg, destination)
    if src == dst:
        raise PolicyError("Cannot move a file onto itself")
    if src.stat().st_dev != dst.parent.stat().st_dev:
        raise PolicyError("Cross-volume moves are not atomic; move refused")
    # Exclusive destination link before unlinking source; even a race cannot
    # silently overwrite a file created by another program.
    os.link(src, dst)
    try:
        src.unlink()
    except Exception:
        dst.unlink(missing_ok=True)
        raise
    return {"moved": str(dst), "from": str(src)}


def send2trash(path: str) -> None:
    """Use the Windows Recycle Bin via a library, not shell commands or deletion."""
    from send2trash import send2trash as recycle
    recycle(path)


def recycle_file(cfg: Config, path: str) -> dict:
    src = _source(cfg, path)
    safe_path(str(src), cfg, writing=True)
    send2trash(str(src))
    return {"recycle_requested": str(src), "note": "Check Windows Recycle Bin to restore"}
