# Release signature gate. Never imports private keys or signs files.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ExpectedPublisher,
    [Parameter(Mandatory=$true)][string]$PortableRoot
)
$ErrorActionPreference = 'Stop'
$paths = @(
    $Installer,
    (Join-Path $PortableRoot 'UniversalRemoteAgent-Preview\UniversalRemoteAgent-Preview.exe'),
    (Join-Path $PortableRoot 'UniversalRemote-Preview\UniversalRemote-Preview.exe'),
    (Join-Path $PortableRoot 'UniversalRemoteUpdater-Preview\UniversalRemoteUpdater-Preview.exe'),
    (Join-Path $PortableRoot 'UniversalRemoteTunnel-Preview\UniversalRemoteTunnel-Preview.exe')
)
if ([string]::IsNullOrWhiteSpace($ExpectedPublisher) -or $ExpectedPublisher.Length -lt 4) {
    throw 'E obrigatorio indicar a identidade legal do editor.'
}
$signTool = Get-ChildItem -LiteralPath 'C:\Program Files (x86)\Windows Kits\10\bin' -Filter signtool.exe -Recurse -ErrorAction Stop |
    Where-Object { $_.FullName -match '\\x64\\signtool.exe$' } |
    Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
if (-not $signTool) { throw 'Windows SDK / SignTool nao encontrado.' }
if (-not (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue)) {
    $mod = Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1'
    if (Test-Path -LiteralPath $mod) { Import-Module -Name $mod -ErrorAction Stop }
}
if (-not (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue)) {
    throw 'Modulo Microsoft.PowerShell.Security nao disponivel.'
}
foreach ($path in $paths) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw ('Falta ficheiro de release: ' + (Split-Path $path -Leaf))
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $path -ErrorAction Stop
    if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate) {
        throw ('Assinatura Authenticode invalida: ' + (Split-Path $path -Leaf))
    }
    # Exact leaf CN match: wildcards or substring matches can certify another publisher.
    $actualPublisher = $signature.SignerCertificate.GetNameInfo(
        [System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
    if (-not [string]::Equals($actualPublisher, $ExpectedPublisher,
            [System.StringComparison]::OrdinalIgnoreCase)) {
        throw ('Identidade do editor inesperada: ' + (Split-Path $path -Leaf))
    }
    if ($signature.SignerCertificate.Subject -eq $signature.SignerCertificate.Issuer) {
        throw ('Certificado autoassinado recusado: ' + (Split-Path $path -Leaf))
    }
    if (-not $signature.TimeStamperCertificate) {
        throw ('Carimbo temporal em falta: ' + (Split-Path $path -Leaf))
    }
    $ekuIds = @($signature.SignerCertificate.EnhancedKeyUsageList |
        ForEach-Object { $_.ObjectId })
    if ($ekuIds -notcontains '1.3.6.1.5.5.7.3.3') {
        throw ('Certificate lacks Code Signing EKU: ' + (Split-Path $path -Leaf))
    }
    & $signTool verify /pa /all /v $path | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw ('Cadeia de confianca Authenticode falhou: ' + (Split-Path $path -Leaf))
    }
    Write-Output ('PASS_SIGNED ' + (Split-Path $path -Leaf))
}
Write-Output 'PUBLISHER_SIGNATURE_GATE_PASS'
