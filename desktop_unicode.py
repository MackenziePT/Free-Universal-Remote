"""Unicode keyboard injection using documented Win32 SendInput KEYEVENTF_UNICODE.

Only invoked after the MCP desktop-input capability and local temporary grant
have both been checked. It does not bypass UAC or Windows secure desktop.
"""
from __future__ import annotations

import ctypes
import os
# Win32 LONG/DWORD are 32-bit even when native Unix 'long' is 64-bit.
WORD = ctypes.c_uint16
DWORD = ctypes.c_uint32
LONG = ctypes.c_int32
UINT = ctypes.c_uint32
from typing import Callable

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", WORD), ("wScan", WORD),
                ("dwFlags", DWORD), ("time", DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", LONG), ("dy", LONG),
                ("mouseData", DWORD), ("dwFlags", DWORD),
                ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD),
                ("wParamH", WORD)]


class INPUTDATA(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", DWORD), ("data", INPUTDATA)]


def keyboard_units(text: str) -> list[int]:
    """The Win32 Unicode scan-code path consumes UTF-16 code units."""
    if not isinstance(text, str) or not 1 <= len(text) <= 500:
        raise ValueError("Text must contain 1-500 Unicode characters")
    encoded = text.encode('utf-16-le')
    return [int.from_bytes(encoded[i:i + 2], 'little')
            for i in range(0, len(encoded), 2)]


def type_unicode(text: str, check_abort: Callable[[], None] | None = None) -> int:
    if os.name != 'nt':
        raise OSError('Windows Unicode input requires Windows')
    # LOAD the Windows API only after validation and authorization.
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    send_input = user32.SendInput
    send_input.argtypes = [UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    send_input.restype = UINT
    sent = 0
    for code in keyboard_units(text):
        if check_abort is not None:
            check_abort()
        for flags in (0x0004, 0x0004 | 0x0002):
            event = INPUT(type=1, data=INPUTDATA(ki=KEYBDINPUT(0, code, flags, 0, 0)))
            if send_input(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
                raise OSError(ctypes.get_last_error(), 'Win32 SendInput failed; application may be elevated or input blocked')
        sent += 1
    return sent


def virtual_screen_bounds() -> tuple[int, int, int, int]:
    """Win32 virtual desktop bounds (left, top, right-exclusive, bottom-exclusive).

    Can include negative coordinates for a monitor left/above the primary.
    Do not infer these bounds from pyautogui.size(), which reports primary only.
    """
    if os.name != 'nt':
        raise OSError('Virtual desktop geometry requires Windows')
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    get_metric = user32.GetSystemMetrics
    get_metric.argtypes = [ctypes.c_int]
    get_metric.restype = ctypes.c_int
    left, top = get_metric(76), get_metric(77)
    width, height = get_metric(78), get_metric(79)
    if width < 1 or height < 1:
        raise OSError('No usable virtual screen geometry')
    return (left, top, left + width, top + height)


def validate_click_coordinates(x: int, y: int,
                               bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    if type(x) is not int or type(y) is not int:
        raise ValueError('Screen coordinates must be integers')
    left, top, right, bottom = bounds
    if not left <= x < right or not top <= y < bottom:
        raise ValueError('Click coordinates outside available virtual desktop')
    return (x, y)
