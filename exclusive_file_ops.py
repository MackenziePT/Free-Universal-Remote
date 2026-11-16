"""Atomic no-replace file operations without NTFS hardlinks on Windows.

Windows os.rename refuses to replace an existing destination, whereas POSIX
os.rename may replace one. All callers must validate path and source identity.
"""
from __future__ import annotations
import os
from pathlib import Path

def publish_no_replace(source: str | Path, destination: str | Path) -> None:
    src, dst = Path(source), Path(destination)
    if os.name == "nt":
        try:
            os.rename(src, dst)
        except OSError as exc:
            if os.path.lexists(dst):
                raise FileExistsError("Exclusive destination already exists: " + str(dst)) from exc
            raise
    else:
        os.link(src, dst)

def move_no_replace(source: str | Path, destination: str | Path) -> None:
    src, dst = Path(source), Path(destination)
    if os.name == "nt":
        publish_no_replace(src, dst)
        return
    os.link(src, dst)
    try:
        src.unlink()
    except BaseException:
        try:
            a, b = src.stat(), dst.stat()
            if (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino):
                dst.unlink()
        except OSError:
            pass
        raise
