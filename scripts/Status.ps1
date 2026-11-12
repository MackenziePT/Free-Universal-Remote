# Local diagnostics. Does not display or decrypt any API key.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Tunnel-Identity.ps1')
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$PidFile = Join-Path $State 'tunnel-launcher.pid'
$Binary = Join-Path $Root 'bin\tunnel-client.exe'
$Link = Join-Path ([Environment]::GetFolderPath('Startup')) 'Harmony Remote MCP.lnk'
$Running = $false
$IdentityStatus = 'not_present'
if (Test-Path -LiteralPath $PidFile) {
    try {
        $Proc = Get-VerifiedTunnelIdentity -Path $PidFile -Launcher (Join-Path $PSScriptRoot 'Start-Tunnel.ps1')
        $Running = [bool]$Proc
        $IdentityStatus = if ($Running) { 'verified' } else { 'process_absent' }
    } catch { $IdentityStatus = 'unverified_or_legacy' }
}
[pscustomobject]@{
    Root = $Root
    PythonVenv = Test-Path (Join-Path $Root '.venv\Scripts\python.exe')
    TunnelBinary = Test-Path -LiteralPath $Binary
    TunnelKeyStored = Test-Path (Join-Path $State 'tunnel-key.dpapi')
    LauncherProcessDetected = $Running
    LauncherIdentity = $IdentityStatus
    AutoStartConfigured = Test-Path -LiteralPath $Link
} | Format-List
Write-Host 'These indicators do not prove remote connectivity; use tunnel-client doctor and a ChatGPT ping.'
