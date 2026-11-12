"""Native Win32 window inspection and consent-gated foreground selection."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os

from remote_core import PolicyError

if os.name == "nt":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    _enum_windows = user32.EnumWindows
    _enum_windows.argtypes = (ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM)
    _enum_windows.restype = wintypes.BOOL
    _get_text_length = user32.GetWindowTextLengthW
    _get_text_length.argtypes = (wintypes.HWND,)
    _get_text_length.restype = ctypes.c_int
    _get_text = user32.GetWindowTextW
    _get_text.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    _get_text.restype = ctypes.c_int
    _visible = user32.IsWindowVisible
    _visible.argtypes = (wintypes.HWND,)
    _visible.restype = wintypes.BOOL
    _process_id = user32.GetWindowThreadProcessId
    _process_id.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    _process_id.restype = wintypes.DWORD
    _get_rect = user32.GetWindowRect
    _get_rect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    _get_rect.restype = wintypes.BOOL
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL


def _require_windows():
    if os.name != "nt":
        raise PolicyError("Window automation is supported only on Windows")


def window_list(limit: int = 80) -> list[dict]:
    _require_windows()
    if type(limit) is not int or not 1 <= limit <= 200:
        raise PolicyError("Window listing limit must be between 1 and 200")
    results: list[dict] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if len(results) >= limit:
            return False
        if not _visible(hwnd) or _get_text_length(hwnd) < 1:
            return True
        title = ctypes.create_unicode_buffer(min(_get_text_length(hwnd) + 1, 257))
        _get_text(hwnd, title, len(title))
        if not title.value.strip():
            return True
        pid = wintypes.DWORD()
        _process_id(hwnd, ctypes.byref(pid))
        rect = wintypes.RECT()
        _get_rect(hwnd, ctypes.byref(rect))
        results.append({
            "handle": int(hwnd), "pid": int(pid.value),
            "title": title.value[:256],
            "bounds": [rect.left, rect.top, rect.right, rect.bottom],
        })
        return True

    _enum_windows(callback_type(callback), 0)
    return results


def focus_window(handle: int, expected_pid: int) -> dict:
    _require_windows()
    if type(handle) is not int or type(expected_pid) is not int or handle <= 0 or expected_pid <= 0:
        raise PolicyError("Window handle and expected PID must be positive integers")
    if not bool(user32.IsWindow(wintypes.HWND(handle))):
        raise PolicyError("Window no longer exists")
    pid = wintypes.DWORD()
    _process_id(wintypes.HWND(handle), ctypes.byref(pid))
    if pid.value != expected_pid:
        raise PolicyError("Window PID changed, focus denied")
    user32.ShowWindow(wintypes.HWND(handle), 9)  # SW_RESTORE, no elevation
    if not user32.SetForegroundWindow(wintypes.HWND(handle)):
        raise PolicyError("Windows denied foreground focus")
    return {"focused_handle": handle, "pid": expected_pid}
