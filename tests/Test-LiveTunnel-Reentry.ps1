# Windows-only live integration check. Never starts or stops a tunnel, changes profile or reads credentials.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $Root 'scripts\Tunnel-Identity.ps1')
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$PidFile = Join-Path $State 'tunnel-launcher.pid'
$Launcher = Join-Path $Root 'scripts\Start-Tunnel.ps1'
$Verified = Get-VerifiedTunnelIdentity -Path $PidFile -Launcher $Launcher
if (-not $Verified) { throw 'Precondition: a verified live tunnel is required.' }
$Ready = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/readyz' -TimeoutSec 4 -ErrorAction Stop
if ($Ready.StatusCode -ne 200 -or $Ready.Content.Trim() -cne 'ready') { throw 'Precondition: tunnel is not ready.' }
Assert-OwnedHealthListener -Owner $Verified -Port 8080
& (Join-Path $Root 'scripts\Test-Tunnel.ps1')
Write-Output 'PASS: live tunnel re-entry checks verified owner and readiness without a conflicting doctor.'
