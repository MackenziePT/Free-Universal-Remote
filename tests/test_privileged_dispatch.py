"""End-to-end server dispatch with fake MCP SDK, real local grant and journal."""
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
        def decorate(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorate

class PrivilegedDispatchTests(unittest.TestCase):
    def test_desktop_retry_is_rejected_even_after_original_returned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'data'
            root.mkdir()
            state = Path(td) / 'state'
            state.mkdir()
            cfg = Path(td) / 'config.json'
            cfg.write_text(json.dumps({'allowed_roots':[str(root)],
                                      'enable_input':True,
                                      'backup_root':str(state/'backups'),
                                      'grants_path':str(state/'grants.json')}))
            import time
            (state/'grants.json').write_text(json.dumps({'expires_at':time.time()+300,
                                                        'capabilities':['input']}))
            fake_mcp = types.ModuleType('mcp')
            fake_srv = types.ModuleType('mcp.server')
            fake_fastmcp = types.ModuleType('mcp.server.fastmcp')
            fake_fastmcp.FastMCP=FakeFastMCP
            fake_fastmcp.Image=type('Image',(),{})
            script=Path(__file__).resolve().parents[1]/'server.py'
            spec=importlib.util.spec_from_file_location('isolated_server_dispatch',script)
            module=importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules,{'mcp':fake_mcp,'mcp.server':fake_srv,
                                          'mcp.server.fastmcp':fake_fastmcp}), \
                 patch.dict(os.environ,{'HARMONY_MCP_CONFIG':str(cfg),'LOCALAPPDATA':td}), \
                 patch('logging.handlers.RotatingFileHandler', return_value=logging.NullHandler()):
                spec.loader.exec_module(module)
                operation_id=str(uuid.uuid4())
                with patch.object(module,'_desktop_action',return_value='{"ok":true}') as gui:
                    self.assertEqual(json.loads(module.desktop_action('click',operation_id=operation_id,x=3,y=4)), {'ok':True})
                    with self.assertRaises(ValueError):
                        module.desktop_action('click',operation_id=operation_id,x=3,y=4)
                    gui.assert_called_once()
                self.assertEqual(json.loads(module.check_operation(operation_id))['state'],'completed')

class DesktopInputRoutingTests(unittest.TestCase):
    def test_click_press_and_unicode_type_route_without_real_gui_actions(self):
        # Exercise actual action routing; fake OS input so no user window is touched.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            allowed = base/'allowed'
            allowed.mkdir()
            cfg = base/'config.json'
            cfg.write_text(json.dumps({'allowed_roots': [str(allowed)],
                                       'backup_root': str(base/'backups'),
                                       'grants_path': str(base/'grants.json')}))
            fake_sdk = types.ModuleType('mcp')
            fake_server = types.ModuleType('mcp.server')
            fake_fast = types.ModuleType('mcp.server.fastmcp')
            fake_fast.FastMCP = FakeFastMCP
            fake_fast.Image = type('Image', (), {})
            fake_gui = types.ModuleType('pyautogui')
            from unittest.mock import Mock
            fake_gui.click = Mock()
            fake_gui.press = Mock()
            fake_gui.failSafeCheck = Mock()
            spec = importlib.util.spec_from_file_location(
                'isolated_desktop_route', Path(__file__).resolve().parents[1]/'server.py')
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {'mcp':fake_sdk, 'mcp.server':fake_server,
                                          'mcp.server.fastmcp':fake_fast,
                                          'pyautogui':fake_gui}), \
                 patch.dict(os.environ, {'HARMONY_MCP_CONFIG':str(cfg), 'LOCALAPPDATA':td}), \
                 patch('logging.handlers.RotatingFileHandler', return_value=logging.NullHandler()), \
                 patch('desktop_unicode.virtual_screen_bounds', return_value=(-100, -100, 1000, 1000)), \
                 patch('desktop_unicode.type_unicode', return_value=5) as unicode_input:
                spec.loader.exec_module(module)
                self.assertEqual(module._desktop_action('click', -20, 100, ''), '{"ok":true}')
                self.assertEqual(module._desktop_action('press', 0, 0, 'esc'), '{"ok":true}')
                self.assertEqual(module._desktop_action('type', 0, 0, 'olá 🌿'), '{"ok":true}')
                fake_gui.click.assert_called_once_with(x=-20,y=100)
                fake_gui.press.assert_called_once_with('esc')
                unicode_input.assert_called_once()
                self.assertEqual(unicode_input.call_args.args[0], 'olá 🌿')
                with self.assertRaises(ValueError):
                    module._desktop_action('press',0,0,'win+r')
                self.assertEqual(fake_gui.press.call_count, 1)


if __name__=='__main__': unittest.main()
