# CA-issued Individual Validation Authenticode signing.
# Preflight is read-only. Sign is explicitly opt-in, requires HSM/token/CKA.
# Never copy private keys, PINs, OTPs or PFX passwords into source/build logs.
[CmdletBinding()]
param(
    [ValidateSet('Preflight','Sign')][string]$Mode = 'Preflight',
    [string]$CertificateThumbprint = '',
    [string]$PublisherLegalName = '',
    [string]$TimestampUrl = 'http://ts.ssl.com',
    [switch]$ConfirmIdentityValidated,
    [switch]$ConfirmSecureKeyProvider
)
$ErrorActionPreference = 'Stop'
$root=Split-Path -Parent $PSScriptRoot
$bundle=Join-Path $root 'evidence\qa\public-portable-prototype'
if($Mode -eq 'Sign') {
    # Private QA executables must NEVER be published with a CA signature.
    $bundle=Join-Path $root 'evidence\qa\publisher-ready-bundle'
}
$iss=Join-Path $root 'packaging\UniversalRemote-SIGNED-CANDIDATE.iss'
$verify=Join-Path $PSScriptRoot 'Test-PublisherSignature.ps1'
$signTool=Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Filter 'signtool.exe' -Recurse -ErrorAction Stop | Where-Object { $_.FullName -match '\\x64\\signtool.exe$' } | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
$inno=Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'
$names=@('UniversalRemote-Preview','UniversalRemoteAgent-Preview',
         'UniversalRemoteUpdater-Preview','UniversalRemoteTunnel-Preview')
function Refuse([string]$reason) { throw ('SIGNING_BLOCKED: '+$reason) }
if (-not $signTool -or -not (Test-Path -LiteralPath $inno -PathType Leaf)) { Refuse 'SignTool or Inno Setup 7 missing' }
foreach($file in @($iss,$verify)) {
    if(-not (Test-Path -LiteralPath $file -PathType Leaf)) { Refuse 'Missing signed-release template or gate' }
}
foreach($name in $names) {
    $exe=Join-Path (Join-Path $bundle $name) ($name+'.exe')
    if(-not (Test-Path -LiteralPath $exe -PathType Leaf)) { Refuse ('Missing built EXE: '+$name) }
}
if($Mode -eq 'Preflight' -and -not $CertificateThumbprint) {
    $available=@(Get-ChildItem Cert:\CurrentUser\My -ErrorAction SilentlyContinue | Where-Object {
        $eku=@($_.EnhancedKeyUsageList | ForEach-Object {$_.ObjectId})
        $_.HasPrivateKey -and ($eku -contains '1.3.6.1.5.5.7.3.3')
    })
    Write-Output ('IV_PREFLIGHT SDK=READY INNO=READY BUILD=READY CODE_SIGNING_CERTS='+$available.Count)
    if($available.Count -eq 0) {
        Write-Output 'CA_ISSUED_IV_CERTIFICATE_MISSING'
        exit 3
    }
    Write-Output 'CERTIFICATE_PRESENT: select exact CA-issued thumbprint locally'
    return
}
$thumb=($CertificateThumbprint -replace '\s','').ToUpperInvariant()
if($thumb -notmatch '^[A-F0-9]{40}$') { Refuse 'Certificate thumbprint must be 40 hexadecimal digits' }
$cert=Get-Item -LiteralPath ('Cert:\CurrentUser\My\'+$thumb) -ErrorAction SilentlyContinue
if(-not $cert) { Refuse 'CA-issued certificate not in personal Windows certificate store' }
$actualName=$cert.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false)
if ($Mode -eq 'Preflight') {
    $ekus=@($cert.EnhancedKeyUsageList | ForEach-Object {$_.ObjectId})
    Write-Output ('CERTIFICATE_PREFLIGHT EKU='+($ekus -contains '1.3.6.1.5.5.7.3.3')+
                  ' KEY='+$cert.HasPrivateKey+' EXPIRED='+($cert.NotAfter -le [DateTime]::UtcNow))
    return
}
if(-not $ConfirmIdentityValidated -or -not $ConfirmSecureKeyProvider) {
    Refuse 'Local owner confirmations required for validated identity and hardware-backed key'
}
if([string]::IsNullOrWhiteSpace($PublisherLegalName) -or $PublisherLegalName.Length -gt 100 -or
    $PublisherLegalName -match '[#"<>{}\r\n]') {
    Refuse 'PublisherLegalName must exactly match the CA-validated personal name'
}
if(-not [string]::Equals($PublisherLegalName,$actualName,[System.StringComparison]::OrdinalIgnoreCase)) {
    Refuse 'Publisher identity mismatch'
}
if($TimestampUrl -notmatch '^https?://[A-Za-z0-9.-]+(/[A-Za-z0-9/._-]*)?$') {
    Refuse 'Invalid CA timestamp URL'
}
if(-not $cert.HasPrivateKey -or $cert.Subject -eq $cert.Issuer -or
   $cert.NotBefore -gt [DateTime]::UtcNow -or $cert.NotAfter -le [DateTime]::UtcNow) {
    Refuse 'Certificate is self-signed, expired or missing private key'
}
$eku=@($cert.EnhancedKeyUsageList | ForEach-Object {$_.ObjectId})
if($eku -notcontains '1.3.6.1.5.5.7.3.3') { Refuse 'Code Signing EKU required' }
$chain=New-Object System.Security.Cryptography.X509Certificates.X509Chain
try {
    $chain.ChainPolicy.RevocationMode=[System.Security.Cryptography.X509Certificates.X509RevocationMode]::Online
    if(-not $chain.Build($cert)) { Refuse 'Certificate chain/revocation validation failed' }
} finally { $chain.Dispose() }
# A public release MUST NOT ship a QA updater that accepts caller-supplied keys.
# Trust anchors must be immutable, embedded, and independently provisioned.
$updaterBinary=Join-Path $bundle 'UniversalRemoteUpdater-Preview\UniversalRemoteUpdater-Preview.exe'
$profileJson=& $updaterBinary trust-profile
if($LASTEXITCODE -ne 0) { Refuse 'Updater does not expose a valid built-in trust profile' }
try { $trustProfile=$profileJson | ConvertFrom-Json -ErrorAction Stop }
catch { Refuse 'Updater trust profile returned invalid JSON' }
if($trustProfile.channel -ne 'PRODUCTION' -or $trustProfile.embedded_keys -lt 1) {
    Refuse 'Updater lacks production-pinned publisher signing keys. Rebuild from verified public-key anchor.'
}
$stage=Join-Path ([IO.Path]::GetTempPath()) ('UR-IV-RELEASE-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage -ErrorAction Stop | Out-Null
try {
    foreach($name in $names) {
        $source=Join-Path $bundle $name
        if(@(Get-ChildItem -LiteralPath $source -Recurse -Force -Attributes ReparsePoint -ErrorAction Stop).Count -gt 0) {
            Refuse 'Unsafe link/junction in source payload'
        }
        Copy-Item -LiteralPath $source -Destination (Join-Path $stage $name) -Recurse -Force -ErrorAction Stop
        $exe=Join-Path (Join-Path $stage $name) ($name+'.exe')
        & $signTool sign /sha1 $thumb /s My /fd SHA256 /tr $TimestampUrl /td SHA256 $exe | Out-Null
        if($LASTEXITCODE -ne 0) { Refuse ('Signing failed: '+$name) }
    }
    $out=Join-Path $stage 'output'
    New-Item -ItemType Directory -Path $out -ErrorAction Stop | Out-Null
    $signCommand=('"'+$signTool+'" sign /sha1 '+$thumb+' /s My /fd SHA256 /tr '+$TimestampUrl+' /td SHA256 $f')
    & $inno '--no-ide-signtools' ('--signtool=URPublisher='+$signCommand) ('-dPublisherLegalName='+$PublisherLegalName) ('-dPackageRoot='+$stage) ('--output-dir='+$out) $iss | Out-Null
    if($LASTEXITCODE -ne 0) { Refuse 'Signed Inno compilation failed' }
    $installer=Join-Path $out 'UniversalRemote-1.0.0-rc5.1-x64-SIGNED-CANDIDATE.exe'
    if(-not (Test-Path -LiteralPath $installer -PathType Leaf)) { Refuse 'Signed installer missing' }
    & $verify -Installer $installer -ExpectedPublisher $PublisherLegalName -PortableRoot $stage
    $destination=Join-Path $root 'evidence\qa\ca-signed-candidate'
    if(Test-Path -LiteralPath $destination) { Refuse 'Signed candidate already exists; never overwrite it' }
    New-Item -ItemType Directory -Path $destination -ErrorAction Stop | Out-Null
    foreach($name in $names) {
        Copy-Item -LiteralPath (Join-Path $stage $name) -Destination (Join-Path $destination $name) -Recurse -ErrorAction Stop
    }
    Copy-Item -LiteralPath $installer -Destination (Join-Path $destination (Split-Path $installer -Leaf)) -ErrorAction Stop
    Write-Output ('SIGNED_CANDIDATE_FOR_REVIEW '+$destination)
    Write-Output 'PUBLIC_RELEASE_BLOCKED_UNTIL_INDEPENDENT_TESTS_AND_SECURITY_AUDIT'
} finally {
    if(Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}
