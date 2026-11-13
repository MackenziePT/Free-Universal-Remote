# Migrate only this user's previously authenticated OpenAI private MCP tunnel.
# This script never reveals, changes, creates or shares a tunnel API credential.
# The old profile is backed up and can be restored with -Rollback.
[CmdletBinding()]
param([switch]$Rollback)
$ErrorActionPreference='Stop'

$OldRoot=Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\app'
$Launcher=Join-Path $OldRoot 'scripts\Start-Tunnel.ps1'
$Stopper=Join-Path $OldRoot 'scripts\Stop-Tunnel.ps1'
$Profile=Join-Path $env:USERPROFILE '.config\tunnel-client\harmony-remote.yaml'
$Backup=$Profile+'.pre-rc51-preserved'
$Bridge=Join-Path $env:LOCALAPPDATA 'Programs\UniversalRemote\Bridge\UniversalRemoteBridge-Preview.exe'
$Key=Join-Path $env:LOCALAPPDATA 'UniversalRemote\security\private-tunnel-identity.dpapi'
$Identity=Join-Path $env:LOCALAPPDATA 'UniversalRemote\security\private-tunnel-identity.json'
$Shell='C:\Program Files\PowerShell\7\pwsh.exe'

function Stop-OnlyOwnedTunnel {
    if (-not (Test-Path -LiteralPath $Stopper)) { throw 'Original supervisor is missing' }
    & $Stopper
    if ($LASTEXITCODE -notin @(0,$null)) { throw 'Original tunnel supervisor refused to stop' }
    Start-Sleep -Milliseconds 1000
}
function Start-OriginalSupervisor {
    $quoted='"'+$Launcher+'"'
    $p=Start-Process -FilePath $Shell -ArgumentList ('-NoLogo -NoProfile -ExecutionPolicy Bypass -File '+$quoted) -WindowStyle Minimized -PassThru
    Start-Sleep -Seconds 3
    $p.Refresh()
    if ($p.HasExited) { throw 'Private tunnel supervisor failed to start' }
    for($i=0;$i -lt 10;$i++) {
        try {
            $ready=Invoke-RestMethod -Uri 'http://127.0.0.1:8080/readyz' -TimeoutSec 2 -ErrorAction Stop
            if ($ready -eq 'ready') {
                Write-Output 'PRIVATE_TUNNEL_LOCAL_READY'
                return
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    throw 'Private tunnel did not reach locally ready state'
}
function Restore-OriginalProfile {
    if (-not (Test-Path -LiteralPath $Backup)) { throw 'Preserved original tunnel profile is missing' }
    Stop-OnlyOwnedTunnel
    Copy-Item -LiteralPath $Backup -Destination $Profile -Force
    Start-OriginalSupervisor
    Write-Output 'RC50_PROFILE_RESTORED'
}
if ($Rollback) {
    Restore-OriginalProfile
    exit 0
}
foreach ($f in @($Profile,$Launcher,$Stopper,$Shell,$Bridge,$Key,$Identity)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) {
        throw ('Required private bridge component is missing: '+[IO.Path]::GetFileName($f))
    }
}
$health=Start-Process -FilePath $Bridge -ArgumentList '--health-probe' -NoNewWindow -Wait -PassThru
if ($health.ExitCode -ne 0) { throw 'Installed RC5.1 bridge failed its runtime health probe' }
$OldText=[IO.File]::ReadAllText($Profile)
if ($OldText -notmatch 'CONTROL_PLANE_API_KEY' -or $OldText -notmatch 'channel:\s*main') {
    throw 'Existing private tunnel profile is not the expected owner-managed channel'
}
$lines=[regex]::Matches($OldText, '(?m)^[ \t]*command:[^\r\n]*$')
if ($lines.Count -ne 1) { throw 'Expected exactly one private MCP command' }
if ($OldText.Contains('UniversalRemoteBridge-Preview.exe')) {
    Write-Output 'RC51_BRIDGE_ALREADY_ACTIVE_IN_PROFILE'
    exit 0
}
if (-not $OldText.Contains('launch_server.py')) {
    throw 'Unexpected existing MCP command; refusing to modify'
}
if (-not (Test-Path -LiteralPath $Backup)) {
    Copy-Item -LiteralPath $Profile -Destination $Backup -ErrorAction Stop
} else {
    $Prior=[IO.File]::ReadAllText($Backup)
    if (-not $Prior.Contains('launch_server.py')) {
        throw 'Preserved profile backup is not the original legacy profile'
    }
}
# Windows path encoded as YAML double quoted scalar containing a single quoted
# command path. No credentials or tunnel IDs are modified.
$QuotedCommand="'"+($Bridge.Replace('\','\\'))+"'"
$Replacement=($lines[0].Value -replace 'command:.*$', 'command: "'+$QuotedCommand+'"')
$Next=$OldText.Substring(0,$lines[0].Index)+$Replacement+$OldText.Substring($lines[0].Index+$lines[0].Length)
if ($Next -eq $OldText) { throw 'Private profile migration produced no change' }
try {
    Stop-OnlyOwnedTunnel
    [IO.File]::WriteAllText($Profile,$Next,[Text.UTF8Encoding]::new($false))
    Start-OriginalSupervisor
    Write-Output 'RC51_PRIVATE_TUNNEL_MIGRATED_LOCAL_READY'
} catch {
    Write-Output ('RC51_SWITCH_FAILED_AND_ROLLBACK_REQUESTED='+$_.Exception.GetType().Name)
    try {
        Stop-OnlyOwnedTunnel
        Copy-Item -LiteralPath $Backup -Destination $Profile -Force
        Start-OriginalSupervisor
        Write-Output 'RC50_PROFILE_RESTORED_AFTER_FAILURE'
    } catch {
        Write-Output 'WARNING_MANUAL_TUNNEL_RECOVERY_REQUIRED'
    }
    throw
}
