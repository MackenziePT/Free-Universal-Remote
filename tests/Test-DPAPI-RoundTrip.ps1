# Regression: old Windows PowerShell 5.1 DPAPI files have BOM + CRLF.
# This test uses a synthetic disposable secret and never prints it.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $Root 'scripts\PowerShell-Security.ps1')
. (Join-Path $Root 'scripts\Secret-Storage.ps1')
$Directory = Join-Path $env:TEMP ('universal-dpapi-regression-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $Directory | Out-Null
try {
    $Synthetic = ConvertTo-SecureString -String 'synthetic-local-test-not-an-api-credential' -AsPlainText -Force
    $CipherText = ConvertFrom-SecureString -SecureString $Synthetic
    $Legacy = Join-Path $Directory 'legacy.dpapi'
    $CipherText | Set-Content -LiteralPath $Legacy -Encoding UTF8
    $Bytes = [IO.File]::ReadAllBytes($Legacy)
    if ($Bytes.Length -lt 4 -or $Bytes[0] -ne 239 -or $Bytes[1] -ne 187 -or $Bytes[2] -ne 191) {
        throw 'Legacy fixture must have a UTF8 BOM.'
    }
    $Decoded = Read-UniversalStoredSecret -Path $Legacy
    try {
        if ($Decoded.Length -ne $Synthetic.Length) { throw 'Legacy DPAPI round-trip length mismatch' }
    } finally { $Decoded.Dispose() }
    Write-Output 'PASS: legacy UTF8 BOM+CRLF DPAPI ciphertext unseals safely'

    $Modern = Join-Path $Directory 'modern.dpapi'
    [IO.File]::WriteAllText($Modern, $CipherText, (New-Object Text.UTF8Encoding($false)))
    $Decoded = Read-UniversalStoredSecret -Path $Modern
    try {
        if ($Decoded.Length -ne $Synthetic.Length) { throw 'Modern DPAPI round-trip mismatch' }
    } finally { $Decoded.Dispose() }
    Write-Output 'PASS: modern BOM-less ciphertext unseals safely'

    $Bad = Join-Path $Directory 'corrupted.dpapi'
    [IO.File]::WriteAllText($Bad, 'not-ciphertext', (New-Object Text.UTF8Encoding($false)))
    $Rejected = $false
    try {
        $Wrong = Read-UniversalStoredSecret -Path $Bad
        if ($Wrong) { $Wrong.Dispose() }
    } catch { $Rejected = $true }
    if (-not $Rejected) { throw 'Malformed ciphertext was accepted' }
    Write-Output 'PASS: malformed DPAPI file rejected'

    foreach ($Name in @('Start-Tunnel.ps1', 'Test-Tunnel.ps1')) {
        $Content = [IO.File]::ReadAllText((Join-Path $Root ('scripts\' + $Name)))
        if ($Content -notmatch 'Read-UniversalStoredSecret') {
            throw ('Production script missing secure reader: ' + $Name)
        }
    }
    Write-Output 'PASS: both production secret consumers use compatible reader'
} finally {
    if ($Synthetic) { $Synthetic.Dispose() }
    Remove-Item -LiteralPath $Directory -Recurse -Force -ErrorAction SilentlyContinue
}
