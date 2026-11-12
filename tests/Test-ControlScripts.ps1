# Portable behavioral test: CIM/taskkill are simulated; no real process is killed.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Sandbox = Join-Path ([IO.Path]::GetTempPath()) ('universal-control-test-' + [guid]::NewGuid().ToString('N'))
$PreviousLocalAppData = $env:LOCALAPPDATA
$env:LOCALAPPDATA = $Sandbox
$State = Join-Path $Sandbox 'HarmonyRemoteMCP'
New-Item -ItemType Directory -Path $State -Force | Out-Null
$PidFile = Join-Path $State 'tunnel-launcher.pid'
$global:UniversalTestKilled = 0
function Get-CimInstance { param($ClassName, $Filter); return $global:UniversalTestProcess }
function taskkill.exe { $global:UniversalTestKilled++; $global:LASTEXITCODE = 0 }
try {
    # A stale RC3 PID can now identify an unrelated script with the same filename.
    $global:UniversalTestProcess = [pscustomobject]@{ ProcessId=123; Name='pwsh.exe';
        CommandLine='pwsh -File C:\Unrelated\Start-Tunnel.ps1'; CreationDate=[datetime]::UtcNow }
    [IO.File]::WriteAllText($PidFile, '123')
    $Denied = $false
    try { & (Join-Path $Root 'scripts/Stop-Tunnel.ps1') } catch { $Denied = $true; Write-Output ('Observed refusal: ' + $_.Exception.Message) }
    if (-not $Denied -or $global:UniversalTestKilled -ne 0) { throw 'FAIL: stale PID terminated an unrelated launcher' }
    Write-Output 'PASS: stale/legacy PID is refused without taskkill'
    . (Join-Path $Root 'scripts/Tunnel-Identity.ps1')
    $Launcher = Join-Path $Root 'scripts/Start-Tunnel.ps1'
    $StartDate = [datetime]::UtcNow
    $global:UniversalTestProcess = [pscustomobject]@{ ProcessId=123; Name='pwsh.exe';
        CommandLine=('pwsh -File "' + $Launcher + '"'); CreationDate=$StartDate }
    Save-TunnelIdentity -Path $PidFile -Launcher $Launcher -ProcessId 123
    $Verified = Get-VerifiedTunnelIdentity -Path $PidFile -Launcher $Launcher
    if ($Verified.ProcessId -ne 123) { throw 'FAIL: matching process identity rejected' }
    Write-Output 'PASS: matching PID, timestamp, path and command hash accepted'
    $global:UniversalTestProcess.CreationDate = $StartDate.AddSeconds(5)
    $Denied = $false
    try { & (Join-Path $Root 'scripts/Stop-Tunnel.ps1') } catch { $Denied = $true }
    if (-not $Denied -or $global:UniversalTestKilled -ne 0) { throw 'FAIL: reused PID was terminated' }
    Write-Output 'PASS: reused PID refused'
    $global:UniversalTestProcess.CreationDate = $StartDate
    & (Join-Path $Root 'scripts/Stop-Tunnel.ps1')
    if ($global:UniversalTestKilled -ne 1 -or (Test-Path -LiteralPath $PidFile)) { throw 'FAIL: verified stop did not clean identity' }
    Write-Output 'PASS: verified stop invokes only the recorded process tree and clears identity'
} finally {
    $env:LOCALAPPDATA = $PreviousLocalAppData
    Remove-Item -LiteralPath $Sandbox -Recurse -Force
}
