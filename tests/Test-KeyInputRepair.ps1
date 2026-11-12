# Actual repair/backup/hash/rollback operations in a disposable directory.
# The Windows CMD host and authentication are not executed by this test.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $Root 'scripts/Repair-KeyInput.ps1')
$Sandbox = Join-Path ([IO.Path]::GetTempPath()) ('universal repair [test] ' + [guid]::NewGuid().ToString('N'))
$Original = [IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'fixtures/Initialize-Tunnel.console.ps1.txt'))
# Historical repair installs a pinned 2026-10-22 payload. The RC4.4
# Initialize-Tunnel.ps1 is intentionally newer and has a different hash.
if (-not (Get-Command Get-FileHash -ErrorAction SilentlyContinue)) {
    if ($PSVersionTable.PSEdition -eq 'Desktop') {
        Import-Module Microsoft.PowerShell.Utility -RequiredVersion 3.1.0.0 -ErrorAction Stop
    } else { Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop }
}
$FixedHash = 'fbe8b65d201e34e593bf448afa2b9befd70bd5124718a688d0f898997ccef3c2'
function Assert-True($Value, [string]$Message) { if (-not $Value) { throw ('FAIL: ' + $Message) } }
try {
    $State = Join-Path $Sandbox 'state'
    $Target = Join-Path $State 'app/scripts/Initialize-Tunnel.ps1'
    $Backup = Join-Path $State 'repair-backups/key-paste-20261022/Initialize-Tunnel.ps1.bak'
    $null = [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target))
    [IO.File]::WriteAllText((Join-Path $State 'app/scripts/Bootstrap.ps1'), "throw 'Bootstrap must not execute in unit repair test'")
    [IO.File]::WriteAllBytes($Target, $Original)
    [IO.File]::WriteAllText((Join-Path $State 'tunnel-key.dpapi'), 'synthetic-dpapi-placeholder')
    [IO.File]::WriteAllText((Join-Path $State 'app/config.json'), '{"test":"preserve configuration"}')
    $OriginalHash = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash
    $null = Invoke-UniversalKeyInputRepair -State $State
    Assert-True ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -eq $FixedHash) 'fixed bytes installed'
    Assert-True ((Get-FileHash -LiteralPath $Backup -Algorithm SHA256).Hash -eq $OriginalHash) 'exact original backed up'
    Write-Output 'PASS: repair installs exact fixed bytes and preserves original'
    $BackupTime = [IO.File]::GetLastWriteTimeUtc($Backup).Ticks
    $null = Invoke-UniversalKeyInputRepair -State $State
    Assert-True ([IO.File]::GetLastWriteTimeUtc($Backup).Ticks -eq $BackupTime) 'second run must not overwrite backup'
    Write-Output 'PASS: repeat repair is idempotent'
    $null = Invoke-UniversalKeyInputRepair -State $State -Rollback
    Assert-True ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -eq $OriginalHash) 'rollback restores original bytes'
    $null = Invoke-UniversalKeyInputRepair -State $State -Rollback
    Write-Output 'PASS: rollback and repeat rollback restore original bytes'
    [IO.File]::WriteAllText($Target, '# unknown local revision')
    $Failed = $false
    try { $null = Invoke-UniversalKeyInputRepair -State $State } catch { $Failed = $true }
    Assert-True $Failed 'unknown revision refused'
    Assert-True ([IO.File]::ReadAllText($Target) -eq '# unknown local revision') 'unknown revision retained'
    Write-Output 'PASS: unknown revision is not overwritten'
    [IO.File]::WriteAllBytes($Target, $Original)
    [IO.File]::WriteAllText($Backup, '# modified backup')
    $Failed = $false
    try { $null = Invoke-UniversalKeyInputRepair -State $State } catch { $Failed = $true }
    Assert-True $Failed 'modified backup refused'
    Assert-True ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -eq $OriginalHash) 'original retained after backup error'
    Write-Output 'PASS: modified backup stops repair without changing target'
    Assert-True ([IO.File]::ReadAllText((Join-Path $State 'tunnel-key.dpapi')) -eq 'synthetic-dpapi-placeholder') 'synthetic credential retained'
    Assert-True ([IO.File]::ReadAllText((Join-Path $State 'app/config.json')) -eq '{"test":"preserve configuration"}') 'configuration retained'
    Assert-True (@(Get-ChildItem -LiteralPath (Split-Path -LiteralPath $Target) -Filter '*.repair.*').Count -eq 0) 'no leftover staging file'
    Write-Output 'PASS: credential/configuration preserved and temporary files cleaned'
} finally {
    if (Test-Path -LiteralPath $Sandbox) { Remove-Item -LiteralPath $Sandbox -Recurse -Force }
}
