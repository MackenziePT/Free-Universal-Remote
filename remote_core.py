"""Local policy and OS operations for Universal Remote MCP (no MCP dependency)."""
from __future__ import annotations

import json
import base64
import hashlib
import fnmatch
import re
import stat
import os
import platform
import math
import time
import secrets
import shutil
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any
from operation_journal import operation_status, execute_once

BASE = Path(__file__).resolve().parent


class PolicyError(ValueError):
    """A requested operation is outside the explicitly permitted policy."""


@dataclass(frozen=True)
class Config:
    allowed_roots: tuple[Path, ...]
    enable_writes: bool = False
    enable_shell: bool = False
    enable_screen: bool = False
    enable_input: bool = False
    max_read_bytes: int = 65536
    max_write_bytes: int = 1048576
    max_command_seconds: int = 30
    backup_root: Path = BASE / "backups"
    grants_path: Path = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "HarmonyRemoteMCP" / "grants.json"


def validate_windows_path(path: str) -> None:
    """Reject Windows device names, namespace paths and ambiguous filesystem aliases.

    Pure lexical screening; safe_path still enforces the authorized root and
    rejects actual NTFS reparse points before each operation.
    """
    if not isinstance(path, str) or not path or path.startswith(("\\\\", "//")):
        raise PolicyError("UNC and Windows namespace paths are forbidden")
    parsed = PureWindowsPath(path)
    if not re.fullmatch(r"[A-Za-z]:\\", parsed.anchor):
        raise PolicyError("Expected an absolute local Windows drive path")
    for part in parsed.parts[1:]:
        if part in (".", "..") or part.endswith((" ", ".")):
            raise PolicyError("Ambiguous Windows path component")
        if any(ord(c) < 32 or c in '<>:"|?*' for c in part):
            raise PolicyError("Invalid Windows path characters or alternate data stream")
        base = part.split(".", 1)[0].rstrip(" ").upper()
        if (base in {"CON", "PRN", "AUX", "NUL"}
                or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", base)):
            raise PolicyError("Windows reserved device name")


def _bounded_integer(data: dict, name: str, default: int, minimum: int, maximum: int) -> int:
    value = data.get(name, default)
    # Never silently convert booleans, floats or strings into security policy limits.
    if type(value) is not int or not minimum <= value <= maximum:
        raise PolicyError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)()):
        return True
    if os.name == "nt":
        # Python 3.11 lacks Path.is_junction; inspect the Windows reparse flag.
        # This also rejects mount points and other reparse-based aliases.
        try:
            info = path.lstat()
            return bool(getattr(info, "st_file_attributes", 0) &
                        getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        except FileNotFoundError:
            return False
    return False


def _deny_path_aliases(original: Path, roots: tuple[Path, ...]) -> None:
    """Refuse symlink/junction components under approved roots, not just final links.

    This narrows attack surface; it is not a kernel-level race-free open handle.
    """
    lexical = Path(os.path.abspath(original))
    root = next((r for r in roots if lexical.is_relative_to(r)), None)
    if root is None:
        raise PolicyError("Path falls outside permitted roots")
    current = root
    if _is_link_or_junction(current):
        raise PolicyError("Links and junctions in approved roots are forbidden")
    for component in lexical.relative_to(root).parts:
        current = current / component
        if _is_link_or_junction(current):
            raise PolicyError("Links and junctions along paths are forbidden")


def _expand(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def load_config(path: str | Path | None = None) -> Config:
    source = Path(path or os.environ.get("HARMONY_MCP_CONFIG", BASE / "config.json"))
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise PolicyError("Configuration must be a JSON object")
    permitted_keys = {"allowed_roots", "enable_writes", "enable_shell", "enable_screen",
                      "enable_input", "max_read_bytes", "max_write_bytes",
                      "max_command_seconds", "backup_root", "grants_path"}
    unexpected = set(data) - permitted_keys
    if unexpected:
        raise PolicyError(f"Unknown configuration keys: {', '.join(sorted(unexpected))}")
    for flag in ("enable_writes", "enable_shell", "enable_screen", "enable_input"):
        if flag in data and type(data[flag]) is not bool:
            raise PolicyError(f"{flag} must be a JSON boolean")
    supplied = data.get("allowed_roots", [])
    if not isinstance(supplied, list) or not supplied or not all(isinstance(x, str) and x.strip() for x in supplied):
        raise PolicyError("allowed_roots must be a non-empty array of absolute paths")
    expanded = [os.path.expandvars(os.path.expanduser(x)) for x in supplied]
    if any(not Path(x).is_absolute() for x in expanded):
        raise PolicyError("allowed_roots entries must expand into absolute paths")
    roots = tuple(Path(x).resolve() for x in expanded)
    if any(str(root) == root.anchor for root in roots):
        raise PolicyError("Specify narrowly scoped, non-volume-root allowed_roots in config.json")
    timeout = _bounded_integer(data, "max_command_seconds", 30, 1, 120)
    backup_root = _expand(str(data.get("backup_root", str(BASE / "backups"))))
    grants_path = _expand(str(data.get("grants_path", str(Config.grants_path))))
    if any(backup_root.is_relative_to(root) or grants_path.is_relative_to(root) for root in roots):
        raise PolicyError("Backup and local authorization state must be outside all allowed_roots")
    return Config(
        allowed_roots=roots,
        enable_writes=data.get("enable_writes") is True,
        enable_shell=data.get("enable_shell") is True,
        enable_screen=data.get("enable_screen") is True,
        enable_input=data.get("enable_input") is True,
        max_read_bytes=_bounded_integer(data, "max_read_bytes", 65536, 4, 1048576),
        max_write_bytes=_bounded_integer(data, "max_write_bytes", 1048576, 1, 8388608),
        max_command_seconds=timeout,
        backup_root=backup_root,
        grants_path=grants_path,
    )


def grant_allowed(cfg: Config, capability: str) -> bool:
    """A short-lived, LOCAL permission separate from the persistent config flag."""
    if capability not in {"writes", "shell", "screen", "input"}:
        return False
    try:
        if _is_link_or_junction(cfg.grants_path):
            return False
        with cfg.grants_path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                return False
            if info.st_size > 4096 or info.st_size == 0:
                return False
            raw = stream.read(4097)
        payload = json.loads(raw.decode("utf-8-sig"))
        valid_until = payload.get("expires_at")
        caps = payload.get("capabilities")
        now = time.time()
        return (isinstance(valid_until, (int, float)) and not isinstance(valid_until, bool)
                and math.isfinite(valid_until) and now < valid_until <= now + 3600
                and isinstance(caps, list) and capability in caps
                and all(isinstance(item, str) and item in {"writes", "shell", "screen", "input"} for item in caps))
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def require_grant(cfg: Config, capability: str) -> None:
    if not grant_allowed(cfg, capability):
        raise PolicyError(f"{capability} requires a fresh local Grant-Session.ps1 authorization")


def safe_path(path: str, cfg: Config, *, writing: bool = False) -> Path:
    if os.name == "nt":
        validate_windows_path(path)
    if not isinstance(path, str) or not path or not Path(path).is_absolute():
        raise PolicyError("Use a full absolute filesystem path")
    # Do not normalize away an intermediate junction/symlink via '..' before
    # the lexical component-by-component reparse-point inspection.
    if ".." in Path(path).parts:
        raise PolicyError("Parent traversal segments are forbidden")
    if os.name == "nt":
        if path.startswith(("\\\\", "//")) or ":" in path[2:]:
            raise PolicyError("UNC, device paths and alternate data streams are denied")
    original = Path(path)
    _deny_path_aliases(original, cfg.allowed_roots)
    candidate = original.resolve(strict=False)
    if not any(candidate.is_relative_to(root) for root in cfg.allowed_roots):
        raise PolicyError("Path falls outside permitted roots")
    if writing:
        if not cfg.enable_writes:
            raise PolicyError("File writing is disabled in config.json")
        require_grant(cfg, "writes")
        if candidate.is_dir() or not candidate.parent.is_dir():
            raise PolicyError("Parent directory must already exist; target must be a file")
    return candidate


def list_directory(cfg: Config, path: str, limit: int = 100) -> dict[str, Any]:
    p = safe_path(path, cfg)
    if not p.is_dir():
        raise NotADirectoryError(str(p))
    if type(limit) is not int or not 1 <= limit <= 250:
        raise PolicyError("Directory limit must be an integer between 1 and 250")
    max_items = limit
    result = []
    truncated = False
    # Avoid recursively walking symlinks or emitting file content.
    with os.scandir(p) as entries:
        for index, entry in enumerate(entries):
            if index >= max_items:
                truncated = True
                break
            result.append({"name": entry.name, "directory": entry.is_dir(follow_symlinks=False),
                           "symlink": entry.is_symlink()})
    return {"path": str(p), "entries": result, "max_items": max_items,
            "truncated": truncated}



def search_files(cfg: Config, path: str, pattern: str = "*", max_depth: int = 4,
                 max_results: int = 100, max_scanned: int = 5000) -> dict[str, Any]:
    """Bounded name search; never follows symlinks, junctions or reparse points.

    Not a content index or privileged disk crawler. Every starting path must be
    inside an approved root. Enumeration errors are returned, not hidden.
    """
    base = safe_path(path, cfg)
    if not base.is_dir():
        raise NotADirectoryError(str(base))
    if not isinstance(pattern, str) or not 1 <= len(pattern) <= 120 or '/' in pattern or "\\" in pattern:
        raise PolicyError("Pattern must be a filename glob (1-120 characters)")
    for n, value, lo, hi in (("max_depth", max_depth, 0, 8),
                             ("max_results", max_results, 1, 200),
                             ("max_scanned", max_scanned, 1, 10000)):
        if type(value) is not int or not lo <= value <= hi:
            raise PolicyError(f"{n} outside approved bounds")
    queue = [(base, 0)]
    matches = []
    scanned = 0
    errors = 0
    truncated = False
    while queue:
        folder, depth = queue.pop(0)
        # Directory may be replaced between enumeration steps: refuse known aliases.
        _deny_path_aliases(folder, cfg.allowed_roots)
        try:
            with os.scandir(folder) as children:
                for entry in children:
                    if scanned >= max_scanned or len(matches) >= max_results:
                        truncated = True
                        queue.clear()
                        break
                    scanned += 1
                    try:
                        alias = entry.is_symlink() or _is_link_or_junction(Path(entry.path))
                        directory = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        errors += 1
                        continue
                    if alias:
                        continue
                    if fnmatch.fnmatchcase(entry.name.casefold(), pattern.casefold()):
                        matches.append({"name": entry.name, "path": entry.path,
                                        "directory": directory})
                    if directory and depth < max_depth:
                        queue.append((Path(entry.path), depth + 1))
        except (OSError, PermissionError):
            errors += 1
    return {"root": str(base), "matches": matches, "scanned": scanned,
            "errors": errors, "truncated": truncated}


@contextmanager
def _approved_read(path: Path, cfg: Config):
    """Check the opened file identity, including hardlinks, before returning bytes.

    This is defense in depth, not a race-free filesystem sandbox.
    """
    _deny_path_aliases(path, cfg.allowed_roots)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise PolicyError("Read requires a regular file with no hardlink aliases")
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino)):
            raise PolicyError("Read target changed or has aliases")
        _deny_path_aliases(path, cfg.allowed_roots)
        yield stream


def read_binary(cfg: Config, path: str, offset: int = 0, max_bytes: int = 32768) -> dict[str, Any]:
    """Read an explicitly bounded binary chunk as Base64 over text-oriented MCP."""
    if type(offset) is not int or not 0 <= offset < 2**63:
        raise PolicyError("Offset must be a nonnegative signed 64-bit integer")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 65536:
        raise PolicyError("Binary chunk limit must be 1-65536 bytes")
    target = safe_path(path, cfg)
    if not target.is_file():
        raise FileNotFoundError(str(target))
    count = min(max_bytes, cfg.max_read_bytes)
    with _approved_read(target, cfg) as stream:
        stream.seek(offset)
        raw = stream.read(count + 1)
    data = raw[:count]
    return {"path": str(target), "offset": offset, "returned_bytes": len(data),
            "next_offset": offset + len(data), "truncated": len(raw) > count,
            "base64": base64.b64encode(data).decode("ascii")}


def read_text(cfg: Config, path: str, offset: int = 0, max_bytes: int = 16384) -> dict[str, Any]:
    p = safe_path(path, cfg)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    if type(offset) is not int or not 0 <= offset < (1 << 63):
        raise PolicyError("Offset must be a nonnegative signed 64-bit integer")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 1048576:
        raise PolicyError("max_bytes must be a positive integer no larger than 1 MiB")
    requested = min(max_bytes, cfg.max_read_bytes)
    with _approved_read(p, cfg) as stream:
        stream.seek(offset)
        blob = stream.read(requested + 4)
    if b"\x00" in blob:
        raise PolicyError("Binary file blocked; use text-only reads")
    # Bound payload size without returning half of a multibyte code point. The
    # next page should use next_offset, which is guaranteed to be a code-point
    # boundary. Never replace invalid Unicode silently.
    segment = blob[:requested]
    try:
        text = segment.decode("utf-8-sig" if offset == 0 else "utf-8", errors="strict")
        used = len(segment)
    except UnicodeDecodeError as exc:
        if exc.reason != "unexpected end of data" or exc.end != len(segment):
            raise PolicyError("Invalid UTF-8 byte sequence or non-boundary offset") from exc
        used = exc.start
        if not used:
            raise PolicyError("max_bytes too small for next UTF-8 code point") from exc
        text = segment[:used].decode("utf-8-sig" if offset == 0 else "utf-8", errors="strict")
    return {"path": str(p), "offset": offset, "returned_bytes": used,
            "next_offset": offset + used, "truncated": len(blob) > used, "text": text}


def file_info(cfg: Config, path: str) -> dict[str, Any]:
    """Non-destructive fingerprint; only hashes bounded, regular approved files."""
    p = safe_path(path, cfg)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    digest = None
    with _approved_read(p, cfg) as stream:
        info = os.fstat(stream.fileno())
        if info.st_size <= cfg.max_write_bytes:
            data = stream.read(cfg.max_write_bytes + 1)
            if len(data) <= cfg.max_write_bytes:
                digest = hashlib.sha256(data).hexdigest()
    return {"path": str(p), "size": info.st_size, "sha256": digest,
            "hardlinks": info.st_nlink, "modified_ns": info.st_mtime_ns}


def write_text(cfg: Config, path: str, content: str,
               expected_sha256: str | None = None) -> dict[str, Any]:
    """Guarded create/replace, preserving prior content with a verified backup.

    expected_sha256 prevents accidentally overwriting stale content. This is
    best-effort CAS, NOT a filesystem transaction or a TOCTOU-free guarantee.
    """
    p = safe_path(path, cfg, writing=True)
    raw = content.encode("utf-8")
    if len(raw) > cfg.max_write_bytes:
        raise PolicyError("Write exceeds size limit")
    backup: Path | None = None
    prior_digest = None
    prior_stat = None
    if p.exists():
        prior_stat = p.stat()
        if not stat.S_ISREG(prior_stat.st_mode):
            raise PolicyError("Only regular files can be replaced")
        if prior_stat.st_nlink > 1:
            raise PolicyError("Refusing to replace hardlinked files")
        if prior_stat.st_size > cfg.max_write_bytes:
            raise PolicyError("Existing file too large for a bounded backup")
        if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
            raise PolicyError("Existing file requires a valid expected_sha256 from file_info")
        with p.open("rb") as stream:
            prior_digest = hashlib.sha256(stream.read(cfg.max_write_bytes + 1)).hexdigest()
        if prior_digest != expected_sha256.lower():
            raise PolicyError("File changed since it was inspected; no write performed")
        cfg.backup_root.mkdir(parents=True, exist_ok=True)
        backup = cfg.backup_root / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{secrets.token_hex(5)}-{p.name}.bak"
        shutil.copy2(p, backup)
        with backup.open("rb") as stream:
            if hashlib.sha256(stream.read(cfg.max_write_bytes + 1)).hexdigest() != prior_digest:
                backup.unlink(missing_ok=True)
                raise PolicyError("Backup verification failed; write cancelled")
    elif expected_sha256 is not None:
        raise PolicyError("Expected an existing file, but it does not exist")
    fd, tmp = tempfile.mkstemp(prefix=".harmony-", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        if prior_stat is not None:
            # Preserve basic mode/readonly state where supported; Windows file ACLs
            # may still differ, hence this tool is not for security-sensitive files.
            os.chmod(tmp, stat.S_IMODE(prior_stat.st_mode))
            _deny_path_aliases(p, cfg.allowed_roots)
            if not p.is_file():
                raise PolicyError("Target changed during write; cancelled")
            current_stat = p.stat()
            fingerprint = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns,
                                     s.st_ctime_ns, s.st_nlink, stat.S_IMODE(s.st_mode))
            if fingerprint(current_stat) != fingerprint(prior_stat):
                raise PolicyError("File identity or metadata changed during write; cancelled")
            with p.open("rb") as stream:
                current = hashlib.sha256(stream.read(cfg.max_write_bytes + 1)).hexdigest()
            if current != prior_digest:
                raise PolicyError("Target changed during write; cancelled")
            os.replace(tmp, p)
        else:
            _deny_path_aliases(p, cfg.allowed_roots)
            # Atomic create-if-absent. os.replace would overwrite a file that
            # appears after the earlier existence check.
            try:
                os.link(tmp, p)
            except FileExistsError as exc:
                raise PolicyError("New target appeared during write; cancelled") from exc
            except (OSError, NotImplementedError) as exc:
                raise PolicyError("Filesystem does not support safe atomic create") from exc
            os.unlink(tmp)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {"written": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "backup": str(backup) if backup else None}


def system_snapshot() -> dict[str, Any]:
    import psutil
    memory = psutil.virtual_memory()
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({"mount": part.mountpoint, "fstype": part.fstype,
                          "total": usage.total, "used": usage.used, "free": usage.free})
        except (OSError, PermissionError):
            continue
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(), "os": platform.platform(),
            "python": platform.python_version(), "cpu_percent": psutil.cpu_percent(interval=0.2),
            "logical_cpus": psutil.cpu_count(),
            "memory": {"total": memory.total, "available": memory.available,
                       "used": memory.used, "percent": memory.percent},
            "disks": disks,
            "network_bytes": {"sent": psutil.net_io_counters().bytes_sent,
                              "received": psutil.net_io_counters().bytes_recv}}


def processes(limit: int = 80) -> list[dict[str, Any]]:
    import psutil
    found = []
    for process in psutil.process_iter(attrs=["pid", "name", "memory_info", "status"]):
        try:
            info = process.info
            found.append({"pid": info["pid"], "name": info["name"],
                          "rss": getattr(info["memory_info"], "rss", 0), "status": info["status"]})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    found.sort(key=lambda p: p["rss"], reverse=True)
    return found[:max(1, min(int(limit), 200))]


DIAGNOSTICS = {
    "computer": "Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory | ConvertTo-Json -Compress",
    "cpu": "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Compress",
    "gpu": "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM | ConvertTo-Json -Compress",
    "network": "Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed | ConvertTo-Json -Compress",
    "memory_manager": "Get-MMAgent | ConvertTo-Json -Compress",
    "volumes": "Get-Volume | Select-Object DriveLetter,FileSystem,Size,SizeRemaining | ConvertTo-Json -Compress",
}


# Kept as a public import for existing callers.
from process_runner import run_limited_process


def powershell_encoded_command(command: str) -> str:
    """Encode a script for WinPS 5.1 and PS7; avoid shell-quoting and OEM decoding.

    PowerShell expects UTF-16LE bytes under -EncodedCommand. The script sets
    UTF-8 console output before running the requested command.
    """
    prelude = ("$ErrorActionPreference = 'Stop'; "
               "$utf8 = [System.Text.UTF8Encoding]::new($false); "
               "[Console]::OutputEncoding = $utf8; $OutputEncoding = $utf8; ")
    return base64.b64encode((prelude + command).encode("utf-16-le")).decode("ascii")


def _windows_executable_version(executable: str | Path) -> tuple[int, int, int] | None:
    """Read Windows FileVersionInfo without spawning a shell or downloading anything."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        version = ctypes.WinDLL("version", use_last_error=True)
        version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        version.GetFileVersionInfoW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        version.GetFileVersionInfoW.restype = wintypes.BOOL
        version.VerQueryValueW.argtypes = [
            ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.UINT)]
        version.VerQueryValueW.restype = wintypes.BOOL
        handle = wintypes.DWORD()
        size = version.GetFileVersionInfoSizeW(str(executable), ctypes.byref(handle))
        if size <= 0:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(executable), 0, size, buffer):
            return None
        block, length = ctypes.c_void_p(), wintypes.UINT()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(block), ctypes.byref(length)):
            return None
        if length.value < 16:
            return None
        fixed = ctypes.cast(block, ctypes.POINTER(wintypes.DWORD))
        if fixed[0] != 0xFEEF04BD:
            return None
        major, minor, patch = fixed[2] >> 16, fixed[2] & 0xFFFF, fixed[3] >> 16
        return int(major), int(minor), int(patch)
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _powershell(command: str, timeout: int) -> dict[str, Any]:
    if os.name != "nt":
        raise OSError("PowerShell diagnostics are Windows-only")

    # The updater validates Microsoft's signature/digest before installing private
    # runtimes. Prefer the highest version, rather than a stale global PATH entry.
    choices: list[tuple[tuple[int, int, int], str]] = []
    global_shell = shutil.which("pwsh.exe")
    if global_shell:
        global_version = _windows_executable_version(global_shell)
        if global_version is not None and global_version[0] >= 7:
            choices.append((global_version, global_shell))
        else:
            # Retain legacy behavior for a user-provided shell with no version
            # metadata, but never rank it above a verified private installation.
            choices.append(((0, 0, 0), global_shell))

    programs = os.environ.get("ProgramFiles", "")
    if programs:
        install_root = Path(programs) / "PowerShell"
        if install_root.is_dir() and not _is_link_or_junction(install_root):
            for folder in install_root.iterdir():
                if (not folder.is_dir() or _is_link_or_junction(folder)
                        or not folder.name.isdecimal() or int(folder.name) < 7):
                    continue
                standard = folder / "pwsh.exe"
                if standard.is_file() and not _is_link_or_junction(standard):
                    found = _windows_executable_version(standard)
                    if found and found[0] >= 7:
                        choices.append((found, str(standard)))

    state = Path(os.environ.get("LOCALAPPDATA", "")) / "UniversalRemote" / "runtime" / "powershell"
    if state.is_dir() and not _is_link_or_junction(state):
        for folder in state.iterdir():
            candidate = folder / "pwsh.exe"
            if not (folder.is_dir() and not _is_link_or_junction(folder)
                    and candidate.is_file() and not _is_link_or_junction(candidate)):
                continue
            try:
                version_parts = tuple(int(x) for x in folder.name.split("-", 1)[0].split("."))
                if len(version_parts) != 3 or version_parts[0] < 7:
                    continue
                file_version = _windows_executable_version(candidate)
                if file_version is not None and file_version != version_parts:
                    continue
                choices.append((version_parts, str(candidate)))
            except (ValueError, OSError):
                continue

    if not choices:
        raise FileNotFoundError(
            "PowerShell moderno indisponível. Abre Conexões para obter a versão estável mais recente.")
    executable = max(choices)[1]
    return run_limited_process(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive",
         "-EncodedCommand", powershell_encoded_command(command)], timeout)


def diagnostic(cfg: Config, name: str) -> dict[str, Any]:
    if name not in DIAGNOSTICS:
        raise PolicyError(f"Choose one of: {', '.join(DIAGNOSTICS)}")
    return _powershell(DIAGNOSTICS[name], cfg.max_command_seconds)


def powershell(cfg: Config, command: str, operation_id: str = "") -> dict[str, Any]:
    if not cfg.enable_shell:
        raise PolicyError("Arbitrary PowerShell is disabled; enabling it grants powerful local access")
    require_grant(cfg, "shell")
    if not command or len(command) > 8192:
        raise PolicyError("PowerShell command must be between 1 and 8192 characters")
    return execute_once(cfg, operation_id, "shell", command,
                        lambda: _powershell(command, cfg.max_command_seconds))
