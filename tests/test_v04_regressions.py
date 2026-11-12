"""Security and correctness regression tests for v0.4 behavior."""
import hashlib
import json
import os
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from remote_core import Config, PolicyError, file_info, grant_allowed, load_config, read_text, write_text

class V04Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'root'
        self.root.mkdir()
        self.grant = Path(self.tmp.name)/'grant.json'
        self.grant.write_text(json.dumps({'expires_at':time.time()+300, 'capabilities':['writes']}))
        self.cfg=Config(allowed_roots=(self.root.resolve(),), enable_writes=True,
                        grants_path=self.grant, backup_root=Path(self.tmp.name)/'backups')

    def test_symlinked_intermediate_directory_rejected_even_inside_root(self):
        sub=self.root/'real'
        sub.mkdir()
        (sub/'file.txt').write_text('hello')
        alias=self.root/'alias'
        try: alias.symlink_to(sub, target_is_directory=True)
        except OSError: self.skipTest('symlinks unavailable')
        with self.assertRaisesRegex(PolicyError, 'link|reparse|junction'):
            read_text(self.cfg, str(alias/'file.txt'))
        with self.assertRaisesRegex(PolicyError, 'link|reparse|junction'):
            write_text(self.cfg, str(alias/'new.txt'), 'text')

    def test_grant_symlink_is_not_an_authorization(self):
        original=self.grant
        second=original.with_suffix('.other')
        original.replace(second)
        try: original.symlink_to(second)
        except OSError: self.skipTest('symlinks unavailable')
        self.assertFalse(grant_allowed(self.cfg, 'writes'))

    def test_config_rejects_boolean_or_fractional_limits(self):
        for limit in (True, 0.5, 'infinite', -5):
            with self.subTest(limit=limit):
                conf=Path(self.tmp.name)/'config.json'
                conf.write_text(json.dumps({'allowed_roots':[str(self.root)], 'max_write_bytes':limit}))
                with self.assertRaises((PolicyError, ValueError, TypeError)):
                    load_config(conf)

    def test_utf8_pagination_never_splits_code_point(self):
        path=self.root/'unicode.txt'
        path.write_text('abc😀def', encoding='utf-8')
        first=read_text(self.cfg,str(path),max_bytes=5)
        self.assertEqual(first['text'],'abc')
        self.assertEqual(first['returned_bytes'],3)
        self.assertEqual(first['next_offset'],3)
        self.assertTrue(first['truncated'])
        second=read_text(self.cfg,str(path),offset=first['next_offset'],max_bytes=5)
        self.assertEqual(second['text'],'😀d')
        self.assertEqual(first['text']+second['text'],'abc😀d')

    def test_write_refuses_target_replaced_with_same_content_during_backup(self):
        p=self.root/'victim.txt'
        p.write_text('original')
        digest=file_info(self.cfg,str(p))['sha256']
        import remote_core
        original_copy=remote_core.shutil.copy2
        def switch_target(src,dest,*args,**kwargs):
            result=original_copy(src,dest,*args,**kwargs)
            os.unlink(p)
            p.write_text('original') # same SHA, different inode
            return result
        with patch('remote_core.shutil.copy2',side_effect=switch_target):
            with self.assertRaisesRegex(PolicyError,'changed|identity'):
                write_text(self.cfg,str(p),'new',expected_sha256=digest)
        self.assertEqual(p.read_text(),'original')

if __name__=='__main__': unittest.main()

class MoreConfigTests(unittest.TestCase):
    def test_unknown_flag_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'config.json'
            p.write_text(json.dumps({'allowed_roots':[td], 'enable_write':True}))
            with self.assertRaisesRegex(PolicyError, 'Unknown configuration'):
                load_config(p)

    def test_string_boolean_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'config.json'
            p.write_text(json.dumps({'allowed_roots':[td], 'enable_shell':'false'}))
            with self.assertRaisesRegex(PolicyError, 'boolean'):
                load_config(p)
