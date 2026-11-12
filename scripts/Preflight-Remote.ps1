# Non-invasive availability check. Never reads/decrypts the API key.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$Client = Join-Path $Root 'bin\tunnel-client.exe'
$Config = Join-Path $Root 'config.json'
$KeyFile = Join-Path $State 'tunnel-key.dpapi'
$ReportFile = Join-Path $State 'bootstrap-status.json'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Report = $null
if (Test-Path -LiteralPath $ReportFile -PathType Leaf) {
    try { $Report = Get-Content -LiteralPath $ReportFile -Raw | ConvertFrom-Json }
    catch { Write-Warning 'Bootstrap status JSON cannot be parsed.' }
}
$Configured = $null
if (Test-Path -LiteralPath $Config -PathType Leaf) {
    try {
        $Policy = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
        $Configured = [ordered]@{
            writes = ($Policy.enable_writes -eq $true)
            shell  = ($Policy.enable_shell -eq $true)
            screen = ($Policy.enable_screen -eq $true)
            input  = ($Policy.enable_input -eq $true)
        }
    } catch { Write-Warning 'Configuration JSON cannot be parsed.' }
}
$TunnelProcesses = @(Get-Process -Name 'tunnel-client' -ErrorAction SilentlyContinue)
[pscustomobject][ordered]@{
    AppPresent = (Test-Path -LiteralPath $Config -PathType Leaf)
    PythonVenvPresent = (Test-Path -LiteralPath $Python -PathType Leaf)
    TunnelClientPresent = (Test-Path -LiteralPath $Client -PathType Leaf)
    TunnelClientProcesses = $TunnelProcesses.Count
    LocalKeyFilePresent = (Test-Path -LiteralPath $KeyFile -PathType Leaf)
    PreviousLocalAcceptance = if ($Report) { $Report.local_mcp_verified } else { $null }
    PreviousRemoteAcceptance = if ($Report) { $Report.remote_mcp_verified } else { $null }
    SetupPhase = if ($Report) { $Report.phase } else { 'unknown' }
    ConfiguredCapabilities = $Configured
} | Format-List
Write-Host 'Only a live MCP ping from ChatGPT proves a remote connection. Nothing changed.'
