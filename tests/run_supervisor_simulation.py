"""Run isolated PowerShell supervisor behavior with a disposable fake Unix client."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--pwsh', required=True)
args = parser.parse_args()
if os.name == 'nt':
    parser.error('This harness uses a Unix fake executable; use real Windows acceptance separately.')
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='universal-supervisor-') as directory:
    base = Path(directory)
    shutil.copytree(root/'scripts', base/'app/scripts')
    binary = base/'app/bin/tunnel-client.exe'
    binary.parent.mkdir()
    binary.write_text('#!/bin/sh\nprintf "%s\\n" "$CONTROL_PLANE_API_KEY"\nexit 23\n')
    binary.chmod(0o700)
    result = subprocess.run([args.pwsh, '-NoProfile', '-NonInteractive', '-File',
        str(root/'tests/Test-SupervisorSimulation.ps1'), '-Fixture',str(base)],
        capture_output=True, text=True, timeout=20)
    print(result.stdout, end='')
    print(result.stderr, end='')
    raise SystemExit(result.returncode)
