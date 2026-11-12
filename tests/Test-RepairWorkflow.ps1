# Actual repair/backup/hash/rollback operations in a disposable directory.
# The Windows CMD host and authentication are not executed by this test.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $Root 'scripts/Tunnel-Client.ps1') # preload native Windows PS utility module if needed
. (Join-Path $Root 'scripts/Repair-Verification.ps1')
$Sandbox = Join-Path ([IO.Path]::GetTempPath()) ('universal repair [test] ' + [guid]::NewGuid().ToString('N'))
$Original = [IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'fixtures/Verify-Windows.standalone-2.ps1.txt'))
# The legacy standalone verifier repair has a pinned 2026-10-22 payload;
# modern Verify-Windows.ps1 intentionally differs and must not be used as expected hash.
$FixedHash = '76eafee038d131b1240c5e1135cfec0d9141c42ab4ebb1ecebbdfefbd8828e28'
function Assert-True($Value, [string]$Message) { if (-not $Value) { throw ('FAIL: ' + $Message) } }
try {
    $State = Join-Path $Sandbox 'state'
    $Target = Join-Path $State 'app/scripts/Verify-Windows.ps1'
    $Backup = Join-Path $State 'repair-backups/verify-cwd-20261022/Verify-Windows.ps1.bak'
    $null = [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target))
    [IO.File]::WriteAllText((Join-Path $State 'app/scripts/Bootstrap.ps1'), "throw 'Bootstrap must not execute in unit repair test'")
    [IO.File]::WriteAllBytes($Target, $Original)
    [IO.File]::WriteAllText((Join-Path $State 'tunnel-key.dpapi'), 'synthetic-dpapi-placeholder')
    [IO.File]::WriteAllText((Join-Path $State 'app/config.json'), '{"test":"preserve configuration"}')
    $OriginalHash = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash
    $null = Invoke-UniversalVerifierRepair -State $State
    Assert-True ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -eq $FixedHash) 'fixed bytes installed'
    Assert-True ((Get-FileHash -LiteralPath $Backup -Algorithm SHA256).Hash -eq $OriginalHash) 'exact original backed up'
    Write-Output 'PASS: repair installs exact fixed bytes and preserves original'
    $BackupTime = [IO.File]::GetLastWriteTimeUtc($Backup).Ticks
    $null = Invoke-UniversalVerifierRepair -State $State
    Assert-True ([IO.File]::GetLastWriteTimeUtc($Backup).Ticks -eq $BackupTime) 'second run must not overwrite backup'
    Write-Output 'PASS: repeat repair is idempotent'
    $null = Invoke-UniversalVerifierRepair -State $State -Rollback
    Assert-True ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -eq $OriginalHash) 'rollback restores original bytes'
    $null = Invoke-UniversalVerifierRepair -State $State -Rollback
    Write-Output 'PASS: rollback and repeat rollback restore original bytes'
    [IO.File]::WriteAllText($Target, '# unknown local revision')
    $Failed = $false
    try { $null = Invoke-UniversalVerifierRepair -State $State } catch { $Failed = $true }
    Assert-True $Failed 'unknown revision refused'
    Assert-True ([IO.File]::ReadAllText($Target) -eq '# unknown local revision') 'unknown revision retained'
    Write-Output 'PASS: unknown revision is not overwritten'
    [IO.File]::WriteAllBytes($Target, $Original)
    [IO.File]::WriteAllText($Backup, '# modified backup')
    $Failed = $false
    try { $null = Invoke-UniversalVerifierRepair -State $State } catch { $Failed = $true }
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
