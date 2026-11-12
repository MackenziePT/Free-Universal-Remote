# Read a user-DPAPI-protected value without exposing or logging plaintext.
# Windows PowerShell 5.1 legacy Set-Content -Encoding UTF8 adds BOM + CRLF.
function Read-UniversalStoredSecret {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'DPAPI credential file missing'
    }
    $File = Get-Item -LiteralPath $Path -ErrorAction Stop
    if ($File.Length -lt 128 -or $File.Length -gt 16384) {
        throw 'Unexpected DPAPI credential size'
    }
    $Cipher = [IO.File]::ReadAllText($File.FullName, [Text.Encoding]::UTF8)
    $Cipher = $Cipher.Trim([char]0xfeff, [char]13, [char]10, [char]32, [char]9)
    if ($Cipher -cnotmatch '\A[0-9a-fA-F]{128,}\z') {
        throw 'Invalid DPAPI ciphertext format'
    }
    return ConvertTo-SecureString -String $Cipher -ErrorAction Stop
}
