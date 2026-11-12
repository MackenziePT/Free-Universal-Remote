"""Offline init with official Linux tunnel-client, no connection/doctor/run.

The official client validates the command using its own parser and writes only
disposable profiles. A POSIX directory with literal backslashes checks the same
escaping rule that is required for Windows paths. This is not a Windows test.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from initialize_tunnel import mcp_command

parser = argparse.ArgumentParser()
parser.add_argument('--client', required=True)
args = parser.parse_args()
if os.name == 'nt':
    parser.error('This fixture uses POSIX filenames containing literal backslashes.')
with tempfile.TemporaryDirectory(prefix='universal-offline-client-') as directory:
    base = Path(directory)
    app = base/r"C:\Users\O'Neil\Remote MCP"
    app.mkdir()
    python = app/'python.exe'
    python.symlink_to(sys.executable)
    server = app/'launch_server.py'
    server.write_text('# Only existence is inspected by tunnel-client init.\n')
    profile_dir = base/'profiles'
    for mode, command in [('old', '"'+str(python)+'" "'+str(server)+'"'),
                          ('fixed', mcp_command(python, server))]:
        result = subprocess.run([args.client, 'init', '--sample', 'sample_mcp_stdio_local',
            '--profile', mode, '--profile-dir', str(profile_dir), '--tunnel-id', 'tunnel_'+'a'*32,
            '--health-listen-addr', '127.0.0.1:0', '--mcp-command', command],
            env={**os.environ, 'CONTROL_PLANE_API_KEY': 'synthetic-unused-no-connection'},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15)
        profile = profile_dir/(mode+'.yaml')
        if mode == 'old':
            if result.returncode == 0 or profile.exists():
                raise AssertionError('Expected original command backslash-loss failure')
            if 'mcp-command preflight failed' not in result.stdout:
                raise AssertionError(result.stdout)
            print('RED CONFIRMED: official v0.0.16 parser rejects unescaped backslashes in original command')
        else:
            if result.returncode != 0 or not profile.is_file():
                raise AssertionError(result.stdout)
            print('PASS: official v0.0.16 offline init accepts escaped command with backslashes, spaces and apostrophe')
print('No doctor, run, network connection, real authentication or Windows execution was tested.')
