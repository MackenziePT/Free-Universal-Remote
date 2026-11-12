# Inspect the real shortcut without executing it or changing logon settings.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Path = Join-Path ([Environment]::GetFolderPath('Startup')) 'Harmony Remote MCP.lnk'
if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'Startup shortcut not configured' }
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($Path)
$Expected = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $Root 'scripts\Start-Tunnel.ps1') + '"'
if ($Shortcut.Arguments -cne $Expected -or $Shortcut.WorkingDirectory -ine $Root -or
    $Shortcut.TargetPath -ine (Get-Command powershell.exe).Source) {
    throw 'Startup shortcut does not match this installation'
}
Write-Host 'Startup shortcut target, arguments and working directory verified.'
Write-Host 'Actual logon startup still requires a new Windows session and a remote MCP ping.'
