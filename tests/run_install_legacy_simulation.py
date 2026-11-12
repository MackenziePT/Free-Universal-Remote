"""Run the real installer in PowerShell Legacy argument mode, in disposable paths.

Linux fixture: venv creation, pip and GUI imports are simulated. The installer,
Python execution, unit suite, MCP handshakes, staging and backup are real.
No Windows/NTFS certification, network access or installed application is involved.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--pwsh', required=True)
parser.add_argument('--expected-failure', action='store_true')
args = parser.parse_args()
if os.name == 'nt':
    parser.error('This simulation uses a Unix executable wrapper.')
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="universal install O'Neil ") as directory:
    base = Path(directory)
    source = base/'release with spaces'
    shutil.copytree(root, source, ignore=shutil.ignore_patterns('__pycache__', 'previous-release', 'evidence'))
    state = base/'local app data'/'HarmonyRemoteMCP'
    app = state/'app'
    app.mkdir(parents=True)
    (app/'marker.txt').write_text('original installation')
    allowed = base/'allowed'
    allowed.mkdir()
    (app/'config.json').write_text(json.dumps({'allowed_roots': [str(allowed)],
        'backup_root': str(base/'file backups'), 'grants_path': str(base/'grants.json')}))
    stubs = base/'gui stubs'
    stubs.mkdir()
    for name in ('mss', 'PIL', 'pyautogui'):
        (stubs/(name+'.py')).write_text('# Empty GUI import fixture; no GUI verification.\n')
    template = base/'venv template'
    exe = template/'Scripts/python.exe'
    exe.parent.mkdir(parents=True)
    exe.write_text('#!'+sys.executable+'\nimport os,sys\n'
        'if sys.argv[1:3]==["-m","pip"]:\n'
        ' print("SIMULATED: dependency installation (preinstalled test environment)")\n'
        ' sys.exit(0)\n'
        'os.execv('+repr(sys.executable)+', ['+repr(sys.executable)+', *sys.argv[1:]])\n')
    exe.chmod(0o700)
    driver = base/'test driver.ps1'
    driver.write_text("""param([string]$Source, [string]$Template)
$ErrorActionPreference = 'Stop'
$PSNativeCommandArgumentPassing = 'Legacy'
$global:UniversalTestVenvTemplate = $Template
function py {
    $Target = $args[-1]
    Copy-Item -LiteralPath $global:UniversalTestVenvTemplate -Destination $Target -Recurse
    $global:LASTEXITCODE = 0
}
& (Join-Path $Source 'scripts/Install.ps1')
""")
    result = subprocess.run([args.pwsh, '-NoProfile', '-NonInteractive', '-File', str(driver),
        '-Source', str(source), '-Template', str(template)],
        env={**os.environ, 'LOCALAPPDATA': str(state.parent), 'PYTHONPATH': str(stubs)},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
    if args.expected_failure:
        if result.returncode == 0 or 'SyntaxError' not in result.stdout:
            raise AssertionError(result.stdout)
        if (app/'marker.txt').read_text() != 'original installation' or list(state.glob('app.previous.*')):
            raise AssertionError('Failed staging modified the existing app')
        print(result.stdout)
        print('RED CONFIRMED: Legacy quote loss fails before promotion; original app retained')
    else:
        if result.returncode != 0:
            raise AssertionError(result.stdout)
        backups = list(state.glob('app.previous.*'))
        if len(backups) != 1 or (backups[0]/'marker.txt').read_text() != 'original installation':
            raise AssertionError('Prior installation not backed up')
        if list(state.glob('app.stage.*')) or not (app/'server.py').is_file():
            raise AssertionError('Stage promotion incomplete')
        if (app/'config.json').read_bytes() != (backups[0]/'config.json').read_bytes():
            raise AssertionError('Existing configuration was not preserved')
        print(result.stdout)
        print('PASS: installer in Legacy mode, paths with spaces/apostrophe, real suite and MCP handshakes, backup/config preserved')
