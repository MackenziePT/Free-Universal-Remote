"""Reject Windows NT device aliases in release updates and approved-root paths."""
import unittest

from release_security import ReleaseError, _safe_name
from remote_core import PolicyError, validate_windows_path


class WindowsReservedNameSecurityTests(unittest.TestCase):
    def test_signed_release_disallows_device_aliases(self):
        names = ("COM\u00b9.txt", "COM\u00b2", "LPT\u00b3.data",
                 "CONIN$", "CONOUT$.txt")
        for name in names:
            with self.subTest(name=name), self.assertRaises(ReleaseError):
                _safe_name("Agent/" + name)

    def test_remote_paths_disallow_console_aliases(self):
        for name in ("CONIN$", "CONOUT$.txt"):
            with self.subTest(name=name), self.assertRaises(PolicyError):
                validate_windows_path(r"C:\approved" + "\\" + name)

    def test_normal_non_reserved_filenames_remain_valid(self):
        for name in ("commercial.txt", "computer.txt", "LPT10.data",
                     "Coninvoice.txt", "model_version_3.txt"):
            with self.subTest(name=name):
                self.assertEqual(_safe_name("Agent/" + name), "Agent/" + name)
                validate_windows_path(r"C:\approved" + "\\" + name)


if __name__ == "__main__":
    unittest.main()
