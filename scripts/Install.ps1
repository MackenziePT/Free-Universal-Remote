# Non-admin, staged and rollback-capable installer.
# Keeps the existing installation untouched until Python, dependencies, config
# and the MCP JSON-RPC handshake pass in a separate staging directory.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Tunnel-Client.ps1')

# Directory.Move renames within a single NTFS volume atomically. Move-Item
# can perform partial, recursive moves of a virtualenv before a file-lock error.
function Move-AtomicDirectory {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$From,
          [Parameter(Mandatory=$true)][string]$To)
    $ParentFrom = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($From))
    $ParentTo = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($To))
    if ($ParentFrom -ine $ParentTo) { throw 'Atomic directory switch requires the same volume' }
    for ($Attempt = 1; $Attempt -le 8; $Attempt++) {
        try {
            [IO.Directory]::Move($From, $To)
            return
        } catch [IO.IOException] {
            if ($Attempt -eq 8) { throw }
            Start-Sleep -Milliseconds (300 * $Attempt)
        } catch [UnauthorizedAccessException] {
            if ($Attempt -eq 8) { throw }
            Start-Sleep -Milliseconds (300 * $Attempt)
        }
    }
}

$InstallMutex = [System.Threading.Mutex]::new($false, 'Local\HarmonyRemoteMCP')
$Locked = $false
$Stage = $null
$Prior = $null
try {
    try { $Locked = $InstallMutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $Locked = $true }
    if (-not $Locked) { throw 'Stop the active MCP tunnel with Stop-Tunnel.ps1 before updating.' }

    $Source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
    $Destination = Join-Path $State 'app'
    if ($Source.TrimEnd('\') -ieq $Destination.TrimEnd('\')) {
        throw 'Run from the extracted release, not the installed app.'
    }
    # The file list must match the audited local release before any staging.
    $Verifier = Join-Path $Source 'tools\verify_release.py'
    if (-not (Test-Path -LiteralPath $Verifier -PathType Leaf)) { throw 'Release integrity verifier missing.' }
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 $Verifier }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python $Verifier }
    else { throw 'Python 3.11+ is needed to verify the release.' }
    if ($LASTEXITCODE -ne 0) { throw 'Source release failed SHA-256 integrity verification; installation refused.' }
    New-Item -ItemType Directory -Force -Path $State | Out-Null
    $Id = [guid]::NewGuid().ToString('N')
    $Stage = Join-Path $State "app.stage.$Id"
    $Prior = Join-Path $State "app.previous.$Id"
    New-Item -ItemType Directory -Force -Path $Stage | Out-Null

    # Copy source but never execute downloaded *.pyc files or bundled caches.
    $Names = @('server.py','launch_server.py','install_check.py','initialize_tunnel.py','remote_core.py','desktop_unicode.py','requirements.txt',
               'config.example.json','smoke_test.py','windows_verify.py','operation_journal.py','process_runner.py',
               'native_files.py','native_jobs.py','native_windows.py','universal_remote_ui.py',
               'README.md','START-HERE-PT.md','AUDIT.md','RELEASE_NOTES.md','TEST_REPORT.md','PRODUCT_ARCHITECTURE_AND_PLAN.md','RC5_0_VERIFICATION.md','RC4_1_VERIFICATION.md','RC4_2_VERIFICATION.md','RC4_3_VERIFICATION.md','RC4_4_VERIFICATION.md','RC4_5_VERIFICATION.md','RC4_6_VERIFICATION.md','RC4_7_VERIFICATION.md','RC4_8_VERIFICATION.md','RC4_6_FINAL_VALIDATION_2026-11-10.md','INICIAR.cmd','ABRIR-UNIVERSAL-REMOTE.cmd','AUTORIZAR-MCP-60MIN.cmd','REVOGAR-MCP.cmd',
               'REPAIR_REPORT_2026-10-22.md','CORRIGIR-E-LIGAR-UNIVERSAL-REMOTE.cmd',
               'KEY_INPUT_REPORT_2026-10-22.md','COLAR-CHAVE-E-LIGAR.cmd')
    foreach ($Name in $Names) {
        $From = Join-Path $Source $Name
        if (-not (Test-Path -LiteralPath $From)) { throw "Release missing $Name" }
        Copy-Item -LiteralPath $From -Destination (Join-Path $Stage $Name)
    }
    Copy-Item -LiteralPath (Join-Path $Source 'scripts') -Destination $Stage -Recurse
    Copy-Item -LiteralPath (Join-Path $Source 'tests') -Destination $Stage -Recurse
    Copy-Item -LiteralPath (Join-Path $Source 'tools') -Destination $Stage -Recurse
    New-Item -ItemType Directory -Force -Path (Join-Path $Stage 'bin') | Out-Null
    $ConfigOld = Join-Path $Destination 'config.json'
    if (Test-Path -LiteralPath $ConfigOld) {
        Copy-Item -LiteralPath $ConfigOld -Destination (Join-Path $Stage 'config.json')
    } else {
        Copy-Item -LiteralPath (Join-Path $Stage 'config.example.json') -Destination (Join-Path $Stage 'config.json')
    }
    # Install the pinned release client; the old client stays in app.previous.*.
    Copy-VerifiedTunnelClient -SourceRoot $Source -DestinationRoot $Stage

    # Isolate venv creation, pip, tests and MCP child processes in a second
    # PowerShell process. When it exits, it cannot retain handles inside Stage.
    # This prevents Windows sharing violations during atomic directory rename.
    $PrepScript = Join-Path $Source 'scripts\Prepare-Stage.ps1'
    $HostExe = if ($PSVersionTable.PSEdition -eq 'Core') { Join-Path $PSHOME 'pwsh.exe' } else { Join-Path $PSHOME 'powershell.exe' }
    $PrepArgs = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $PrepScript + '" -Stage "' + $Stage + '"'
    $Output = Join-Path $State ('logs\prepare-' + $Id + '.stdout.txt')
    $Errors = Join-Path $State ('logs\prepare-' + $Id + '.stderr.txt')
    New-Item -ItemType Directory -Path (Join-Path $State 'logs') -Force | Out-Null
    $Prep = Start-Process -FilePath $HostExe -ArgumentList $PrepArgs -PassThru -Wait -RedirectStandardOutput $Output -RedirectStandardError $Errors
    if ($Prep.ExitCode -ne 0) {
        Write-Warning ("Preparation failed; see logs at {0}, {1}" -f $Output, $Errors)
        throw 'Staging dependencies, tests or MCP handshake failed; original app unchanged.'
    }
    Write-Host ('Preparation completed in separate process; details: ' + $Output)

    $MovedOld = $false
    if (Test-Path -LiteralPath $Destination) {
        Move-AtomicDirectory -From $Destination -To $Prior
        $MovedOld = $true
    }
    try {
        Move-AtomicDirectory -From $Stage -To $Destination
        $Stage = $null
        # Test the final installed location too; the tunnel will use this location.
        $Python = Join-Path $Destination '.venv\Scripts\python.exe'
        $OldConfigEnv = $env:HARMONY_MCP_CONFIG
        try {
            $env:HARMONY_MCP_CONFIG = Join-Path $Destination 'config.json'
            & $Python (Join-Path $Destination 'smoke_test.py')
            if ($LASTEXITCODE -ne 0) { throw 'Installed-path MCP handshake failed.' }
        } finally { $env:HARMONY_MCP_CONFIG = $OldConfigEnv }
    } catch {
        if (Test-Path -LiteralPath $Destination) {
            $Broken = Join-Path $State "app.failed.$Id"
            Move-AtomicDirectory -From $Destination -To $Broken
        }
        if ($MovedOld -and (Test-Path -LiteralPath $Prior)) {
            Move-AtomicDirectory -From $Prior -To $Destination
        }
        throw
    }
    Write-Host "MCP installed and locally verified: $Destination" -ForegroundColor Green
    if ($MovedOld) { Write-Host "Prior version saved: $Prior" }
    Write-Host 'Run scripts\Verify-Windows.ps1. Tunnel pairing is a separate step.'
} finally {
    if ($Stage -and (Test-Path -LiteralPath $Stage)) {
        Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($Locked) { $InstallMutex.ReleaseMutex() }
    $InstallMutex.Dispose()
}
