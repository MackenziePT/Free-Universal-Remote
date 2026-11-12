# Windows live regression suite. Run after installation while the private tunnel is connected.
# Read-only validation except that Enable-Startup is called to prove it is idempotent.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
foreach ($Test in @('Test-LiveListenerOwnership.ps1', 'Test-LiveTunnel-Reentry.ps1', 'Test-Startup-Idempotence.ps1')) {
    Write-Host ('Live acceptance: ' + $Test) -ForegroundColor Cyan
    & (Join-Path $Root ('tests\' + $Test))
}
& (Join-Path $Root 'scripts\Status.ps1')
Write-Host 'LOCAL LIVE ACCEPTANCE PASSED. Verify ChatGPT ping independently; actual post-logon restart is not tested.' -ForegroundColor Green
