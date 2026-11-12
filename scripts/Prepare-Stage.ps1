# Runs in a separate PowerShell process to release every child process and
# virtualenv handle BEFORE the parent promotes the staged directory.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Stage)
$ErrorActionPreference = 'Stop'
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$Parent = [IO.Path]::GetFullPath((Split-Path -Parent $Stage))
if ($Parent.TrimEnd('\') -ine [IO.Path]::GetFullPath($State).TrimEnd('\') -or
    (Split-Path -Leaf $Stage) -notmatch '^app\.stage\.[a-f0-9]{32}$') {
    throw 'Stage must be an installer-created directory under HarmonyRemoteMCP'
}
$Python = Join-Path $Stage '.venv\Scripts\python.exe'
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv (Join-Path $Stage '.venv') }
elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv (Join-Path $Stage '.venv') }
else { throw 'Python 3.11+ required' }
if ($LASTEXITCODE -ne 0) { throw 'Python virtualenv creation failed' }
& $Python (Join-Path $Stage 'install_check.py') --version-only
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed' }
& $Python -m pip install --disable-pip-version-check -r (Join-Path $Stage 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependencies failed' }
$OldConfig = $env:HARMONY_MCP_CONFIG
try {
    $env:HARMONY_MCP_CONFIG = Join-Path $Stage 'config.json'
    Push-Location -LiteralPath $Stage
    try {
        & $Python (Join-Path $Stage 'install_check.py')
        if ($LASTEXITCODE -ne 0) { throw 'Policy/import validation failed' }
        & $Python -m unittest discover -s (Join-Path $Stage 'tests') -q
        if ($LASTEXITCODE -ne 0) { throw 'Regression suite failed' }
        & $Python (Join-Path $Stage 'smoke_test.py')
        if ($LASTEXITCODE -ne 0) { throw 'MCP staging stdio handshake failed' }
        & (Get-Process -Id $PID).Path -NoLogo -NoProfile -File (Join-Path $Stage 'tests\Test-DPAPI-RoundTrip.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Staging DPAPI regression test failed' }
    } finally { Pop-Location }
} finally { $env:HARMONY_MCP_CONFIG = $OldConfig }
Write-Host 'PREPARE_STAGE_PASS'
