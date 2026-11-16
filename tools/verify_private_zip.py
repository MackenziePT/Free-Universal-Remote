"""Independent smoke test of the exact ZIP after extraction on Windows."""
from __future__ import annotations
import asyncio
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "evidence" / "qa" / "UniversalRemote-RC5.1-20261113-HARDENED-PRIVATE-UNSIGNED.zip"
PREFIX = "UniversalRemote-RC5.1-HARDENED-PRIVATE"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


async def handshake(exe: Path, env: dict) -> int:
    params = StdioServerParameters(command=str(exe), args=[], env=env)
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=35)) as session:
            await session.initialize()
            tools = await session.list_tools()
            ping = await session.call_tool("ping", {})
            if ping.isError or len(tools.tools) != 27:
                raise AssertionError("MCP handshake or tool inventory failed")
            return len(tools.tools)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="urm-unpack-") as tmp:
        dest = Path(tmp)
        with zipfile.ZipFile(ARCHIVE) as arc:
            for item in arc.infolist():
                p = PurePosixPath(item.filename)
                if p.is_absolute() or ".." in p.parts or not p.parts or p.parts[0] != PREFIX:
                    raise RuntimeError("Unsafe zip path")
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError("Symlink entries forbidden")
            if arc.testzip() is not None:
                raise RuntimeError("Corrupt zip")
            arc.extractall(dest)
        base = dest / PREFIX
        manifest = json.loads((base / "BUILD-MANIFEST.json").read_text("utf-8"))
        if manifest["publishable"] is not False or manifest["format"] != 2:
            raise RuntimeError("Unexpected release channel")
        for entry in manifest["files"]:
            p = base / entry["path"]
            if not p.is_file() or p.stat().st_size != entry["bytes"] or sha256(p) != entry["sha256"]:
                raise RuntimeError("Corrupt or missing extracted file: " + entry["path"])
        if sha256(base / "bin" / "tunnel-client.exe") != manifest["tunnel_client"]["sha256"]:
            raise RuntimeError("Tunnel client digest mismatch")
        env = {name: value for name, value in os.environ.items()
               if not name.upper().startswith("_PYI_") and
               name.upper() not in {"PYINSTALLER_RESET_ENVIRONMENT",
                                    "PYINSTALLER_SUPPRESS_SPLASH_SCREEN"}}
        for key in ("CONTROL_PLANE_API_KEY", "HARMONY_MCP_CONFIG",
                    "UNIVERSAL_REMOTE_DATA_HOME", "PYTHONPATH", "PYTHONHOME"):
            env.pop(key, None)
        env["PATH"] = os.pathsep.join([str(Path(os.environ["SystemRoot"]) / "System32"),
                                       os.environ["SystemRoot"]])
        state = dest / "profile"
        state.mkdir()
        env["LOCALAPPDATA"] = str(state)
        probes = [
            ("GUI", "UniversalRemote-Preview.exe", "--self-test", ""),
            ("Agent", "UniversalRemoteAgent-Preview.exe", "--health-probe", "UNIVERSAL_REMOTE_AGENT_HEALTH_OK"),
            ("Bridge", "UniversalRemoteBridge-Preview.exe", "--health-probe", "UNIVERSAL_REMOTE_TUNNEL_BRIDGE_HEALTH_OK"),
            ("Tunnel", "UniversalRemoteTunnel-Preview.exe", "--self-test", "UNIVERSAL_REMOTE_TUNNEL_SELFTEST_OK"),
            ("Updater", "UniversalRemoteUpdater-Preview.exe", "trust-profile", '"channel": "PRIVATE_QA"'),
        ]
        for folder, exe, argument, marker in probes:
            binary = base / folder / exe
            x = subprocess.run([str(binary), argument], cwd=binary.parent,
                               env=env, capture_output=True, text=True, timeout=70)
            if x.returncode != 0 or marker not in x.stdout:
                raise RuntimeError(f"Extracted {folder} launch failed: {x.returncode}")
        agent = base / "Agent" / "UniversalRemoteAgent-Preview.exe"
        without = subprocess.run([str(agent), "--version"], env=env,
                                 capture_output=True, text=True, timeout=30)
        if without.returncode != 12:
            raise RuntimeError("Unconfigured agent must deny access")
        home = state / "UniversalRemote"
        home.mkdir()
        allowed = dest / "approved"
        allowed.mkdir()
        config = {
            "allowed_roots": [str(allowed)],
            "backup_root": str(home / "backups"),
            "grants_path": str(home / "grants.json"),
            "enable_writes": False, "enable_shell": False,
            "enable_screen": False, "enable_input": False,
        }
        (home / "config.json").write_text(json.dumps(config), encoding="utf-8")
        count = asyncio.run(handshake(agent, env))
        if (home / "grants.json").exists():
            raise RuntimeError("Unexpected elevated permission grant")
        print("EXTRACTED_PRIVATE_ZIP_ACCEPTANCE_PASS", json.dumps({
            "archive_sha256": sha256(ARCHIVE), "files": len(manifest["files"]),
            "components": len(probes), "mcp_tools": count,
            "tunnel_client_sha256": manifest["tunnel_client"]["sha256"],
            "grant_created": False,
        }), flush=True)


if __name__ == "__main__":
    main()
