"""Pass the stdio command to tunnel-client without PowerShell quote rewriting.

tunnel-client v0.0.16 parses mcp.command with shell-style quoting, including on
Windows. Single-quote escaping preserves Windows backslashes and apostrophes.
Python subprocess sends the resulting command as one argument with shell=False.
"""
import argparse
from pathlib import Path
import re
import shlex
import subprocess
import sys


def mcp_command(python, server):
    return shlex.join([str(python), str(server)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tunnel-id', required=True)
    args = parser.parse_args(argv)
    if re.fullmatch(r'tunnel_[0-9a-f]{32}', args.tunnel_id) is None:
        parser.error('Invalid tunnel ID format')
    root = Path(__file__).resolve().parent
    command = mcp_command(sys.executable, root/'launch_server.py')
    profile = Path.home() / '.config' / 'tunnel-client' / 'harmony-remote.yaml'
    if profile.exists():
        if not profile.is_file() or profile.stat().st_size > 16384:
            raise SystemExit('Existing tunnel profile is invalid or too large; refusing replacement.')
        contents = profile.read_text(encoding='utf-8-sig')
        found = re.search(r'(?m)^[ \t]*tunnel_id:[ \t]*["\']?(tunnel_[0-9a-f]{32})["\']?[ \t]*$', contents)
        uses_env = bool(re.search(r'(?m)^[ \t]*api_key:[ \t]*["\']?env:CONTROL_PLANE_API_KEY["\']?[ \t]*$', contents))
        server = bool(re.search(r'(?m)^[ \t]*command:.*launch_server\.py', contents))
        if found and found.group(1) == args.tunnel_id and uses_env and server:
            print('Matching private tunnel profile already prepared; no overwrite needed.')
            return 0
        raise SystemExit('Existing tunnel profile differs from requested ID or security policy; no change made.')
    result = subprocess.run([str(root/'bin/tunnel-client.exe'), 'init',
        '--sample', 'sample_mcp_stdio_local', '--profile', 'harmony-remote',
        '--tunnel-id', args.tunnel_id, '--mcp-command', command], shell=False)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
