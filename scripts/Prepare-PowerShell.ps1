# Invoked by a visible, user-initiated UI action.
# Windows PowerShell 5.1 runs only the bootstrap; no system-wide installation.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Resolve-PowerShell.ps1')
$Result = Resolve-UniversalPowerShell -PreferLatest
if (-not $Result -or -not (Test-Path -LiteralPath $Result -PathType Leaf)) {
    throw 'Microsoft PowerShell runtime is not available'
}
Write-Output ('UNIVERSAL_REMOTE_PWSH_READY=' + $Result)
