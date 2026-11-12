"""Exercise the real rollback script in disposable directories with a fake handshake.

Linux-only fixture. No Windows installation, DPAPI or real MCP is involved here.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--pwsh', required=True)
args = parser.parse_args()
if os.name == 'nt':
    parser.error('This simulation uses a Unix fake executable.')
root = Path(__file__).resolve().parents[1]
for exit_code in (0, 1):
    with tempfile.TemporaryDirectory(prefix='universal-rollback-') as directory:
        base = Path(directory)
        state = base/'HarmonyRemoteMCP'
        app = state/'app'
        app.mkdir(parents=True)
        (app/'marker.txt').write_text('current')
        backup = state/('app.previous.'+'a'*32)
        exe = backup/'.venv/Scripts/python.exe'
        exe.parent.mkdir(parents=True)
        exe.write_text('#!/bin/sh\nexit '+str(exit_code)+'\n')
        exe.chmod(0o700)
        (backup/'config.json').write_text('{}')
        (backup/'smoke_test.py').write_text('# simulated for rollback test only')
        (backup/'marker.txt').write_text('backup')
        result = subprocess.run([args.pwsh, '-NoProfile', '-NonInteractive', '-File',
            str(root/'scripts/Restore-Previous.ps1'), '-BackupPath',str(backup)],
            env={**os.environ,'LOCALAPPDATA':str(base)}, capture_output=True, text=True, timeout=20)
        expected = 'backup' if exit_code == 0 else 'current'
        if (app/'marker.txt').read_text() != expected or (backup/'marker.txt').read_text() != 'backup':
            raise AssertionError('Rollback did not preserve expected application/backup state')
        if exit_code == 0:
            if result.returncode != 0:
                raise AssertionError(result.stderr)
            retained = list(state.glob('app.before-rollback.*/marker.txt'))
            if len(retained) != 1 or retained[0].read_text() != 'current':
                raise AssertionError('Replaced application not retained')
            print('PASS: rollback promotes selected backup and retains backup plus replaced app (handshake simulated)')
        else:
            if result.returncode == 0 or 'Restored app did not pass MCP handshake' not in result.stderr:
                raise AssertionError('Expected failed handshake was not observed')
            failed = list(state.glob('app.restore.*.failed/marker.txt'))
            if len(failed) != 1 or failed[0].read_text() != 'backup':
                raise AssertionError('Failed candidate not retained')
            print('PASS: failed handshake restores current app and retains failed candidate (handshake simulated)')
