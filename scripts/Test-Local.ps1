[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Run Install.ps1 first' }
& $Python (Join-Path $Root 'smoke_test.py')
if ($LASTEXITCODE -ne 0) { throw 'MCP local handshake failed' }
