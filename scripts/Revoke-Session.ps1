# RC5.1 local revocation. Read the active product config; never revoke another installation.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$HomePath = Join-Path $env:LOCALAPPDATA 'UniversalRemote'
$ConfigPath = Join-Path $HomePath 'config.json'
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw 'Universal Remote RC5.1 is not configured. No permissions were changed.'
}
$Config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$Grant = [IO.Path]::GetFullPath([string]$Config.grants_path)
$Expected = [IO.Path]::GetFullPath((Join-Path $HomePath 'grants.json'))
if (-not [string]::Equals($Grant,$Expected,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'The configured grant path differs from the RC5.1 product path. Revoke from the application instead.'
}
if (Test-Path -LiteralPath $Grant -PathType Leaf) {
    $File = Get-Item -LiteralPath $Grant -Force
    if ($File.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Refusing to follow a grant-file reparse point'
    }
    Remove-Item -LiteralPath $Grant -Force
}
Write-Host 'Universal Remote RC5.1: future privileged MCP calls revoked. Previously launched processes may continue.' -ForegroundColor Green
