[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Launcher = Join-Path $Root 'scripts\Start-Tunnel.ps1'
if (-not (Test-Path (Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\tunnel-key.dpapi'))) {
    throw 'Initialize the tunnel before enabling startup'
}
& (Join-Path $PSScriptRoot 'Test-Local.ps1')
& (Join-Path $PSScriptRoot 'Test-Tunnel.ps1')
# A process-scoped execution-policy option avoids changing Windows policy.
# The archive must be acquired from a trusted source; execution policy is not a sandbox.
# An interactive user startup shortcut is needed for screen/input access; no elevated Windows service.
$Startup = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $Startup 'Harmony Remote MCP.lnk'
if (Test-Path -LiteralPath $ShortcutPath -PathType Leaf) {
    # Never overwrite a valid shortcut on re-entry, or silently replace an unexpected one.
    & (Join-Path $PSScriptRoot 'Test-Startup.ps1')
    Write-Host 'Existing verified auto-start shortcut preserved (idempotent).' -ForegroundColor Green
    return
}
if (Test-Path -LiteralPath $ShortcutPath) {
    $BackupFolder = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\startup-backups'
    New-Item -ItemType Directory -Path $BackupFolder -Force | Out-Null
    Copy-Item -LiteralPath $ShortcutPath -Destination (Join-Path $BackupFolder ([guid]::NewGuid().ToString('N') + '.lnk'))
}
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
. (Join-Path $PSScriptRoot 'Resolve-PowerShell.ps1')
$Shortcut.TargetPath = Resolve-UniversalPowerShell -NoDownload
$Shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $Launcher + '"'
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = 'User-authorized private MCP tunnel for Harmony Remote MCP'
$Shortcut.Save()
& (Join-Path $PSScriptRoot 'Test-Startup.ps1')
Write-Host "Startup shortcut installed: $ShortcutPath" -ForegroundColor Green
Write-Host 'The tunnel starts after the next user logon. Run Start-Tunnel.ps1 now for this session.'
