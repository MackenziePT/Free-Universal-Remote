"""Run real PowerShell -> Python -> native argv with a synthetic pasted key.

The GUI reader, DPAPI and external tunnel service are simulated. A disabled
console reader proves setup no longer depends on Read-Host. No real credential.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--pwsh', required=True)
args = parser.parse_args()
if os.name == 'nt':
    parser.error('This simulation uses a Unix recording client.')
root = Path(__file__).resolve().parents[1]
synthetic = 'sk-SYNTHETIC-NOT-A-CREDENTIAL_' + ('AaZz0123456789-_' * 30)
for failure in ['none', 'init', 'doctor', 'cancel', 'invalid']:
    for existing in [False, True]:
        with tempfile.TemporaryDirectory(prefix="universal tunnel O'Neil [test] ") as directory:
            base = Path(directory)
            fixture = base/'app with spaces'
            (fixture/'scripts').mkdir(parents=True)
            shutil.copy2(root/'scripts/Initialize-Tunnel.ps1', fixture/'scripts/Initialize-Tunnel.ps1')
            shutil.copy2(root/'scripts/PowerShell-Security.ps1', fixture/'scripts/PowerShell-Security.ps1')
            shutil.copy2(root/'initialize_tunnel.py', fixture/'initialize_tunnel.py')
            python = fixture/'.venv/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.symlink_to(sys.executable)
            (fixture/'launch_server.py').write_text('# not executed by this simulated client\n')
            client = fixture/'bin/tunnel-client.exe'
            client.parent.mkdir()
            capture = base/'argv.json'
            client.write_text('#!'+sys.executable+'\n'
                'import hashlib,json,os,sys\nfrom pathlib import Path\n'
                'key=os.environ.get("CONTROL_PLANE_API_KEY", "")\n'
                'if hashlib.sha256(key.encode()).hexdigest()!=os.environ["UNIVERSAL_EXPECTED_KEY_DIGEST"]: sys.exit(32)\n'
                'p=Path(os.environ["UNIVERSAL_INIT_CAPTURE"])\n'
                'calls=json.loads(p.read_text()) if p.exists() else []\n'
                'calls.append(sys.argv[1:]); p.write_text(json.dumps(calls))\n'
                'sys.exit(19 if sys.argv[1]==os.environ["UNIVERSAL_INIT_FAIL"] else 0)\n')
            client.chmod(0o700)
            driver = base/'driver.ps1'
            driver.write_text(r"""param([string]$Fixture)
$ErrorActionPreference = 'Stop'
$PSNativeCommandArgumentPassing = 'Legacy'
. (Join-Path $Fixture 'scripts/Initialize-Tunnel.ps1')
function Read-Host { throw 'LEGACY_CONSOLE_INPUT_UNAVAILABLE' }
function Read-UniversalTunnelKey {
    if ($env:UNIVERSAL_INIT_FAIL -eq 'cancel') { throw [OperationCanceledException]::new('Synthetic cancellation') }
    if ($env:UNIVERSAL_INIT_FAIL -eq 'invalid') { return ConvertTo-UniversalTunnelKey ('tunnel_' + ('a' * 32)) }
    return ConvertTo-UniversalTunnelKey (" `r`n" + 'sk-SYNTHETIC-NOT-A-CREDENTIAL_' + ('AaZz0123456789-_' * 30) + "`r`n ")
}
function ConvertFrom-SecureString { process { 'simulated-dpapi-ciphertext' } }
try {
    Invoke-UniversalTunnelInitialization -TunnelId ('tunnel_' + ('a' * 32))
} finally {
    if (Test-Path Env:\CONTROL_PLANE_API_KEY) { throw 'Runtime key not cleared' }
}
""")
            state = base/'state'
            secret = state/'HarmonyRemoteMCP/tunnel-key.dpapi'
            if existing:
                secret.parent.mkdir(parents=True)
                secret.write_text('synthetic-old-ciphertext')
            result = subprocess.run([args.pwsh, '-NoProfile', '-NonInteractive', '-File', str(driver),
                '-Fixture', str(fixture)], env={**os.environ, 'LOCALAPPDATA': str(state),
                'UNIVERSAL_INIT_CAPTURE': str(capture), 'UNIVERSAL_INIT_FAIL': failure,
                'UNIVERSAL_EXPECTED_KEY_DIGEST': hashlib.sha256(synthetic.encode()).hexdigest()},
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15)
            if synthetic in result.stdout or 'Runtime key not cleared' in result.stdout:
                raise AssertionError('Credential leakage or runtime environment not cleared')
            if 'LEGACY_CONSOLE_INPUT_UNAVAILABLE' in result.stdout:
                raise AssertionError('Still depends on the console key input')
            calls = json.loads(capture.read_text()) if capture.exists() else []
            if failure in ['cancel', 'invalid']:
                assert calls == [], 'Cancelled or invalid input must not launch the client'
            else:
                expected_calls = ['init'] if failure == 'init' else ['init', 'doctor']
                assert [call[0] for call in calls] == expected_calls, result.stdout
                command = calls[0][calls[0].index('--mcp-command')+1]
                assert shlex.split(command) == [str(python), str(fixture/'launch_server.py')]
                assert all(synthetic not in arg for call in calls for arg in call)
            if failure == 'none':
                assert result.returncode == 0 and secret.read_text().strip() == 'simulated-dpapi-ciphertext', result.stdout
            else:
                assert result.returncode != 0, 'Expected failure/cancel'
                assert secret.exists() == existing, 'Failed setup created or removed a credential file'
                if existing:
                    assert secret.read_text() == 'synthetic-old-ciphertext', 'Failed setup replaced existing credential'
            print(f'PASS: {failure}, previous credential={existing}; exact value/argv, no console reader, cleanup and persistence gates')
print('PASS: 10 initialization scenarios; GUI, DPAPI and external service simulated')
