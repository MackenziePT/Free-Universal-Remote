# Private, single-instance tunnel supervisor; no inbound listener is created here.
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'PowerShell-Security.ps1')
. (Join-Path $PSScriptRoot 'Secret-Storage.ps1')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Tunnel-Identity.ps1')
. (Join-Path $PSScriptRoot 'Tunnel-Logging.ps1')
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Client = Join-Path $Root 'bin\tunnel-client.exe'
$ProfileFile = Join-Path $env:USERPROFILE '.config\tunnel-client\harmony-remote.yaml'
if (-not (Test-Path -LiteralPath $ProfileFile -PathType Leaf)) { throw 'Configured private tunnel profile missing' }
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$Secret = Join-Path $State 'tunnel-key.dpapi'
$Logs = Join-Path $State 'logs'
$PidFile = Join-Path $State 'tunnel-launcher.pid'
if (-not (Test-Path -LiteralPath $Client -PathType Leaf)) { throw 'tunnel-client.exe missing' }
if (-not (Test-Path -LiteralPath $Secret -PathType Leaf)) { throw 'Run Initialize-Tunnel.ps1 first' }
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

$Mutex = [System.Threading.Mutex]::new($false, 'Local\HarmonyRemoteMCP')
$Locked = $false
try {
    try { $Locked = $Mutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] {
        # Previous launcher crashed; ownership is transferred to this thread.
        $Locked = $true
    }
    if (-not $Locked) { throw 'Harmony tunnel is already running for this user' }

    # Keep the control-plane key in memory only for the lifetime of this process.
    # The MCP child launcher (launch_server.py) strips it from the MCP server.
    $Secure = Read-UniversalStoredSecret -Path $Secret
    $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { $env:CONTROL_PLANE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR) }

    Save-TunnelIdentity -Path $PidFile -Launcher $PSCommandPath -ProcessId $PID
    $LogFile = Join-Path $Logs 'tunnel.log'
    $RetrySeconds = 5
    while ($true) {
        if ((Test-Path -LiteralPath $LogFile) -and (Get-Item -LiteralPath $LogFile).Length -ge 10485760) {
            Move-Item -LiteralPath $LogFile -Destination (Join-Path $Logs 'tunnel.previous.log') -Force
        }
        $Started = Get-Date
        $ExitCode = -1
        try {
            & $Client run --profile-file $ProfileFile 2>&1 | ForEach-Object {
                Write-TunnelLog -Path $LogFile -Message ([string]$_)
            }
            $ExitCode = $LASTEXITCODE
        } catch {
            Write-TunnelLog -Path $LogFile -Message ('Tunnel launch exception type={0} HResult={1}' -f $_.Exception.GetType().Name, $_.Exception.HResult)
        }
        $Lifetime = ((Get-Date) - $Started).TotalSeconds
        if ($Lifetime -ge 120) { $RetrySeconds = 5 }
        $RetrySeconds = [Math]::Min(300, [int]($RetrySeconds * 2))
        Write-TunnelLog -Path $LogFile -Message ('Tunnel exited with code {0} at {1:u}. Retry after {2} s.' -f $ExitCode, (Get-Date), $RetrySeconds)
        Start-Sleep -Seconds $RetrySeconds
    }
} finally {
    Remove-Item Env:\CONTROL_PLANE_API_KEY -ErrorAction SilentlyContinue
    # Never leave a stale launcher status if this process shuts down normally.
    if ($Locked) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        $Mutex.ReleaseMutex()
    }
    $Mutex.Dispose()
}
