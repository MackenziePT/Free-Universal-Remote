"""Bounded command output and a deadline covering inherited pipes as well as the parent.

No reader thread is allowed to block return. Windows uses PeekNamedPipe; POSIX
uses select. Tree termination is best effort, not an OS sandbox or a Job Object.
"""
from __future__ import annotations

import math
import os
import select
import signal
import subprocess
import time


def clean_child_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Isolate unrelated subprocesses from inherited PyInstaller bootloader state.

    Preserve normal user variables and PATH; discard only PyInstaller's
    process-internal bootstrap keys, which are invalid for another executable.
    """
    environment = dict(os.environ if source is None else source)
    for name in tuple(environment):
        if name.upper().startswith("_PYI_") or name.upper() in {
                "PYINSTALLER_RESET_ENVIRONMENT",
                "PYINSTALLER_SUPPRESS_SPLASH_SCREEN"}:
            environment.pop(name, None)
    return environment


def _pipe_reader():
    if os.name != 'nt':
        def read(stream):
            if not select.select([stream], [], [], 0)[0]:
                return None
            return os.read(stream.fileno(), 65536)
        return read

    import ctypes
    import msvcrt
    from ctypes import wintypes
    peek = ctypes.WinDLL('kernel32', use_last_error=True).PeekNamedPipe
    peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                     ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                     ctypes.POINTER(wintypes.DWORD)]
    peek.restype = wintypes.BOOL

    def read(stream):
        available = wintypes.DWORD()
        if not peek(msvcrt.get_osfhandle(stream.fileno()), None, 0, None,
                    ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error in (109, 232):  # ERROR_BROKEN_PIPE / ERROR_NO_DATA
                return b''
            raise ctypes.WinError(error)
        if not available.value:
            return None
        return os.read(stream.fileno(), min(available.value, 65536))
    return read


def _terminate(process, flags):
    if os.name == 'nt':
        if process.poll() is None:
            system = os.environ.get('SystemRoot', r'C:\Windows')
            try:
                subprocess.run([os.path.join(system, 'System32', 'taskkill.exe'),
                                '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=2, creationflags=flags, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
    else:
        # The process group can survive its leader when children retain pipes.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=2)


def run_limited_process(command: list[str], timeout: float, stdout_limit: int = 65536,
                        stderr_limit: int = 8192) -> dict:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('A finite positive timeout is required')
    if any(type(n) is not int or n < 0 for n in (stdout_limit, stderr_limit)):
        raise ValueError('Output limits must be nonnegative integers')
    read_available = _pipe_reader()
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if os.name == 'nt':
        flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, bufsize=0, creationflags=flags,
                               env=clean_child_environment(),
                               start_new_session=os.name != 'nt')
    streams = {'stdout': process.stdout, 'stderr': process.stderr}
    buffers = {name: bytearray() for name in streams}
    limits = {'stdout': stdout_limit, 'stderr': stderr_limit}
    truncated = {name: False for name in streams}
    pending = set(streams)
    deadline = time.monotonic() + timeout
    timed_out = False

    def drain_once():
        activity = False
        for name in tuple(pending):
            block = read_available(streams[name])
            if block is None:
                continue
            activity = True
            if not block:
                pending.remove(name)
                continue
            room = max(0, limits[name] - len(buffers[name]))
            buffers[name].extend(block[:room])
            truncated[name] |= len(block) > room
        return activity

    try:
        while pending or process.poll() is None:
            if time.monotonic() >= deadline:
                timed_out = True
                _terminate(process, flags)
                # Capture already-buffered bytes without waiting on an inherited handle.
                cleanup_deadline = time.monotonic() + 0.1
                while pending and time.monotonic() < cleanup_deadline and drain_once():
                    pass
                break
            if not drain_once():
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        process.wait(timeout=2)
    except BaseException:
        _terminate(process, flags)
        raise
    finally:
        for stream in streams.values():
            stream.close()
    incomplete = bool(pending)
    return {'exit_code': process.returncode,
            'stdout': bytes(buffers['stdout']).decode('utf-8-sig', errors='replace'),
            'stderr': bytes(buffers['stderr']).decode('utf-8-sig', errors='replace'),
            'stdout_truncated': truncated['stdout'] or 'stdout' in pending,
            'stderr_truncated': truncated['stderr'] or 'stderr' in pending,
            'output_incomplete': incomplete, 'timed_out': timed_out}
