"""Behavioral tests for bounded universal search and binary reads."""
import base64
import tempfile
import unittest
from pathlib import Path
from remote_core import Config, PolicyError, search_files, read_binary


class UniversalOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'allowed'
        self.root.mkdir()
        self.outside = Path(self.tmp.name) / 'outside'
        self.outside.mkdir()
        self.cfg = Config(allowed_roots=(self.root.resolve(),))

    def test_search_finds_nested_files_without_leaving_allowed_tree(self):
        (self.root/'src').mkdir()
        (self.root/'src'/'alpha.py').write_text('alpha')
        (self.root/'src'/'beta.md').write_text('beta')
        self.assertEqual([x['name'] for x in search_files(self.cfg,str(self.root),'*.py')['matches']], ['alpha.py'])

    def test_search_never_follows_symlinks(self):
        (self.outside/'secret.py').write_text('password')
        try:
            (self.root/'alias').symlink_to(self.outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Filesystem does not support symlinks')
        self.assertEqual(search_files(self.cfg, str(self.root),'*.py')['matches'], [])

    def test_search_depth_and_limits_are_bounded(self):
        (self.root/'a').mkdir()
        (self.root/'a'/'match.txt').write_text('yes')
        self.assertEqual(search_files(self.cfg,str(self.root),'*.txt',max_depth=0)['matches'], [])
        with self.assertRaises(PolicyError):
            search_files(self.cfg,str(self.root),'*',max_results=1000000)

    def test_binary_read_is_bounded_and_exact(self):
        p = self.root/'bytes.bin'
        p.write_bytes(bytes(range(256)))
        d = read_binary(self.cfg,str(p),offset=11,max_bytes=13)
        self.assertEqual(base64.b64decode(d['base64']), bytes(range(11,24)))
        self.assertEqual(d['next_offset'],24)
        self.assertTrue(d['truncated'])

    def test_binary_read_denies_outside_path_and_invalid_offset(self):
        p = self.outside/'no.bin'
        p.write_bytes(b'secret')
        with self.assertRaises(PolicyError): read_binary(self.cfg,str(p))
        with self.assertRaises(PolicyError): read_binary(self.cfg,str(self.root/'not-there'),offset=-1)

if __name__ == '__main__': unittest.main()
