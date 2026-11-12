"""Strip tunnel control-plane credentials from the MCP server environment."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    env = os.environ.copy()
    env.pop("CONTROL_PLANE_API_KEY", None)
    script = Path(__file__).resolve().parent / "server.py"
    return subprocess.call([sys.executable, str(script)], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
