# Standalone, deterministic listener ownership regression; no network or process changes.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $Root 'scripts\Tunnel-Identity.ps1')
$script:Owner = [pscustomobject]@{ ProcessId = 4100; CreationDate = [datetime]'2026-11-10T15:00:00Z' }
$script:Client = [pscustomobject]@{ ProcessId = 4200; ParentProcessId = 4100
    Name='tunnel-client.exe'; CreationDate = [datetime]'2026-11-10T15:00:01Z' }
$script:Connections = @([pscustomobject]@{ LocalAddress='127.0.0.1'; LocalPort=8080
    RemotePort=0; OwningProcess=4200 })
function Get-NetTCPConnection {
    param([int]$LocalPort, [string]$ErrorAction)
    if ($LocalPort -ne 8080) { throw 'Unexpected port' }
    return $script:Connections
}
function Get-CimInstance {
    param([string]$ClassName, [string]$Filter)
    if ($ClassName -ne 'Win32_Process') { throw 'Unexpected CIM request' }
    if ($Filter -eq 'ProcessId=4200') { return $script:Client }
    return $null
}
function Assert-Reject($Name) {
    $Rejected=$false
    try { Assert-OwnedHealthListener -Owner $script:Owner -Port 8080 } catch { $Rejected=$true }
    if (-not $Rejected) { throw ('FAIL: ' + $Name) }
    Write-Output ('PASS: ' + $Name + ' rejected')
}
Assert-OwnedHealthListener -Owner $script:Owner -Port 8080
Write-Output 'PASS: matching loopback listener, tunnel-client process and launcher parent'
$script:Client.ParentProcessId=9000
Assert-Reject 'unrelated parent'
$script:Client.ParentProcessId=4100
$script:Client.Name='unrelated.exe'
Assert-Reject 'foreign listener executable'
$script:Client.Name='tunnel-client.exe'
$script:Connections[0].LocalAddress='0.0.0.0'
Assert-Reject 'wildcard address'
$script:Connections[0].LocalAddress='127.0.0.1'
$script:Connections[0].OwningProcess=9000
Assert-Reject 'wrong PID listener'
$script:Connections[0].OwningProcess=4200
$script:Client.CreationDate=$script:Owner.CreationDate.AddMinutes(-1)
Assert-Reject 'client predates launcher'
$script:Client.CreationDate=$script:Owner.CreationDate.AddSeconds(1)
$script:Connections=@()
Assert-Reject 'no loopback listener'
Write-Output 'LISTENER_OWNERSHIP_REGRESSION_PASS'
