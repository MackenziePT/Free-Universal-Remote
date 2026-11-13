# This script must be executed LOCALLY by the Windows account owner.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('writes','shell','screen','input')]
    [string[]]$Capabilities,
    [ValidateRange(1,60)]
    [int]$Minutes = 15
)
$ErrorActionPreference = 'Stop'
Write-Host "Requested abilities: $($Capabilities -join ', ') for $Minutes minute(s)." -ForegroundColor Yellow
Write-Host 'PowerShell and desktop control can access data beyond the MCP allowed_roots.' -ForegroundColor Yellow
$Proof = Read-Host 'On this PC, type AUTORIZAR to confirm'
if ($Proof -cne 'AUTORIZAR') { throw 'Local authorization cancelled' }
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
New-Item -ItemType Directory -Path $State -Force | Out-Null
$Until = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() + ($Minutes * 60)
$Grants = Join-Path $State 'grants.json'
$Content = @{ expires_at = $Until; capabilities = @($Capabilities) } | ConvertTo-Json -Compress
$NewFile = Join-Path $State ([IO.Path]::GetRandomFileName())
try {
    [IO.File]::WriteAllText($NewFile, $Content, (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $NewFile -Destination $Grants -Force
} finally { Remove-Item -LiteralPath $NewFile -Force -ErrorAction SilentlyContinue }
Write-Host ('Local access granted until {0:u} UTC.' -f [DateTimeOffset]::FromUnixTimeSeconds($Until).UtcDateTime) -ForegroundColor Green
