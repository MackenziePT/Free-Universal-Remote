# Portable validation tests. Windows Forms and the Windows clipboard are not exercised here.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $Root 'scripts/Initialize-Tunnel.ps1')
function Assert-True($Value, [string]$Message) { if (-not $Value) { throw ('FAIL: ' + $Message) } }
$Synthetic = 'sk-SYNTHETIC-NOT-A-CREDENTIAL_' + ('AaZz0123456789-_' * 30)
$Secure = ConvertTo-UniversalTunnelKey (" `r`n" + $Synthetic + "`r`n ")
try {
    $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { $Equal = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer) -ceq $Synthetic }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer) }
    Assert-True $Equal 'whole pasted value, case and punctuation must be preserved'
    Assert-True $Secure.IsReadOnly() 'returned key is read-only'
} finally { $Secure.Dispose() }
Write-Output 'PASS: complete long synthetic paste preserved; surrounding whitespace removed'
$Invalid = @($null, '', '   ', ('tunnel_' + ('a' * 32)), 'Universal Remote MCP - Windows', "sk-abc`nextra", "sk-abc`0extra", 'sk-abc extra', 'sk-', ('sk-' + ('a' * 4096)))
foreach ($Value in $Invalid) {
    $Failed = $false
    try { $Unexpected = ConvertTo-UniversalTunnelKey $Value; $Unexpected.Dispose() }
    catch {
        $Failed = $true
        Assert-True (-not $_.Exception.Message.Contains('sk-abc')) 'error must not echo input'
        Assert-True (-not $_.Exception.Message.Contains('tunnel_')) 'error must not echo tunnel ID'
    }
    Assert-True $Failed 'invalid input must be rejected before authentication'
}
Write-Output ('PASS: ' + $Invalid.Count + ' invalid inputs rejected without echoing the value')
$CaseSensitive = ConvertTo-UniversalTunnelKey 'sk-Synthetic_AbC-987654321'
try { Assert-True ($CaseSensitive.Length -eq 26) 'ordinary complete token accepted' }
finally { $CaseSensitive.Dispose() }
Write-Output 'PASS: ordinary pasted token accepted as SecureString'

# Event callbacks use closures after their builder's script scope has returned.
$Callback = & {
    param($Path)
    . $Path
    $Converter = ${function:ConvertTo-UniversalTunnelKey}
    $Validator = ${function:Get-UniversalTunnelKeyError}
    return { & $Converter -Value 'sk-Synthetic_AbC-987654321' -Validator $Validator }.GetNewClosure()
} (Join-Path $Root 'scripts/Initialize-Tunnel.ps1')
$FromClosure = & $Callback
try { Assert-True ($FromClosure -is [Security.SecureString]) 'event converter must survive its builder scope' }
finally { $FromClosure.Dispose() }
Write-Output 'PASS: event callback retains validation and conversion after builder scope exits'
