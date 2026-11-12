[CmdletBinding()]
param()
$Shortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'Harmony Remote MCP.lnk'
if (Test-Path $Shortcut) { Remove-Item -LiteralPath $Shortcut -Force }
Write-Host 'Startup entry removed. Any currently running tunnel must be closed separately.'
