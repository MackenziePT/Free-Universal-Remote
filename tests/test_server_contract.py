"""Exercises tool-registration wiring with an in-process SDK fake.

This deliberately does NOT substitute for a real MCP JSON-RPC handshake.
"""
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
    def __init__(self, *args, **kwargs):
        self.tools = {}
        self.annotations = {}

    def tool(self, annotations=None):
        def decorate(fn):
            self.tools[fn.__name__] = fn
            self.annotations[fn.__name__] = annotations
            return fn
        return decorate


class ServerContractTests(unittest.TestCase):
    def test_default_tools_are_registered_and_deny_unapproved_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / 'approved'
            root.mkdir()
            config = base / 'config.json'
            config.write_text(json.dumps({
                'allowed_roots': [str(root)],
                'backup_root': str(base / 'backup'),
                'grants_path': str(base / 'grants.json'),
            }))
            fake_mcp = types.ModuleType('mcp')
            fake_server = types.ModuleType('mcp.server')
            fake_fastmcp = types.ModuleType('mcp.server.fastmcp')
            fake_fastmcp.FastMCP = FakeFastMCP
            fake_fastmcp.Image = type('Image', (), {})
            filename = Path(__file__).resolve().parents[1] / 'server.py'
            spec = importlib.util.spec_from_file_location('harmony_mock_server', filename)
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {'mcp':fake_mcp, 'mcp.server':fake_server,
                                          'mcp.server.fastmcp':fake_fastmcp}), \
                 patch.dict(os.environ, {'HARMONY_MCP_CONFIG':str(config), 'LOCALAPPDATA':td}), \
                 patch('logging.handlers.RotatingFileHandler', return_value=logging.NullHandler()):
                spec.loader.exec_module(module)
                expected = {'ping','agent_policy','get_system_metrics','list_processes',
                            'windows_diagnostic','browse_directory','read_text_file',
                            'inspect_file','write_text_file','run_powershell',
                            'desktop_screenshot','desktop_action','search_files','read_binary_chunk','check_operation',
                            'product_capabilities', 'list_windows', 'focus_window', 'create_folder',
                            'copy_file', 'move_file', 'recycle_file', 'start_task', 'list_tasks',
                            'task_status', 'task_output', 'stop_task'}
                self.assertEqual(set(module.mcp.tools), expected)
                self.assertTrue(json.loads(module.ping())['alive'])
                self.assertEqual(json.loads(module.ping())['version'], '1.0.0-rc5.1-dev')
                self.assertEqual(json.loads(module.check_operation('5e1d7abf-64a9-43ad-91d9-052f8683e6ca'))['state'], 'not_found')
                target = root / 'probe.txt'
                target.write_text('verified MCP dispatch', encoding='utf-8')
                self.assertIn('verified MCP dispatch', json.loads(module.read_text_file(str(target)))['text'])
                self.assertEqual(json.loads(module.inspect_file(str(target)))['size'], len('verified MCP dispatch'))
                self.assertEqual(len(json.loads(module.browse_directory(str(root)))['entries']), 1)
                self.assertEqual(json.loads(module.search_files(str(root), '*.txt'))['matches'][0]['name'], 'probe.txt')
                self.assertEqual(json.loads(module.read_binary_chunk(str(target),0,5))['returned_bytes'], 5)
                with self.assertRaises(ValueError): module.windows_diagnostic('not_allowed')
                with self.assertRaises(ValueError): module.write_text_file(str(root/'new.txt'),'secret',operation_id=str(uuid.uuid4()))
                with self.assertRaises(ValueError): module.run_powershell('Get-Process',operation_id=str(uuid.uuid4()))
                with self.assertRaises(ValueError): module.desktop_screenshot()
                with self.assertRaises(ValueError): module.desktop_action('click',operation_id=str(uuid.uuid4()))
                self.assertFalse((root / 'new.txt').exists())
                self.assertTrue(module.mcp.annotations['inspect_file']['readOnlyHint'])
                self.assertFalse(module.mcp.annotations['run_powershell']['readOnlyHint'])


if __name__ == '__main__':
    unittest.main()
