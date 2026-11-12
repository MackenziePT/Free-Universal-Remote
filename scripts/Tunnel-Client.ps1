# Explicitly load the Windows PowerShell 5.1 native module when auto-loading
# wrongly chooses PowerShell 7's module from an inherited PSModulePath.
if (-not (Get-Command Get-FileHash -ErrorAction SilentlyContinue)) {
    if ($PSVersionTable.PSEdition -eq 'Desktop') {
        Import-Module Microsoft.PowerShell.Utility -RequiredVersion 3.1.0.0 -ErrorAction Stop
    } else {
        Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
    }
}
# Integrity check for the pinned official Windows x64 client shipped in this release.
# The published release archive SHA-256 is recorded separately in bin/.
function Assert-VerifiedTunnelClient {
    param([Parameter(Mandatory=$true)][string]$Root)
    $Client = Join-Path $Root 'bin\tunnel-client.exe'
    $Origin = Join-Path $Root 'bin\tunnel-client-origin.json'
    if (-not (Test-Path -LiteralPath $Client -PathType Leaf) -or -not (Test-Path -LiteralPath $Origin -PathType Leaf)) {
        throw 'Verified official Windows tunnel client is missing; use the full standalone package'
    }
    $Expected = '4226bb74a72388147882881f29f79801b95e285d731a138071812e3aa6766571'
    $Receipt = Get-Content -LiteralPath $Origin -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    if ($Receipt.release -ne 'v0.0.16' -or $Receipt.platform -ne 'windows-amd64' -or
        $Receipt.executable_sha256 -cne $Expected -or $Receipt.executable_bytes -ne 22591488 -or
        (Get-Item -LiteralPath $Client).Length -ne 22591488 -or
        (Get-FileHash -LiteralPath $Client -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Expected) {
        throw 'Bundled tunnel client integrity check failed'
    }
}

function Copy-VerifiedTunnelClient {
    param([Parameter(Mandatory=$true)][string]$SourceRoot,
          [Parameter(Mandatory=$true)][string]$DestinationRoot)
    Assert-VerifiedTunnelClient -Root $SourceRoot
    $Target = Join-Path $DestinationRoot 'bin'
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    foreach ($Name in @('tunnel-client.exe','tunnel-client-origin.json','LICENSE','NOTICE',
            'tunnel-client-v0.0.16-windows-amd64-licenses.txt','tunnel-client-v0.0.16-windows-amd64.spdx.json')) {
        Copy-Item -LiteralPath (Join-Path $SourceRoot ('bin\' + $Name)) -Destination $Target -ErrorAction Stop
    }
    Assert-VerifiedTunnelClient -Root $DestinationRoot
}
