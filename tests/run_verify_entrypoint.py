"""Exercise the real PowerShell verification entry point from an unrelated cwd.

The verifier, Python interpreter and unittest discovery are real. Tiny fixture
modules replace MCP/Win32 checks so this harness also runs on Linux. It proves
import resolution, fail-closed ordering and caller-location restoration, not
native Windows acceptance or a remote tunnel connection.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pwsh', required=True)
    parser.add_argument('--expected-failure', action='store_true')
    parser.add_argument('--verifier', type=Path, help='Explicit historical verifier for a red replay')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = [('none', False)] if args.expected_failure else [
        ('none', False), ('none', True), ('regression', True), ('smoke', True), ('windows', True)]
    for failure, literal_path in cases:
        with tempfile.TemporaryDirectory(prefix="universal verifier O'Neil ") as temp:
            base = Path(temp)
            app = base/('app with spaces [literal]' if literal_path else 'app with spaces')
            (app/'scripts').mkdir(parents=True)
            (app/'tests').mkdir()
            foreign = base/'unrelated caller'
            foreign.mkdir()
            shutil.copy2(args.verifier or root/'scripts/Verify-Windows.ps1', app/'scripts/Verify-Windows.ps1')
            if os.name == 'nt':
                venv.EnvBuilder(with_pip=False).create(app/'.venv')
            else:
                (app/'.venv/Scripts').mkdir(parents=True)
                (app/'.venv/Scripts/python.exe').symlink_to(sys.executable)
            (app/'remote_core.py').write_text('EXPECTED = "installed module"\n')
            (app/'tests/test_imports.py').write_text('''import os, unittest
from pathlib import Path
from remote_core import EXPECTED
class VerifyImports(unittest.TestCase):
    def test_imports(self):
        self.assertEqual(EXPECTED, "installed module")
        with Path(os.environ["UNIVERSAL_VERIFY_TRACE"]).open("a") as f:
            f.write("regression\\n")
        self.assertNotEqual(os.environ["UNIVERSAL_VERIFY_FAIL"], "regression")
''')
            for filename, label in [('smoke_test.py', 'smoke'), ('windows_verify.py', 'windows')]:
                (app/filename).write_text(
                    'import os, sys\nfrom pathlib import Path\n'
                    'with Path(os.environ["UNIVERSAL_VERIFY_TRACE"]).open("a") as f:\n'
                    f'    f.write({label!r}+"\\n")\n'
                    f'sys.exit(17 if os.environ["UNIVERSAL_VERIFY_FAIL"] == {label!r} else 0)\n')
            driver = base/'driver.ps1'
            driver.write_text(r'''param([string]$App, [string]$LocationReport)
$ErrorActionPreference = 'Stop'
$PSNativeCommandArgumentPassing = 'Legacy'
$Before = (Get-Location).Path
$Failed = $false
try { & (Join-Path $App 'scripts/Verify-Windows.ps1') }
catch { $Failed = $true; Write-Output $_.Exception.Message }
finally {
    [IO.File]::WriteAllText($LocationReport, (@{before=$Before; after=(Get-Location).Path} | ConvertTo-Json))
}
if ($Failed) { exit 31 }
''')
            trace = base/'trace.txt'
            locations = base/'locations.json'
            env = {**os.environ, 'UNIVERSAL_VERIFY_TRACE': str(trace), 'UNIVERSAL_VERIFY_FAIL': failure}
            env.pop('PYTHONPATH', None)
            result = subprocess.run([args.pwsh, '-NoLogo', '-NoProfile', '-NonInteractive',
                                     '-File', str(driver), '-App', str(app),
                                     '-LocationReport', str(locations)], cwd=foreign, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=30)
            if args.expected_failure:
                assert result.returncode == 31, result.stdout
                assert "No module named 'remote_core'" in result.stdout, result.stdout
                assert not trace.exists(), 'A failed regression suite reached a later check'
                print('RED CONFIRMED: real Verify-Windows.ps1 cannot import app modules from unrelated cwd')
                continue
            expected = ['regression', 'smoke', 'windows']
            if failure != 'none':
                expected = expected[:expected.index(failure)+1]
            assert result.returncode == (0 if failure == 'none' else 31), result.stdout
            assert trace.read_text().splitlines() == expected, result.stdout
            observed = json.loads(locations.read_text())
            assert observed['before'] == observed['after'] == str(foreign), observed
            print(f'PASS: {failure}, brackets={literal_path}; correct app imports, fail-closed order and caller cwd restored')


if __name__ == '__main__':
    main()
