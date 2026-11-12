# Check the saved local stdio tunnel profile using the official tunnel-client.
# Does not start the tunnel or prove that ChatGPT can reach it.
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'PowerShell-Security.ps1')
. (Join-Path $PSScriptRoot 'Secret-Storage.ps1')
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Client = Join-Path $Root 'bin\tunnel-client.exe'
$ProfileFile = Join-Path $env:USERPROFILE '.config\tunnel-client\harmony-remote.yaml'
if (-not (Test-Path -LiteralPath $ProfileFile -PathType Leaf)) { throw 'Configured private tunnel profile missing' }
$Secret = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\tunnel-key.dpapi'
if (-not (Test-Path -LiteralPath $Client -PathType Leaf)) { throw 'Official tunnel-client.exe not installed' }
if (-not (Test-Path -LiteralPath $Secret -PathType Leaf)) { throw 'Run Initialize-Tunnel.ps1 on this Windows account first' }
# The doctor's health listener cannot bind while our verified supervisor is alive.
# Re-entry must check ownership + current readiness instead of starting a second listener.
. (Join-Path $PSScriptRoot 'Tunnel-Identity.ps1')
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$PidFile = Join-Path $State 'tunnel-launcher.pid'
$Launcher = Join-Path $Root 'scripts\Start-Tunnel.ps1'
$LiveOwner = Get-VerifiedTunnelIdentity -Path $PidFile -Launcher $Launcher
if ($LiveOwner) {
    # A ready response is meaningful only when its listener is our own child process.
    Assert-OwnedHealthListener -Owner $LiveOwner -Port 8080
    $Ready = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/readyz' -TimeoutSec 4 -ErrorAction Stop
    if ($Ready.StatusCode -ne 200 -or $Ready.Content.Trim() -cne 'ready') {
        throw 'Verified tunnel supervisor exists but readiness is invalid; refusing doctor re-entry'
    }
    Write-Host 'Verified tunnel supervisor is running and ready; no duplicate doctor required.' -ForegroundColor Green
    return
}
try {
    # DPAPI ciphertext is bound to this Windows user, not stored in source code.
    $Secure = Read-UniversalStoredSecret -Path $Secret
    $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { $env:CONTROL_PLANE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR) }
    & $Client doctor --profile-file $ProfileFile --explain
    if ($LASTEXITCODE -ne 0) { throw 'Tunnel doctor failed; review messages above locally and do not enable autostart' }
    Write-Host 'Tunnel doctor passed. A live ChatGPT MCP tool call is still required.' -ForegroundColor Green
} finally {
    Remove-Item Env:\CONTROL_PLANE_API_KEY -ErrorAction SilentlyContinue
}
