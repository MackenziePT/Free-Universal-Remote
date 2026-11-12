# Live Windows regression. Requires an already verified startup shortcut and healthy tunnel.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $Root 'scripts\Test-Startup.ps1')
$Link = Join-Path ([Environment]::GetFolderPath('Startup')) 'Harmony Remote MCP.lnk'
$BeforeBytes = [IO.File]::ReadAllBytes($Link)
$BeforeTime = (Get-Item -LiteralPath $Link).LastWriteTimeUtc.Ticks
$BackupDir = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\startup-backups'
$BeforeBackups = @(Get-ChildItem -LiteralPath $BackupDir -File -ErrorAction SilentlyContinue).Count
& (Join-Path $Root 'scripts\Enable-Startup.ps1')
$AfterBackups = @(Get-ChildItem -LiteralPath $BackupDir -File -ErrorAction SilentlyContinue).Count
$AfterTime = (Get-Item -LiteralPath $Link).LastWriteTimeUtc.Ticks
if ($AfterTime -ne $BeforeTime -or $AfterBackups -ne $BeforeBackups) { throw 'FAIL: valid startup shortcut was rewritten or redundantly backed up.' }
if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$BeforeBytes,[byte[]][IO.File]::ReadAllBytes($Link))) { throw 'FAIL: startup shortcut bytes changed.' }
Write-Output 'PASS: enabling auto-start again is a no-op for a validated shortcut.'
