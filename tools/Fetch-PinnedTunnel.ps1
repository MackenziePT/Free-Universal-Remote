# Fetch official pinned tunnel client and companion; hashes validated before use.
# No app installation, tunnels, credential reads or network listeners.
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$zipUrl='https://github.com/openai/tunnel-client/releases/download/v0.0.16/tunnel-client-v0.0.16-windows-amd64.zip'
$zipHash='edef7241b0c647fcb30f1a80ff376b6b25c51927960f257a3f01e21b17c2aba6'
$exeHash='4226bb74a72388147882881f29f79801b95e285d731a138071812e3aa6766571'
function SHA256File([string]$path) {
    $hash=[Security.Cryptography.SHA256]::Create()
    $stream=[IO.File]::OpenRead($path)
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$hash.Dispose() }
}
$workspace=Join-Path ([IO.Path]::GetTempPath()) 'universal-remote-pinned-tunnel-v0016'
New-Item -ItemType Directory -Force -Path $workspace | Out-Null
$zip=Join-Path $workspace 'official.zip'
if (-not (Test-Path -LiteralPath $zip) -or (SHA256File $zip) -ne $zipHash) {
    Invoke-WebRequest -Uri $zipUrl -OutFile $zip
}
if ((SHA256File $zip) -ne $zipHash) { throw 'Pinned official tunnel ZIP hash mismatch' }
$expanded=Join-Path $workspace 'unpacked'
if (Test-Path -LiteralPath $expanded) { Remove-Item -LiteralPath $expanded -Recurse -Force }
Expand-Archive -LiteralPath $zip -DestinationPath $expanded
$matches=@(Get-ChildItem -LiteralPath $expanded -Recurse -File -Filter 'tunnel-client.exe')
if ($matches.Count -ne 1) { throw 'Pinned archive must contain exactly one tunnel-client.exe' }
$agent=$matches[0]
if ($agent.Length -ne 22591488 -or (SHA256File $agent.FullName) -ne $exeHash) { throw 'Pinned tunnel executable hash mismatch' }
$companions=@(Get-ChildItem -LiteralPath $expanded -Recurse -File -Filter 'cloudflared.exe')
if ($companions.Count -ne 1 -or $companions[0].DirectoryName -ne $agent.DirectoryName) { throw 'Missing adjacent cloudflared.exe companion' }
$manifests=@(Get-ChildItem -LiteralPath $expanded -Recurse -File -Filter 'cloudflared-manifest.json')
if ($manifests.Count -ne 1) { throw 'Missing cloudflared manifest' }
$bin=Join-Path $repo 'bin'
New-Item -ItemType Directory -Force -Path $bin | Out-Null
foreach ($name in @('tunnel-client.exe','cloudflared.exe','cloudflared-manifest.json','LICENSE','NOTICE','tunnel-client-v0.0.16-windows-amd64-licenses.txt','tunnel-client-v0.0.16-windows-amd64.spdx.json')) {
    $found=Join-Path $agent.DirectoryName $name
    if (-not (Test-Path -LiteralPath $found -PathType Leaf)) { throw ('Pinned archive asset missing: '+$name) }
    Copy-Item -LiteralPath $found -Destination (Join-Path $bin $name) -Force
    Write-Output ('VERIFIED_BUNDLED_ASSET '+$name)
}
$origin=Join-Path $bin 'tunnel-client-origin.json'
if (-not (Test-Path -LiteralPath $origin)) {
    [IO.File]::WriteAllText($origin,(ConvertTo-Json ([ordered]@{
        release='v0.0.16';platform='windows-amd64';origin=$zipUrl;
        archive_sha256=$zipHash;executable_sha256=$exeHash;executable_bytes=22591488;
        verification='Official pinned SHA-256 archive and executable validated'
    }) -Depth 3),[Text.UTF8Encoding]::new($false))
}
Write-Output 'OFFICIAL_TUNNEL_AND_COMPANION_VERIFIED'