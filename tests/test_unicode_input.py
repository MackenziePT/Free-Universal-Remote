"""Focused tests for Win32 UTF-16 keyboard input representation."""
import ctypes
import unittest
from desktop_unicode import keyboard_units, INPUT, KEYBDINPUT, MOUSEINPUT


class UnicodeInputTests(unittest.TestCase):
    def test_surrogate_pairs_are_not_dropped(self):
        self.assertEqual(keyboard_units('ação 😀'), [0x61,0xe7,0xe3,0x6f,0x20,0xd83d,0xde00])

    def test_input_struct_alignment_matches_pointer_architecture(self):
        self.assertEqual(ctypes.sizeof(KEYBDINPUT), 24 if ctypes.sizeof(ctypes.c_void_p)==8 else 16)
        self.assertEqual(ctypes.sizeof(MOUSEINPUT), 32 if ctypes.sizeof(ctypes.c_void_p)==8 else 24)
        self.assertEqual(ctypes.sizeof(INPUT), 40 if ctypes.sizeof(ctypes.c_void_p)==8 else 28)

if __name__=='__main__': unittest.main()
