# Windows PowerShell 5.1 may see PowerShell 7 modules first in PSModulePath.
# Load the Desktop-compatible Security module explicitly when auto-loading fails.
$ErrorActionPreference = 'Stop'
if (-not (Get-Command ConvertTo-SecureString -ErrorAction SilentlyContinue) -or
    -not (Get-Command ConvertFrom-SecureString -ErrorAction SilentlyContinue)) {
    if ($PSVersionTable.PSEdition -eq 'Desktop') {
        Import-Module Microsoft.PowerShell.Security -RequiredVersion 3.0.0.0 -ErrorAction Stop
    } else {
        Import-Module Microsoft.PowerShell.Security -ErrorAction Stop
    }
}
if (-not (Get-Command ConvertTo-SecureString -ErrorAction SilentlyContinue) -or
    -not (Get-Command ConvertFrom-SecureString -ErrorAction SilentlyContinue)) {
    throw 'Microsoft.PowerShell.Security conversion commands are unavailable.'
}
