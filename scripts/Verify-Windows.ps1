# Full local acceptance without administrative privileges. No real project files modified.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Install the agent first (scripts\Install.ps1).' }
# unittest adds the test directory, but sibling application modules are found
# through the working directory. A desktop/downloads/System32 caller must not
# decide which modules are imported. Restore its location even after a failure.
Push-Location -LiteralPath $Root
try {
    & $Python -m unittest discover -s (Join-Path $Root 'tests') -v
    if ($LASTEXITCODE -ne 0) { throw 'Regression suite failed.' }
    Write-Host '1/3: Checking official MCP stdio handshake.' -ForegroundColor Cyan
    & $Python (Join-Path $Root 'smoke_test.py')
    if ($LASTEXITCODE -ne 0) { throw 'MCP stdio handshake failed' }
    Write-Host '2/3: Checking PowerShell, NTFS and disposable file operations.' -ForegroundColor Cyan
    & $Python (Join-Path $Root 'windows_verify.py')
    if ($LASTEXITCODE -ne 0) { throw 'Windows acceptance test failed. Do not enable autostart.' }
    Write-Host '3/3: Checking legacy and modern Windows DPAPI ciphertext compatibility.' -ForegroundColor Cyan
    & (Get-Process -Id $PID).Path -NoLogo -NoProfile -File (Join-Path $Root 'tests\Test-DPAPI-RoundTrip.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'DPAPI round-trip regression failed' }
    Write-Host 'LOCAL acceptance passed. ChatGPT remote tool call still requires testing.' -ForegroundColor Green
} finally {
    Pop-Location
}
