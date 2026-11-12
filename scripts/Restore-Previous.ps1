# Restore a specified installer backup, retaining both the backup and replaced app.
[CmdletBinding(SupportsShouldProcess=$true)]
param([Parameter(Mandatory=$true)][string]$BackupPath)
$ErrorActionPreference = 'Stop'
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
$Backup = (Resolve-Path -LiteralPath $BackupPath).Path
if ((Split-Path $Backup) -ne $State -or (Split-Path $Backup -Leaf) -notmatch '^app\.previous\.[0-9a-f]{32}$') {
    throw 'Choose an exact app.previous.<id> directory in the agent state folder'
}
if ((Get-Item -LiteralPath $Backup).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Backup aliases are forbidden' }
foreach ($Required in @('config.json','smoke_test.py','.venv\Scripts\python.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Backup $Required) -PathType Leaf)) { throw "Incomplete backup: $Required" }
}
$Destination = Join-Path $State 'app'
if (-not $PSCmdlet.ShouldProcess($Destination, "Restore application from $Backup")) { return }
$Mutex = [Threading.Mutex]::new($false, 'Local\HarmonyRemoteMCP')
$Locked = $false
$Stage = Join-Path $State ('app.restore.' + [guid]::NewGuid().ToString('N'))
$Replaced = Join-Path $State ('app.before-rollback.' + [guid]::NewGuid().ToString('N'))
$MovedOld = $false
try {
    try { $Locked = $Mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $Locked = $true }
    if (-not $Locked) { throw 'Stop the tunnel before restoring the app' }
    Copy-Item -LiteralPath $Backup -Destination $Stage -Recurse
    if (Test-Path -LiteralPath $Destination) {
        Move-Item -LiteralPath $Destination -Destination $Replaced -ErrorAction Stop
        $MovedOld = $true
    }
    try {
        Move-Item -LiteralPath $Stage -Destination $Destination -ErrorAction Stop
        $OldConfig = $env:HARMONY_MCP_CONFIG
        try {
            $env:HARMONY_MCP_CONFIG = Join-Path $Destination 'config.json'
            & (Join-Path $Destination '.venv\Scripts\python.exe') (Join-Path $Destination 'smoke_test.py')
            if ($LASTEXITCODE -ne 0) { throw 'Restored app did not pass MCP handshake' }
        } finally { $env:HARMONY_MCP_CONFIG = $OldConfig }
    } catch {
        if (Test-Path -LiteralPath $Destination) {
            Move-Item -LiteralPath $Destination -Destination ($Stage + '.failed') -ErrorAction Stop
        }
        if ($MovedOld) { Move-Item -LiteralPath $Replaced -Destination $Destination -ErrorAction Stop }
        throw
    }
    Write-Host 'Previous app restored and MCP handshake passed. Runtime credentials and grants were not changed.'
    Write-Host "Original backup retained: $Backup"
    if ($MovedOld) { Write-Host "Replaced app retained: $Replaced" }
} finally {
    # Failed staging is retained for diagnosis; this script never deletes an app.
    if ($Locked) { $Mutex.ReleaseMutex() }
    $Mutex.Dispose()
}
