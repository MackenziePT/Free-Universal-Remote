# Remove program and autostart without deleting user policy, backups or credentials.
[CmdletBinding(SupportsShouldProcess=$true,ConfirmImpact='High')]
param([switch]$RemoveState)
$ErrorActionPreference = 'Stop'
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$Root = Join-Path $State 'app'
$Startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'Harmony Remote MCP.lnk'
Write-Host 'Stop-Tunnel.ps1 must be used first; no running tunnel should remain.'
if ($PSCmdlet.ShouldProcess($Root, 'Remove MCP agent and autostart shortcut')) {
    if (Test-Path -LiteralPath $Startup) { Remove-Item -LiteralPath $Startup -Force }
    if (Test-Path -LiteralPath $Root) { Remove-Item -LiteralPath $Root -Force -Recurse }
    Write-Host 'Agent and startup shortcut removed.'
}
if ($RemoveState -and $PSCmdlet.ShouldProcess($State, 'Delete ALL secrets, policies, logs, backups and older versions')) {
    Remove-Item -LiteralPath $State -Force -Recurse -ErrorAction Stop
    Write-Host 'State data removed.'
} else {
    Write-Host "User state and backups remain at $State"
}
