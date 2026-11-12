# Stop ONLY the recorded Harmony launcher and its child tunnel process.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Tunnel-Identity.ps1')
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$PidFile = Join-Path $State 'tunnel-launcher.pid'
if (-not (Test-Path -LiteralPath $PidFile)) { Write-Host 'No Harmony launcher PID recorded'; return }
$Details = Get-VerifiedTunnelIdentity -Path $PidFile -Launcher (Join-Path $PSScriptRoot 'Start-Tunnel.ps1')
if (-not $Details) {
    Write-Host 'No matching launcher is running; no process terminated.'
    return
}
$LaunchPid = $Details.ProcessId
& taskkill.exe /PID $LaunchPid /T /F | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not terminate Harmony launcher' }
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Write-Host 'Harmony MCP tunnel processes stopped.' -ForegroundColor Green
