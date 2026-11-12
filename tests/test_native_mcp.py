"""MCP end-to-end native files and durable task flows with synthetic local policy."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


class NativeMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="urm-native-mcp-")
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name)
        self.work = self.state / "workspace"
        self.work.mkdir()
        self.cfg = self.state / "config.json"
        self.grant = self.state / "grants.json"
        self.cfg.write_text(json.dumps({
            "allowed_roots": [str(self.work)],
            "backup_root": str(self.state / "backups"),
            "grants_path": str(self.grant),
            "enable_writes": True,
            "enable_shell": True,
            "enable_input": True,
        }), encoding="utf-8")
        self.grant.write_text(json.dumps({
            "expires_at": int(time.time())+900,
            "capabilities": ["writes", "shell", "input"],
        }), encoding="utf-8")
        self.env = {"HARMONY_MCP_CONFIG": str(self.cfg), "LOCALAPPDATA": str(self.state)}

    @asynccontextmanager
    async def connect(self):
        params = StdioServerParameters(command=sys.executable,
                                       args=[str(ROOT / "launch_server.py")],
                                       env=self.env)
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w, read_timeout_seconds=timedelta(seconds=30)) as client:
                await client.initialize()
                yield client

    def unpack(self, result):
        self.assertFalse(result.isError, str(result))
        return json.loads(next(c.text for c in result.content if c.type == "text"))

    async def test_native_file_tools_and_journal(self):
        src = self.work / "source.txt"
        src.write_text("olá 🌿", encoding="utf-8")
        folder = self.work / "sub"
        async with self.connect() as client:
            capabilities = self.unpack(await client.call_tool("product_capabilities", {}))
            self.assertFalse(capabilities["desktop_commander_required"])
            inv = await client.list_tools()
            self.assertGreaterEqual(len(inv.tools), 27)
            identifier = str(uuid.uuid4())
            result = self.unpack(await client.call_tool("create_folder", {
                "path": str(folder), "operation_id": identifier}))
            self.assertEqual(result["created"], str(folder))
            self.assertEqual(self.unpack(await client.call_tool("check_operation",
                {"operation_id": identifier}))["state"], "completed")
            copy_to = folder / "copied.txt"
            self.unpack(await client.call_tool("copy_file", {
                "source": str(src), "destination": str(copy_to), "operation_id": str(uuid.uuid4())}))
            move_to = folder / "moved.txt"
            self.unpack(await client.call_tool("move_file", {
                "source": str(copy_to), "destination": str(move_to),
                "operation_id": str(uuid.uuid4())}))
            self.assertEqual(move_to.read_text(encoding="utf-8"), "olá 🌿")
            self.assertTrue((await client.call_tool("copy_file", {
                "source": str(src), "destination": str(move_to),
                "operation_id": str(uuid.uuid4())})).isError)

    async def test_invalid_copy_does_not_claim_operation_id(self):
        source = self.work / "source.tmp"
        destination = self.work / "existing.tmp"
        source.write_text("source", encoding="utf-8")
        destination.write_text("keep", encoding="utf-8")
        operation_id = str(uuid.uuid4())
        async with self.connect() as client:
            denied = await client.call_tool("copy_file", {
                "source": str(source), "destination": str(destination),
                "operation_id": operation_id})
            self.assertTrue(denied.isError)
            status = self.unpack(await client.call_tool("check_operation",
                                {"operation_id": operation_id}))
            self.assertEqual(status["state"], "not_found")
        self.assertEqual(destination.read_text(), "keep")

    async def test_long_task_returns_output_after_reconnection(self):
        async with self.connect() as client:
            rec = self.unpack(await client.call_tool("start_task", {
                "executable": sys.executable, "arguments": ["-c", "print('NATIVE_JOB_PASS',flush=True)"],
                "cwd": str(self.work), "label": "MCP integration",
                "operation_id": str(uuid.uuid4())}))
            job_id = rec["job_id"]
        async with self.connect() as client:
            last = None
            for _ in range(30):
                last = self.unpack(await client.call_tool("task_status", {"job_id": job_id}))
                if last["status"] in {"exited", "exited_unobserved"}:
                    break
                await __import__("asyncio").sleep(0.1)
            text = self.unpack(await client.call_tool("task_output", {
                "job_id": job_id, "offset": 0, "limit": 4096}))["text"]
            self.assertIn("NATIVE_JOB_PASS", text)
            listed = self.unpack(await client.call_tool("list_tasks", {"limit": 20}))
            self.assertTrue(any(item["job_id"] == job_id for item in listed))
            # Running is not expected; completion can be 'exited_unobserved'
            # after the stdio server holding subprocess returncode closes.
            self.assertIn(last["status"], {"exited", "exited_unobserved"})

    async def test_revocation_does_not_consume_native_operation_id(self):
        self.grant.unlink()
        op = str(uuid.uuid4())
        async with self.connect() as client:
            denied = await client.call_tool("create_folder", {
                "path": str(self.work / "forbidden"), "operation_id": op})
            self.assertTrue(denied.isError)
            self.assertTrue((await client.call_tool("list_windows", {"limit": 5})).isError)
            self.assertTrue((await client.call_tool("list_tasks", {"limit": 5})).isError)
            self.assertTrue((await client.call_tool("task_output", {
                "job_id": str(uuid.uuid4()), "limit": 5})).isError)
            check = self.unpack(await client.call_tool("check_operation", {"operation_id": op}))
            self.assertEqual(check["state"], "not_found")
        self.assertFalse((self.work / "forbidden").exists())


if __name__ == "__main__":
    unittest.main()
