"""Remote write idempotence is enforced at the MCP server boundary."""
import importlib.util
import json
import logging
import os
import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

class FakeFastMCP:
    def __init__(self, *args, **kwargs): self.tools = {}
    def tool(self, annotations=None):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register

class RemoteWriteTests(unittest.TestCase):
    def test_repeat_write_does_not_execute_or_create_second_backup(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / 'files'; data.mkdir()
            state = Path(td) / 'state'; state.mkdir()
            config = Path(td) / 'config.json'
            config.write_text(json.dumps({'allowed_roots':[str(data)],
                        'enable_writes':True, 'grants_path':str(state/'grants.json'),
                        'backup_root':str(state/'backups')}))
            import time
            (state/'grants.json').write_text(json.dumps({'expires_at':time.time()+300,
                                                        'capabilities':['writes']}))
            fake_fastmcp=types.ModuleType('mcp.server.fastmcp')
            fake_fastmcp.FastMCP=FakeFastMCP
            fake_fastmcp.Image=type('Image',(),{})
            script=Path(__file__).resolve().parents[1]/'server.py'
            spec=importlib.util.spec_from_file_location('isolated_write_server',script)
            mod=importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules,{'mcp':types.ModuleType('mcp'),
                  'mcp.server':types.ModuleType('mcp.server'), 'mcp.server.fastmcp':fake_fastmcp}), \
                 patch.dict(os.environ,{'HARMONY_MCP_CONFIG':str(config),'LOCALAPPDATA':td}), \
                 patch('logging.handlers.RotatingFileHandler', return_value=logging.NullHandler()):
                spec.loader.exec_module(mod)
                target=data/'file.txt'
                ident=str(uuid.uuid4())
                with self.assertRaises(ValueError):
                    mod.write_text_file(str(target),'before',operation_id='')
                self.assertFalse(target.exists())
                created=json.loads(mod.write_text_file(str(target),'before',operation_id=ident))
                self.assertEqual(created['sha256'],json.loads(mod.inspect_file(str(target)))['sha256'])
                with self.assertRaises(ValueError):
                    mod.write_text_file(str(target),'before',operation_id=ident)
                self.assertEqual(json.loads(mod.check_operation(ident))['state'],'completed')
                self.assertEqual(list((state/'backups').glob('*')) if (state/'backups').exists() else [], [])
                replacement_id = str(uuid.uuid4())
                sha_before = json.loads(mod.inspect_file(str(target)))['sha256']
                changed = json.loads(mod.write_text_file(str(target),'after',expected_sha256=sha_before,
                                                         operation_id=replacement_id))
                self.assertTrue(Path(changed['backup']).is_file())
                self.assertEqual(target.read_text(), 'after')
                with self.assertRaises(ValueError):
                    mod.write_text_file(str(target),'after',expected_sha256=sha_before,
                                        operation_id=replacement_id)
                self.assertEqual(len(list((state/'backups').glob('*.bak'))), 1)

    def test_crashed_write_does_not_retry(self):
        with tempfile.TemporaryDirectory() as td:
            import remote_core as core
            root=Path(td)/'allowed';root.mkdir()
            state=Path(td)/'state';state.mkdir()
            cfg=core.Config(allowed_roots=(root,),grants_path=state/'grants.json')
            from operation_journal import execute_once
            ident=str(uuid.uuid4())
            called=[]
            def fail():
                called.append(1)
                raise OSError('disk error')
            with self.assertRaises(OSError):execute_once(cfg,ident,'writes','fingerprint',fail)
            with self.assertRaises(core.PolicyError):execute_once(cfg,ident,'writes','fingerprint',fail)
            self.assertEqual(len(called),1)
            self.assertEqual(core.operation_status(cfg,ident)['state'],'uncertain')

if __name__=='__main__':unittest.main()
