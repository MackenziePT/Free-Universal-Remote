"""Security regression checks: unsafe Windows file names and malformed paging limits."""
import tempfile
import unittest
from pathlib import Path

from remote_core import Config, PolicyError, list_directory, read_text, validate_windows_path


class WindowsPathSafetyTests(unittest.TestCase):
    def test_windows_device_names_are_forbidden(self):
        for target in ('CON', 'nul.txt', 'COM1.log', 'LPT9', 'AUX', 'prn:', 'COM1 .txt'):
            with self.subTest(target=target), self.assertRaises(PolicyError):
                validate_windows_path('C:\\Users\\test\\WORK\\' + target)

    def test_windows_aliases_and_ambiguous_components_forbidden(self):
        for target in ('a.txt:stream', 'bad.', 'bad ', 'a?.txt', 'name|pipe', '..\\secret.txt'):
            with self.subTest(target=target), self.assertRaises(PolicyError):
                validate_windows_path('C:\\Users\\test\\WORK\\' + target)

    def test_unc_and_device_prefixes_forbidden(self):
        for target in ('\\\\server\\share\\a.txt', '\\\\?\\C:\\root\\a.txt', '\\\\.\\C:\\root\\a.txt'):
            with self.subTest(target=target), self.assertRaises(PolicyError):
                validate_windows_path(target)

    def test_ordinary_windows_paths_allowed(self):
        for target in ('C:\\Users\\test\\WORK\\file.txt', 'E:\\SISTEMA OPERATIVO AI (Harmony)\\README.md', 'C:/Work/log-2026.txt'):
            with self.subTest(target=target):
                validate_windows_path(target)


class StrictArgumentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = Config(allowed_roots=(self.root.resolve(),))
        (self.root / 'page.txt').write_text('abc', encoding='utf-8')

    def test_bad_offsets_are_rejected(self):
        for bad in (-1, True, '12', 1.1):
            with self.subTest(bad=bad), self.assertRaises(PolicyError):
                read_text(self.cfg, str(self.root / 'page.txt'), offset=bad)

    def test_bad_page_sizes_are_rejected(self):
        for bad in (0, -1, True, 2.5, '300'):
            with self.subTest(bad=bad), self.assertRaises(PolicyError):
                read_text(self.cfg, str(self.root / 'page.txt'), max_bytes=bad)

    def test_bad_directory_limits_are_rejected(self):
        for bad in (0, -20, True, '50', 1.2):
            with self.subTest(bad=bad), self.assertRaises(PolicyError):
                list_directory(self.cfg, str(self.root), limit=bad)

if __name__ == '__main__':
    unittest.main()

class TraversalNormalizationTests(unittest.TestCase):
    def test_dotdot_never_skips_intermediate_link_check(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / 'approved'
            base.mkdir()
            (base / 'sub').mkdir()
            cfg = Config(allowed_roots=(base.resolve(),))
            with self.assertRaises(PolicyError):
                from remote_core import safe_path
                safe_path(str(base / 'sub' / '..' / 'safe.txt'), cfg)

class ConfiguredReadCapTests(unittest.TestCase):
    def test_requested_page_is_capped_by_config_without_disabling_default_call(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            f = base / 'small.txt'
            f.write_text('abcdefghijk', encoding='utf-8')
            cfg = Config(allowed_roots=(base.resolve(),), max_read_bytes=4)
            page = read_text(cfg, str(f))  # caller omits max_bytes; default is 16384
            self.assertEqual(page['text'], 'abcd')
            self.assertTrue(page['truncated'])

class HugeOffsetTests(unittest.TestCase):
    def test_seek_offset_outside_signed_64_bit_range_rejected_as_policy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'tiny.txt'
            path.write_text('a', encoding='utf-8')
            cfg = Config(allowed_roots=(root.resolve(),))
            with self.assertRaises(PolicyError):
                read_text(cfg, str(path), offset=2**100)
