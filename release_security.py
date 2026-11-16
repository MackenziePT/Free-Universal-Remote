"""Cryptographically authenticated, offline-first update transactions.

The pinned publisher public keys MUST come from an existing trusted installation
or explicit, out-of-band owner trust; never accept keys shipped in an untrusted ZIP.
The Ed25519 signature authenticates metadata and every byte of every payload file.
Authenticode for the distributed .exe is a separate (still mandatory) public gate.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
import unicodedata
import zipfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class ReleaseError(ValueError):
    pass


def _unique_json(raw: bytes | str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ReleaseError("Duplicate JSON key")
            result[key] = value
        return result
    try:
        parsed = json.loads(raw, object_pairs_hook=pairs,
                            parse_constant=lambda value: (_ for _ in ()).throw(ReleaseError("Nonfinite JSON")))
    except (json.JSONDecodeError, UnicodeError, TypeError) as exc:
        raise ReleaseError("Malformed JSON") from exc
    if not isinstance(parsed, dict):
        raise ReleaseError("Signed metadata must be an object")
    return parsed


def _canonical(metadata: dict) -> bytes:
    return json.dumps(metadata, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _b64(s: str, length: int) -> bytes:
    try:
        raw = base64.b64decode(s, validate=True)
    except (ValueError, TypeError) as exc:
        raise ReleaseError("Invalid base64 encoding") from exc
    if len(raw) != length:
        raise ReleaseError("Invalid key/signature length")
    return raw


def _safe_name(name: str) -> str:
    if not isinstance(name, str) or not name or "\\" in name or name.startswith("/"):
        raise ReleaseError("Invalid archive path")
    if unicodedata.normalize("NFC", name) != name:
        raise ReleaseError("Non-normalized archive path")
    parts = PurePosixPath(name).parts
    if "/".join(parts) != name:
        raise ReleaseError("Non-canonical archive path")
    if any(p in (".", "..", "") for p in parts) or len(parts) > 16 or len(name) > 240:
        raise ReleaseError("Unsafe archive path")
    if any(":" in p or p[-1] in ". " or
           re.fullmatch(r"(?i)(CON|CONIN\$|CONOUT\$|PRN|AUX|NUL|(?:COM|LPT)[1-9\u00b9\u00b2\u00b3])(?:\..*)?", p)
           for p in parts):
        raise ReleaseError("Windows-reserved archive path")
    if any(ord(char) < 32 or char in '<>"|?*' for char in name):
        raise ReleaseError("Invalid Windows filename")
    return name


def verify_signed_release(metadata_bytes: bytes, signature_b64: str,
                          trusted_keys: dict[str, str], *, minimum_sequence: int,
                          now: int | None = None) -> dict:
    if len(metadata_bytes) > 2_000_000:
        raise ReleaseError("Metadata too large")
    m = _unique_json(metadata_bytes)
    if m.get("format") != 1 or m.get("product") != "universal-remote":
        raise ReleaseError("Unexpected product or metadata format")
    key_id = m.get("key_id")
    if not isinstance(key_id, str) or key_id not in trusted_keys:
        raise ReleaseError("Release signing key not pinned")
    sequence = m.get("sequence")
    if type(sequence) is not int or sequence < 1 or sequence <= minimum_sequence:
        raise ReleaseError("Replay or downgrade forbidden")
    timestamp = int(time.time()) if now is None else int(now)
    if (type(m.get("issued_at")) is not int or type(m.get("expires_at")) is not int
        or m["issued_at"] > timestamp + 300 or m["expires_at"] < timestamp
        or m["expires_at"] <= m["issued_at"] or m["expires_at"] - m["issued_at"] > 32 * 86400):
        raise ReleaseError("Expired, future-dated or overlong release metadata")
    if (not isinstance(m.get("version"), str) or
            not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._+-]{0,63}", m["version"])):
        raise ReleaseError("Invalid release version label")
    if not isinstance(m.get("platform"), str) or m["platform"] not in {"windows-x64", "windows-arm64"}:
        raise ReleaseError("Unsupported platform label")
    if (not isinstance(m.get("archive_sha256"), str) or
            not re.fullmatch("[a-f0-9]{64}", m["archive_sha256"])):
        raise ReleaseError("Invalid archive digest")
    if type(m.get("archive_bytes")) is not int or not 1 <= m["archive_bytes"] <= 1_000_000_000:
        raise ReleaseError("Archive size outside bound")
    files = m.get("files")
    if not isinstance(files, dict) or not 1 <= len(files) <= 12000:
        raise ReleaseError("Invalid signed file inventory")
    folded = set()
    for name, attrs in files.items():
        _safe_name(name)
        key = name.casefold()
        if key in folded:
            raise ReleaseError("Case-insensitive path collision")
        folded.add(key)
        if (not isinstance(attrs, dict) or set(attrs) != {"sha256", "bytes"} or
            not isinstance(attrs["sha256"], str) or
            not re.fullmatch("[a-f0-9]{64}", attrs["sha256"]) or
            type(attrs["bytes"]) is not int or not 0 <= attrs["bytes"] <= 500_000_000):
            raise ReleaseError("Invalid file inventory entry")
    if set(m) != {"format", "product", "key_id", "sequence", "issued_at",
                  "expires_at", "version", "platform", "archive_sha256",
                  "archive_bytes", "files"}:
        raise ReleaseError("Unexpected metadata fields")
    try:
        Ed25519PublicKey.from_public_bytes(_b64(trusted_keys[key_id], 32)).verify(
            _b64(signature_b64, 64), _canonical(m))
    except (InvalidSignature, ValueError) as exc:
        raise ReleaseError("Invalid publisher signature") from exc
    return m


def verify_payload(archive: Path, metadata: dict) -> None:
    archive = Path(archive)
    if archive.stat().st_size != metadata["archive_bytes"]:
        raise ReleaseError("Archive size mismatch")
    with archive.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != metadata["archive_sha256"]:
            raise ReleaseError("Archive digest mismatch")
    with zipfile.ZipFile(archive, "r") as z:
        files = metadata["files"]
        actual = {}
        aliases = set()
        total = 0
        for entry in z.infolist():
            if entry.is_dir() or entry.flag_bits & 0x1:
                raise ReleaseError("Directory/encrypted ZIP entries not allowed")
            name = _safe_name(entry.filename)
            if name.casefold() in aliases or name not in files:
                raise ReleaseError("Unexpected/duplicate ZIP entry")
            aliases.add(name.casefold())
            if (entry.create_system == 3 and
                stat.S_IFMT((entry.external_attr >> 16) & 0xFFFF) not in (0, stat.S_IFREG)):
                raise ReleaseError("Archive symlink/special file refused")
            total += entry.file_size
            if (entry.file_size != files[name]["bytes"] or total > 2_000_000_000 or
                entry.compress_size == 0 and entry.file_size > 0 or
                entry.file_size > 4096 * max(1, entry.compress_size)):
                raise ReleaseError("ZIP size/compression bound exceeded")
            digest = hashlib.sha256()
            with z.open(entry) as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != files[name]["sha256"]:
                raise ReleaseError("Signed payload file mismatch")
            actual[name] = True
        if set(actual) != set(files):
            raise ReleaseError("Missing release files")


def _write_atomic(path: Path, value: dict) -> None:
    temp = path.with_name(path.name + ".partial")
    with temp.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def _read_state(path: Path) -> dict:
    if not path.exists():
        return {"sequence": 0}
    state = _unique_json(path.read_bytes())
    if type(state.get("sequence")) is not int or state["sequence"] < 0:
        raise ReleaseError("Invalid installed release state")
    return state


def recover_update(target: Path, state_dir: Path) -> bool:
    """Recover interrupted switch; never trust arbitrary paths from a journal."""
    target = Path(target).absolute()
    state_dir = Path(state_dir).absolute()
    journal = state_dir / "update.pending.json"
    if not journal.is_file():
        return False
    entry = _unique_json(journal.read_bytes())
    transaction = entry.get("transaction")
    if not isinstance(transaction, str) or not re.fullmatch("[a-f0-9]{32}", transaction):
        raise ReleaseError("Corrupt update journal")
    stage = target.parent / (".ur-stage-" + transaction)
    backup = target.parent / (".ur-backup-" + transaction)
    # State written after a successful health check proves commit; a crash
    # between state fsync and journal cleanup must NOT revert a healthy app.
    committed = (_read_state(state_dir / "update-state.json").get("sequence")
                 == entry.get("sequence"))
    had_previous = entry.get("had_previous")
    if had_previous is not None and type(had_previous) is not bool:
        raise ReleaseError("Invalid pending journal state")
    if committed and target.exists():
        if stage.exists():
            shutil.rmtree(stage)
        journal.unlink()
        return True
    if backup.exists():
        if target.exists():
            quarantine = target.parent / (".ur-failed-" + transaction)
            if quarantine.exists():
                raise ReleaseError("Recovery quarantine already occupied")
            target.rename(quarantine)
        backup.rename(target)
    elif target.exists() and had_previous is True:
        # Crash after journal fsync but BEFORE moving the existing app.
        # Keep the old, known-good installation in place.
        pass
    elif target.exists() and had_previous is False:
        # Failed FIRST installation must not remain executable.
        quarantine = target.parent / (".ur-failed-" + transaction)
        if quarantine.exists():
            raise ReleaseError("Recovery quarantine already occupied")
        target.rename(quarantine)
    elif target.exists():
        # Legacy journal without a prior-install flag: fail closed.
        raise ReleaseError("Ambiguous recovery: existing target and no backup")
    elif not stage.exists():
        raise ReleaseError("No recoverable installation found")
    if stage.exists():
        shutil.rmtree(stage)
    journal.unlink()
    return True


def _apply_signed_update_unlocked(*, target: Path, state_dir: Path, archive: Path,
                                  metadata_bytes: bytes, signature_b64: str,
                                  trusted_keys: dict[str, str], platform: str,
                                  health_check) -> dict:
    """Called by a separate updater after the app has exited.

    health_check(target) must validate the installed candidate and return True.
    No network calls, no execution of a package before signature validation.
    """
    target = Path(target).absolute()
    state_dir = Path(state_dir).absolute()
    if target.is_symlink() or state_dir.is_symlink() or target.parent.is_symlink():
        raise ReleaseError("Symlink installation paths forbidden")
    state_dir.mkdir(parents=True, exist_ok=True)
    if (state_dir / "update.pending.json").exists():
        raise ReleaseError("Interrupted update present; recover first")
    state_path = state_dir / "update-state.json"
    installed = _read_state(state_path)
    m = verify_signed_release(metadata_bytes, signature_b64, trusted_keys,
                              minimum_sequence=installed["sequence"])
    if m["platform"] != platform:
        raise ReleaseError("Release targets a different architecture")
    verify_payload(Path(archive), m)
    import uuid
    transaction = uuid.uuid4().hex
    stage = target.parent / (".ur-stage-" + transaction)
    backup = target.parent / (".ur-backup-" + transaction)
    journal = state_dir / "update.pending.json"
    stage.mkdir(mode=0o700)
    moved = False
    try:
        with zipfile.ZipFile(archive, "r") as z:
            for entry in z.infolist():
                dest = stage.joinpath(*PurePosixPath(entry.filename).parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(entry) as source, dest.open("xb") as sink:
                    shutil.copyfileobj(source, sink, 1024 * 1024)
        had_previous = target.exists()
        _write_atomic(journal, {"transaction": transaction, "sequence": m["sequence"],
                                "had_previous": had_previous})
        if had_previous:
            target.rename(backup)
            moved = True
        stage.rename(target)
        if health_check(target) is not True:
            raise ReleaseError("Installed candidate failed post-switch health check")
        _write_atomic(state_path, {"sequence": m["sequence"], "version": m["version"],
                                   "key_id": m["key_id"]})
        journal.unlink()
        return {"ok": True, "version": m["version"], "sequence": m["sequence"],
                "backup": str(backup) if moved else None}
    except BaseException:
        if journal.exists():
            recover_update(target, state_dir)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)

class UpdateLock:
    """OS-level nonblocking exclusive lock for concurrent updater processes."""
    def __init__(self, state_dir: Path):
        self.path = Path(state_dir) / "update.lock"
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.handle = self.path.open("a+b")
            self.handle.seek(0)
            if self.handle.read(1) != b"0":
                self.handle.seek(0)
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise ReleaseError("Another updater is already active") from exc
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.handle:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


def apply_signed_update(*, target: Path, state_dir: Path, archive: Path,
                        metadata_bytes: bytes, signature_b64: str,
                        trusted_keys: dict[str, str], platform: str,
                        health_check) -> dict:
    # State must survive a binary rollback; never store it underneath target.
    target = Path(target).absolute()
    state_dir = Path(state_dir).absolute()
    if state_dir == target or state_dir.is_relative_to(target) or target.is_relative_to(state_dir):
        raise ReleaseError("Application binaries and persistent state must be separate")
    with UpdateLock(state_dir):
        return _apply_signed_update_unlocked(
            target=target, state_dir=state_dir, archive=archive,
            metadata_bytes=metadata_bytes, signature_b64=signature_b64,
            trusted_keys=trusted_keys, platform=platform, health_check=health_check)
