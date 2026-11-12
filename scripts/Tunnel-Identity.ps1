# Local process identity; never output command lines or credentials.
function Get-TunnelCommandHash {
    param([Parameter(Mandatory=$true)][string]$CommandLine)
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($Hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($CommandLine))).Replace('-', '').ToLowerInvariant() }
    finally { $Hasher.Dispose() }
}

function Save-TunnelIdentity {
    param([string]$Path, [string]$Launcher, [int]$ProcessId)
    $Details = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId"
    if (-not $Details -or -not $Details.CreationDate -or -not $Details.CommandLine) { throw 'Cannot establish launcher process identity' }
    $Record = @{ schema=1; pid=$ProcessId; launcher=[IO.Path]::GetFullPath($Launcher);
        started_ticks=[string]$Details.CreationDate.ToUniversalTime().Ticks;
        command_sha256=(Get-TunnelCommandHash $Details.CommandLine) }
    $Temporary = $Path + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($Temporary, ($Record | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $Temporary -Destination $Path -Force
    } finally { Remove-Item -LiteralPath $Temporary -Force -ErrorAction SilentlyContinue }
}

function Get-VerifiedTunnelIdentity {
    param([string]$Path, [string]$Launcher)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    if ((Get-Item -LiteralPath $Path).Length -gt 8192) { throw 'Invalid launcher identity record' }
    $Record = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    # RC3 stored only a PID. Refuse automatic termination based on an old record.
    if ($Record.schema -ne 1 -or -not ($Record.pid -is [int] -or $Record.pid -is [long]) -or $Record.pid -le 0 -or $Record.pid -gt [int]::MaxValue -or
        $Record.launcher -ne [IO.Path]::GetFullPath($Launcher) -or
        $Record.command_sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Missing or legacy launcher identity; termination refused' }
    $Details = Get-CimInstance Win32_Process -Filter "ProcessId=$($Record.pid)"
    if (-not $Details) { return $null }
    if ($Details.Name -notmatch '^(powershell|pwsh)(\.exe)?$' -or
        -not $Details.CreationDate -or -not $Details.CommandLine -or
        [string]$Details.CreationDate.ToUniversalTime().Ticks -ne $Record.started_ticks -or
        (Get-TunnelCommandHash $Details.CommandLine) -ne $Record.command_sha256 -or
        $Details.CommandLine.IndexOf($Record.launcher, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw 'Launcher PID was reused or identity changed; termination refused'
    }
    return $Details
}

# A 200 response alone does not establish who owns the local readiness port.
# Check that the loopback listener belongs to the verified supervisor's child.
function Assert-OwnedHealthListener {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)]$Owner, [int]$Port=8080)
    if (-not $Owner -or [int]$Owner.ProcessId -le 0 -or -not $Owner.CreationDate) {
        throw 'Verified launcher identity is required to validate health listener ownership.'
    }
    $Connections = @(Get-NetTCPConnection -LocalPort $Port -ErrorAction Stop |
        Where-Object { $_.RemotePort -eq 0 })
    if ($Connections.Count -ne 1 -or $Connections[0].LocalAddress -cne '127.0.0.1') {
        throw 'Expected exactly one private IPv4 loopback health listener.'
    }
    $ClientPid = [int]$Connections[0].OwningProcess
    if ($ClientPid -le 0) { throw 'Health listener owner PID is invalid.' }
    $Client = Get-CimInstance Win32_Process -Filter "ProcessId=$ClientPid"
    if (-not $Client -or $Client.Name -ine 'tunnel-client.exe' -or
        [int]$Client.ParentProcessId -ne [int]$Owner.ProcessId -or
        -not $Client.CreationDate -or
        $Client.CreationDate.ToUniversalTime() -lt $Owner.CreationDate.ToUniversalTime()) {
        throw 'Health listener is not owned by the verified tunnel supervisor.'
    }
}
