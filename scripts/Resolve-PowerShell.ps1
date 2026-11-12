# Universal Remote: find current stable pwsh, or provision a verified portable copy.
# No system-wide installation, admin privilege, registry mutation or PATH edits.
# Windows PowerShell 5.1 may execute THIS bootstrap only.
Set-StrictMode -Version Latest

function Get-UniversalPwshVersion {
    param([Parameter(Mandatory=$true)][string]$Executable)
    try {
        if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
        # OS file metadata avoids spawning one new PowerShell process per candidate.
        $Details = [Diagnostics.FileVersionInfo]::GetVersionInfo($Executable)
        if ($Details.FileMajorPart -lt 7 -or $Details.FileMinorPart -lt 0 -or $Details.FileBuildPart -lt 0) {
            return $null
        }
        if ([string]$Details.ProductVersion -match '(?i)(preview|rc\d|alpha|beta)') { return $null }
        # Cached and PATH-discovered shells also require a genuine Microsoft signature.
        if ($PSVersionTable.PSEdition -eq 'Desktop') {
            Import-Module Microsoft.PowerShell.Security -RequiredVersion 3.0.0.0 -ErrorAction Stop
        } else {
            Import-Module Microsoft.PowerShell.Security -ErrorAction Stop
        }
        $Signature = Get-AuthenticodeSignature -FilePath $Executable
        if ($Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate -or
            $Signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Microsoft Corporation(?:,|$)') {
            return $null
        }
        return [version]('{0}.{1}.{2}' -f $Details.FileMajorPart,$Details.FileMinorPart,$Details.FileBuildPart)
    } catch {
        return $null
    }
}

function Install-UniversalPortablePowerShell {
    [CmdletBinding()]
    param([version]$MinimumVersion = [version]'7.4.0', [string]$ExistingPath = '')
    if ($PSVersionTable.PSEdition -eq 'Core' -and -not $IsWindows) {
        throw 'Portable PowerShell provisioning is Windows-only'
    }
    if (-not ($env:LOCALAPPDATA)) { throw 'LOCALAPPDATA is unavailable' }
    $Architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    if ($Architecture -notin @('x64','arm64','x86')) { throw "Unsupported architecture: $Architecture" }
    $Base = Join-Path $env:LOCALAPPDATA 'UniversalRemote\runtime\powershell'
    $Api = 'https://api.github.com/repos/PowerShell/PowerShell/releases/latest'
    $Headers = @{ 'User-Agent' = 'UniversalRemote-Installer/0.1'; 'Accept' = 'application/vnd.github+json' }
    Write-Host 'A obter metadados da versão estável do PowerShell diretamente da Microsoft/GitHub...' -ForegroundColor Cyan
    $Release = Invoke-RestMethod -Uri $Api -Headers $Headers -TimeoutSec 25 -ErrorAction Stop
    if ([string]$Release.tag_name -notmatch '^v(\d+\.\d+\.\d+)$' -or $Release.prerelease -or $Release.draft) {
        throw 'Untrusted, preview or malformed PowerShell release metadata'
    }
    $Version = [version]$Matches[1]
    if ($Version -lt $MinimumVersion) { throw 'Latest PowerShell is below minimum required version' }
    # Never reinstall an equal version or downgrade a newer Microsoft-signed runtime.
    if ($ExistingPath) {
        $CurrentVersion = Get-UniversalPwshVersion -Executable $ExistingPath
        if ($CurrentVersion) {
            if ($CurrentVersion -ge $Version) {
                Write-Host ('PowerShell ' + $CurrentVersion + ' já está atualizado; sem download necessário.') -ForegroundColor Green
                return $ExistingPath
            }
        }
    }
    $Name = 'PowerShell-{0}-win-{1}.zip' -f $Version, $Architecture
    $MatchesFound = @($Release.assets | Where-Object { $_.name -ceq $Name })
    if ($MatchesFound.Count -ne 1) { throw 'Expected official PowerShell release ZIP not found' }
    $Asset = $MatchesFound[0]
    $ExpectedDigest = [string]$Asset.digest
    if ($ExpectedDigest -notmatch '^sha256:([0-9a-fA-F]{64})$') {
        throw 'Release asset lacks verifiable SHA-256 metadata; refusing download'
    }
    $Expected = $Matches[1].ToLowerInvariant()
    $AllowedPrefix = 'https://github.com/PowerShell/PowerShell/releases/download/'
    $Url = [string]$Asset.browser_download_url
    if (-not $Url.StartsWith($AllowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'PowerShell asset download host/path not approved'
    }
    $Destination = Join-Path $Base ('{0}-{1}' -f $Version,$Architecture)
    $Existing = Join-Path $Destination 'pwsh.exe'
    if ((Get-UniversalPwshVersion -Executable $Existing) -ge $MinimumVersion) {
        return $Existing
    }
    New-Item -ItemType Directory -Force -Path $Base | Out-Null
    $Temp = Join-Path $Base ('stage-' + [guid]::NewGuid().ToString('N'))
    $Archive = Join-Path $Temp $Name
    $Extracted = Join-Path $Temp 'extracted'
    New-Item -ItemType Directory -Path $Temp,$Extracted -Force | Out-Null
    try {
        Write-Host 'A descarregar PowerShell para a pasta privada da aplicação...' -ForegroundColor Cyan
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Archive -TimeoutSec 240 -ErrorAction Stop
        $Hasher = [Security.Cryptography.SHA256]::Create()
        try {
            $Stream = [IO.File]::OpenRead($Archive)
            try { $Actual = ([BitConverter]::ToString($Hasher.ComputeHash($Stream))).Replace('-','').ToLowerInvariant() }
            finally { $Stream.Dispose() }
        } finally { $Hasher.Dispose() }
        if ($Actual -cne $Expected) { throw 'PowerShell downloaded archive SHA-256 mismatch' }
        Expand-Archive -LiteralPath $Archive -DestinationPath $Extracted -Force -ErrorAction Stop
        $NewExecutable = Join-Path $Extracted 'pwsh.exe'
        if (-not (Test-Path -LiteralPath $NewExecutable -PathType Leaf)) { throw 'Extracted PowerShell is missing pwsh.exe' }
        # Windows PowerShell 5.1 may inherit PS7 PSModulePath, making automatic
        # module loading fail. Import the matching signed core module explicitly.
        if ($PSVersionTable.PSEdition -eq "Desktop") {
            Import-Module Microsoft.PowerShell.Security -RequiredVersion 3.0.0.0 -ErrorAction Stop
        } else {
            Import-Module Microsoft.PowerShell.Security -ErrorAction Stop
        }
        $Signature = Get-AuthenticodeSignature -FilePath $NewExecutable
        if ($Signature.Status -ne 'Valid' -or
            -not $Signature.SignerCertificate -or
            $Signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Microsoft Corporation(?:,|$)') {
            throw 'PowerShell executable is not Authenticode-signed by Microsoft Corporation'
        }
        $ActualVersion = Get-UniversalPwshVersion -Executable $NewExecutable
        if (-not $ActualVersion -or $ActualVersion -ne $Version) {
            throw 'Extracted PowerShell version does not match the verified release'
        }
        if (Test-Path -LiteralPath $Destination) {
            $Check = Get-UniversalPwshVersion -Executable (Join-Path $Destination 'pwsh.exe')
            if ($Check -lt $MinimumVersion) { throw 'Conflicting runtime folder; manual repair is required' }
        } else {
            [IO.Directory]::Move($Extracted, $Destination)
        }
        Write-Host ('PowerShell ' + $Version + ' preparado para o Universal Remote sem privilégios de administrador.') -ForegroundColor Green
        return (Join-Path $Destination 'pwsh.exe')
    } finally {
        Remove-Item -LiteralPath $Temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Resolve-UniversalPowerShell {
    [CmdletBinding()]
    param([switch]$NoDownload, [switch]$PreferLatest, [version]$MinimumVersion = [version]'7.4.0')
    $Candidates = New-Object 'System.Collections.Generic.List[string]'
    # User-private runtime, standard installation, WindowsApps and PATH candidates.
    if ($env:LOCALAPPDATA) {
        $runtime = Join-Path $env:LOCALAPPDATA 'UniversalRemote\runtime\powershell'
        if (Test-Path -LiteralPath $runtime -PathType Container) {
            Get-ChildItem -LiteralPath $runtime -Directory -ErrorAction SilentlyContinue |
                ForEach-Object { $Candidates.Add((Join-Path $_.FullName 'pwsh.exe')) }
        }
    }
    if ($env:ProgramFiles) {
        $InstallRoot = Join-Path $env:ProgramFiles 'PowerShell'
        if (Test-Path -LiteralPath $InstallRoot -PathType Container) {
            Get-ChildItem -LiteralPath $InstallRoot -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^\d+$' -and [int]$_.Name -ge 7 } |
                ForEach-Object { $Candidates.Add((Join-Path $_.FullName 'pwsh.exe')) }
        }
    }
    $AllCommands = @(Get-Command pwsh.exe -All -ErrorAction SilentlyContinue)
    foreach ($Command in $AllCommands) {
        if ($Command.Source -and [IO.Path]::IsPathRooted([string]$Command.Source)) {
            $Candidates.Add([string]$Command.Source)
        }
    }
    $BestPath = $null
    $BestVersion = [version]'0.0'
    foreach ($Candidate in ($Candidates | Select-Object -Unique)) {
        $Version = Get-UniversalPwshVersion -Executable $Candidate
        if ($Version -and $Version -ge $MinimumVersion -and $Version -gt $BestVersion) {
            $BestPath = $Candidate
            $BestVersion = $Version
        }
    }
    if ($BestPath -and (-not $PreferLatest -or $NoDownload)) { return $BestPath }
    if ($NoDownload) { throw 'PowerShell 7+ não encontrado; descarregamento desativado neste teste' }
    try {
        return Install-UniversalPortablePowerShell -MinimumVersion $MinimumVersion -ExistingPath $BestPath
    } catch {
        if ($BestPath) {
            Write-Warning 'Não foi possível obter a versão mais recente; foi conservada a instalação atual verificada'
            return $BestPath
        }
        throw
    }
}
