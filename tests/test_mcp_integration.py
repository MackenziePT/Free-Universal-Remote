"""Real SDK, real stdio subprocesses, disposable policy and persistent operation IDs."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

HAS_MCP = importlib.util.find_spec('mcp') is not None
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_MCP, 'Install requirements.txt for real MCP integration')
class MCPIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.allowed = self.base / 'approved'
        self.allowed.mkdir()
        self.grants = self.base / 'grants.json'
        self.config = self.base / 'config.json'
        self.config.write_text(json.dumps({'allowed_roots': [str(self.allowed)],
            'backup_root': str(self.base/'backups'), 'grants_path': str(self.grants),
            'enable_writes': True}), encoding='utf-8-sig')
        self.env = {'HARMONY_MCP_CONFIG': str(self.config), 'LOCALAPPDATA': str(self.base)}

    @asynccontextmanager
    async def connect(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(command=sys.executable,
            args=[str(ROOT/'launch_server.py')], env=self.env)
        with (self.base/'mcp-stderr.txt').open('a', encoding='utf-8') as errors:
            async with stdio_client(params, errlog=errors) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=30)) as session:
                    await session.initialize()
                    yield session

    def text_result(self, result):
        self.assertFalse(result.isError, str(result))
        return json.loads(next(c.text for c in result.content if c.type == 'text'))

    async def test_protocol_schema_denials_and_read(self):
        async with self.connect() as session:
            listing = await session.list_tools()
            self.assertEqual(len(listing.tools), 27)
            for name in ('write_text_file', 'run_powershell', 'desktop_action'):
                tool = next(t for t in listing.tools if t.name == name)
                self.assertIn('operation_id', tool.inputSchema['required'])
            self.assertTrue(self.text_result(await session.call_tool('ping', {}))['alive'])
            doc = self.allowed/'unicode.txt'
            doc.write_text('português 🌿', encoding='utf-8')
            read = await session.call_tool('read_text_file', {'path':str(doc)})
            self.assertEqual(self.text_result(read)['text'], 'português 🌿')
            for name, args in (
                ('read_text_file', {'path':str(self.grants)}),
                ('write_text_file', {'path':str(self.allowed/'denied.txt'), 'content':'denied', 'operation_id':str(uuid.uuid4())}),
                ('run_powershell', {'command':'echo forbidden', 'operation_id':str(uuid.uuid4())}),
                ('desktop_screenshot', {}),
                ('desktop_action', {'action':'click','operation_id':str(uuid.uuid4())})):
                with self.subTest(tool=name):
                    self.assertTrue((await session.call_tool(name, args)).isError)
            self.assertFalse((self.allowed/'denied.txt').exists())

    async def test_restart_preserves_duplicate_guard_and_revocation(self):
        self.grants.write_text(json.dumps({'expires_at':time.time()+900,'capabilities':['writes']}))
        target = self.allowed/'once.txt'
        identifier = str(uuid.uuid4())
        args = {'path':str(target), 'content':'created once', 'operation_id':identifier}
        async with self.connect() as session:
            created = self.text_result(await session.call_tool('write_text_file', args))
            self.assertEqual(created['bytes'], 12)
        # Launch a fresh server process; the journal must still deny a repeat.
        async with self.connect() as session:
            status = self.text_result(await session.call_tool('check_operation', {'operation_id':identifier}))
            self.assertEqual(status['state'], 'completed')
            self.assertTrue((await session.call_tool('write_text_file', args)).isError)
            self.assertEqual(target.read_text(), 'created once')
            self.grants.unlink()
            denied_id = str(uuid.uuid4())
            denied = await session.call_tool('write_text_file', {**args,'operation_id':denied_id})
            self.assertTrue(denied.isError)
            self.assertEqual(self.text_result(await session.call_tool('check_operation', {'operation_id':denied_id}))['state'], 'not_found')

    async def test_invalid_privileged_requests_do_not_create_uncertain_journal_entries(self):
        # Synthetic local authorization in a disposable MCP instance, never the live user's grant.
        self.config.write_text(json.dumps({
            'allowed_roots': [str(self.allowed)],
            'backup_root': str(self.base/'backups'),
            'grants_path': str(self.grants),
            'enable_writes': True, 'enable_input': True,
        }), encoding='utf-8')
        self.grants.write_text(json.dumps({'expires_at': time.time()+900,
                                           'capabilities': ['writes', 'input']}))
        outside = self.base/'outside.txt'
        async with self.connect() as session:
            cases = (
                ('write_text_file', {'path': str(outside), 'content': 'never create'}),
                ('desktop_action', {'action': 'invalid-action'}),
                ('desktop_action', {'action': 'press', 'text': 'unapproved-key'}),
                ('desktop_action', {'action': 'type', 'text': ''}),
            )
            for name, data in cases:
                with self.subTest(tool=name, data=data):
                    identifier = str(uuid.uuid4())
                    response = await session.call_tool(name, {**data, 'operation_id': identifier})
                    self.assertTrue(response.isError)
                    status = self.text_result(await session.call_tool('check_operation',
                                                                      {'operation_id': identifier}))
                    self.assertEqual(status['state'], 'not_found', status)
        self.assertFalse(outside.exists())

    @unittest.skipUnless(os.name == 'nt', 'Native Windows PowerShell required')
    async def test_disposable_shell_grant_runs_then_revokes(self):
        # Separate stdio server, temporary policy and synthetic grant only.
        self.config.write_text(json.dumps({
            'allowed_roots': [str(self.allowed)],
            'backup_root': str(self.base/'backups'), 'grants_path': str(self.grants),
            'enable_writes': True, 'enable_shell': True,
        }), encoding='utf-8')
        self.grants.write_text(json.dumps({'expires_at': time.time()+900,
                                           'capabilities': ['shell']}))
        async with self.connect() as session:
            one = str(uuid.uuid4())
            result = self.text_result(await session.call_tool(
                'run_powershell', {'command': "Write-Output 'URM-SYNTHETIC-SHELL-PROBE'",
                                   'operation_id': one}))
            self.assertEqual(result['exit_code'], 0, result)
            self.assertIn('URM-SYNTHETIC-SHELL-PROBE', result['stdout'])
            status = self.text_result(await session.call_tool('check_operation',
                                                               {'operation_id': one}))
            self.assertEqual(status['state'], 'completed')
            self.grants.unlink()
            two = str(uuid.uuid4())
            self.assertTrue((await session.call_tool('run_powershell',
                        {'command': "Write-Output 'DENIED'", 'operation_id': two})).isError)
            status = self.text_result(await session.call_tool('check_operation',
                                                               {'operation_id': two}))
            self.assertEqual(status['state'], 'not_found')

    @unittest.skipUnless(os.name == 'nt', 'Interactive Windows desktop required')
    @unittest.skipIf(os.environ.get('URM_CI_HEADLESS') == '1',
                     'Interactive screen capture requires a dedicated desktop acceptance runner')
    async def test_disposable_screen_grant_captures_jpeg_in_memory_then_revokes(self):
        # Image bytes remain in process memory: never print, persist or publish screenshots.
        import base64
        self.config.write_text(json.dumps({
            'allowed_roots': [str(self.allowed)],
            'backup_root': str(self.base/'backups'), 'grants_path': str(self.grants),
            'enable_screen': True,
        }), encoding='utf-8')
        self.grants.write_text(json.dumps({'expires_at': time.time()+900,
                                           'capabilities': ['screen']}))
        async with self.connect() as session:
            result = await session.call_tool('desktop_screenshot',
                                             {'monitor': 1, 'max_width': 640})
            self.assertFalse(result.isError, 'Screen capture failed on the actual user session')
            images = [item for item in result.content if item.type == 'image']
            self.assertEqual(len(images), 1)
            data = base64.b64decode(images[0].data)
            self.assertTrue(data.startswith(bytes.fromhex('ffd8ff')))
            self.assertLessEqual(len(data), 2_000_000)
            del data, images, result
            self.grants.unlink()
            denied = await session.call_tool('desktop_screenshot', {'monitor': 1})
            self.assertTrue(denied.isError)

    async def test_smoke_preserves_explicit_config(self):
        result = await asyncio.to_thread(subprocess.run,
            [sys.executable,str(ROOT/'smoke_test.py')],
            env={**os.environ,**self.env}, capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('27 tools; ping OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
