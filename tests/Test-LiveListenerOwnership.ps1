# Real, read-only validation of the live listener's process ancestry.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$Root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $Root 'scripts\Tunnel-Identity.ps1')
$Installed=Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\app'
$PidFile=Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\tunnel-launcher.pid'
$Owner=Get-VerifiedTunnelIdentity -Path $PidFile -Launcher (Join-Path $Installed 'scripts\Start-Tunnel.ps1')
if (-not $Owner) {throw 'Live, verified tunnel supervisor is required.'}
Assert-OwnedHealthListener -Owner $Owner -Port 8080
$Ready=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/readyz' -TimeoutSec 5 -ErrorAction Stop
if ($Ready.StatusCode -ne 200 -or $Ready.Content.Trim() -cne 'ready') { throw 'Verified listener is not ready.' }
Write-Output 'PASS: live listener is loopback-only, tunnel-client.exe and direct child of verified supervisor; ready=200'
