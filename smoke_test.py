"""Real MCP stdio handshake and minimal tool smoke test (run after pip install)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    script = Path(__file__).resolve().parent / "launch_server.py"
    # SDK default inheritance omits project-specific config overrides.
    # Pass only needed settings; never pass the runtime key to the MCP process.
    env = {name: os.environ[name] for name in ('HARMONY_MCP_CONFIG', 'LOCALAPPDATA') if name in os.environ}
    params = StdioServerParameters(command=sys.executable, args=[str(script)], env=env)
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            result = await session.initialize()
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            required = {"ping", "agent_policy", "browse_directory", "search_files", "read_binary_chunk",
                        "product_capabilities", "list_windows", "focus_window",
                        "create_folder", "copy_file", "move_file", "recycle_file",
                        "start_task", "list_tasks", "task_status", "task_output", "stop_task",
                        "desktop_action", "desktop_screenshot", "run_powershell", "write_text_file", "check_operation"}
            if not required <= set(names) or len(names) != 27:
                raise RuntimeError(f"Unexpected MCP tool inventory: {names}")
            status = await session.call_tool("check_operation", arguments={"operation_id": "5e1d7abf-64a9-43ad-91d9-052f8683e6ca"})
            if status.isError:
                raise RuntimeError("Status lookup returned an MCP error")
            ping_result = await session.call_tool("ping", arguments={})
            if ping_result.isError:
                raise RuntimeError("Ping returned an MCP error")
            forbidden = await session.call_tool("read_text_file", arguments={"path": "not-absolute.txt"})
            if not forbidden.isError:
                raise RuntimeError("Relative-path denial must be a genuine MCP error")
            print(f"MCP handshake OK; {len(names)} tools; ping OK")
            print("Tools:", ", ".join(sorted(names)))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=30))
