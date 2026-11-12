# Minimal machine-independent entry point. Never edits the system-wide PowerShell installation.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Resolve-PowerShell.ps1')
$ModernShell = Resolve-UniversalPowerShell
Write-Host ('Universal Remote: PowerShell runtime: ' + $ModernShell) -ForegroundColor Cyan
& $ModernShell -NoLogo -NoProfile -File (Join-Path $PSScriptRoot 'Bootstrap.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
