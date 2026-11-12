# Standalone local entry point. No pre-existing remote-control agent is required.
[CmdletBinding()]
param([switch]$LocalOnly, [string]$TunnelId = '', [switch]$EnableStartup)
. (Join-Path $PSScriptRoot 'Tunnel-Client.ps1')
. (Join-Path $PSScriptRoot 'Tunnel-Identity.ps1')

function Get-UniversalExistingTunnelId {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    $File = Get-Item -LiteralPath $Path -ErrorAction Stop
    if ($File.Length -gt 16384 -or $File.Length -lt 20) { throw 'Invalid local tunnel profile size.' }
    $Text = [IO.File]::ReadAllText($File.FullName)
    $Found = [regex]::Matches($Text, '(?m)^[ \t]*tunnel_id:[ \t]*["'']?(tunnel_[0-9a-f]{32})["'']?[ \t]*$')
    if ($Found.Count -ne 1) { throw 'Missing or ambiguous tunnel ID in existing profile.' }
    if ($Text -notmatch '(?m)^[ \t]*api_key:[ \t]*["'']?env:CONTROL_PLANE_API_KEY["'']?[ \t]*$') {
        throw 'Existing tunnel profile must reference the runtime key via environment variable.'
    }
    return $Found[0].Groups[1].Value
}

function Invoke-UniversalStep {
    param([string]$Path, [hashtable]$Arguments = @{})
    & $Path @Arguments
}

function Open-UniversalPage {
    param([string]$Url)
    # Only these two fixed setup surfaces are used by this workflow.
    if ($Url -notin @('https://platform.openai.com/settings/organization/tunnels', 'https://chatgpt.com/plugins')) {
        throw 'Unexpected setup page'
    }
    Start-Process $Url | Out-Null
}

function Get-UniversalStartupLink {
    $Folder = [Environment]::GetFolderPath('Startup')
    if ([string]::IsNullOrWhiteSpace($Folder)) { throw 'User Startup folder unavailable' }
    return Join-Path $Folder 'Harmony Remote MCP.lnk'
}

function Start-UniversalSupervisor {
    param([string]$Root, [string]$State)
    . (Join-Path $Root 'scripts\Tunnel-Identity.ps1')
    $Launcher = Join-Path $Root 'scripts\Start-Tunnel.ps1'
    $Record = Join-Path $State 'tunnel-launcher.pid'
    try {
        if (Get-VerifiedTunnelIdentity -Path $Record -Launcher $Launcher) { return }
    } catch { }
    . (Join-Path $Root 'scripts\Resolve-PowerShell.ps1')
    $PowerShell = Resolve-UniversalPowerShell -NoDownload
    $Arguments = '-NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "' + $Launcher + '"'
    $Started = Start-Process -FilePath $PowerShell -ArgumentList $Arguments -WorkingDirectory $Root -PassThru
    $Wait = [Diagnostics.Stopwatch]::StartNew()
    while ($Wait.Elapsed.TotalSeconds -lt 10) {
        if ($Started.HasExited) { throw 'Tunnel launcher exited before recording its identity' }
        try {
            if (Get-VerifiedTunnelIdentity -Path $Record -Launcher $Launcher) { return }
        } catch { }
        Start-Sleep -Milliseconds 200
    }
    throw 'Launcher identity not confirmed. Inspect the separate tunnel window; close any older tunnel before retrying.'
}

function Invoke-UniversalBootstrap {
    param([string]$SourceRoot, [switch]$LocalOnly, [string]$TunnelId = '', [switch]$EnableStartup)
    $ErrorActionPreference = 'Stop'
    Write-Host 'Universal Remote MCP 1.0.0-rc5.1-dev / standalone-9' -ForegroundColor Cyan
    $State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
    $App = Join-Path $State 'app'
    $Secret = Join-Path $State 'tunnel-key.dpapi'
    New-Item -ItemType Directory -Path $State -Force | Out-Null
    $Report = [ordered]@{ schema=1; release='1.0.0-rc5.1-dev'; setup_revision='standalone-9';
        updated_utc=''; phase='starting'; powershell_version=$PSVersionTable.PSVersion.ToString();
        powershell_edition=[string]$PSVersionTable.PSEdition;
        local_mcp_verified=$false; launcher_verified=$false;
        remote_mcp_verified=$false; autostart_configured_by_bootstrap=$false; failure_type=$null }
    $ReportPath = Join-Path $State 'bootstrap-status.json'
    function Save-Status {
        $Report.updated_utc = [DateTime]::UtcNow.ToString('o')
        [IO.File]::WriteAllText($ReportPath, ($Report | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    }
    Save-Status
    try {
        if ($TunnelId -and $TunnelId -notmatch '^tunnel_[0-9a-f]{32}$') { throw 'Invalid tunnel ID format' }
        if ([IO.Path]::GetFullPath($SourceRoot).TrimEnd('\','/') -ine [IO.Path]::GetFullPath($App).TrimEnd('\','/')) {
            $Report.phase = 'installation'; Save-Status
            Write-Host '1/4: Install/update with backup, staging and MCP checks.' -ForegroundColor Cyan
            Invoke-UniversalStep -Path (Join-Path $SourceRoot 'scripts\Install.ps1')
        }
        $Report.phase = 'windows_acceptance'; Save-Status
        Write-Host '2/4: Local MCP, policy and Windows acceptance.' -ForegroundColor Cyan
        Invoke-UniversalStep -Path (Join-Path $App 'scripts\Verify-Windows.ps1')
        $Report.local_mcp_verified = $true
        $Report.phase = 'local_ready'; Save-Status
        if ($LocalOnly) {
            Write-Host 'Local checks passed. Tunnel and remote MCP are not yet verified.'
            return
        }
        $Report.phase = 'client_integrity'; Save-Status
        Assert-VerifiedTunnelClient -Root $App
        Write-Host '3/4: Private Secure MCP Tunnel setup. Credentials stay on this Windows account.' -ForegroundColor Cyan
        $ProfilePath = Join-Path $env:USERPROFILE '.config\tunnel-client\harmony-remote.yaml'
        $ExistingTunnelId = Get-UniversalExistingTunnelId -Path $ProfilePath
        if ($TunnelId -and $ExistingTunnelId -and $TunnelId -cne $ExistingTunnelId) {
            throw 'The supplied tunnel ID differs from the configured private profile.'
        }
        $EffectiveTunnelId = if ($TunnelId) { $TunnelId } else { $ExistingTunnelId }
        $SecretExists = Test-Path -LiteralPath $Secret -PathType Leaf
        $ExistingLauncher = $null
        if ($SecretExists) {
            $Record = Join-Path $State 'tunnel-launcher.pid'
            $Launcher = Join-Path $App 'scripts\Start-Tunnel.ps1'
            $ExistingLauncher = Get-VerifiedTunnelIdentity -Path $Record -Launcher $Launcher
        }
        if (-not $SecretExists) {
            if (-not $EffectiveTunnelId) {
                $Report.phase = 'waiting_for_tunnel_id'; Save-Status
                Write-Host 'Create/select your private tunnel in Platform. The account may require authentication or tunnel permissions.'
                Open-UniversalPage 'https://platform.openai.com/settings/organization/tunnels'
                $EffectiveTunnelId = Read-Host 'Paste tunnel_ID here, or press Enter to stop after local setup'
                if (-not $EffectiveTunnelId) { return }
                if ($EffectiveTunnelId -notmatch '^tunnel_[0-9a-f]{32}$') { throw 'Invalid tunnel ID format; no key requested' }
            }
            $Report.phase = 'local_authentication'; Save-Status
            Invoke-UniversalStep -Path (Join-Path $App 'scripts\Initialize-Tunnel.ps1') -Arguments @{TunnelId=$EffectiveTunnelId}
        } elseif ($ExistingLauncher) {
            $Report.phase = 'existing_tunnel_diagnostic'; Save-Status
            try {
                $Ready = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/readyz' -TimeoutSec 4 -ErrorAction Stop
                if ($Ready.StatusCode -ne 200 -or $Ready.Content.Trim() -cne 'ready') {
                    throw 'Unexpected tunnel readiness response'
                }
                Write-Host 'Existing verified Universal Remote tunnel is ready. Reusing it.' -ForegroundColor Green
            } catch { throw 'Own verified tunnel is running but not ready; resolve it before restarting' }
        } else {
            $Report.phase = 'existing_tunnel_diagnostic'; Save-Status
            Invoke-UniversalStep -Path (Join-Path $App 'scripts\Test-Tunnel.ps1')
        }
        if ($EnableStartup) {
            $Report.phase = 'configuring_startup'; Save-Status
            $Link = Get-UniversalStartupLink
            if (Test-Path -LiteralPath $Link -PathType Leaf) {
                Invoke-UniversalStep -Path (Join-Path $App 'scripts\Test-Startup.ps1')
            } else {
                if ($ExistingLauncher) { throw 'Stop the running tunnel before first enabling auto-start' }
                Invoke-UniversalStep -Path (Join-Path $App 'scripts\Enable-Startup.ps1')
            }
            $Report.autostart_configured_by_bootstrap = $true
        }
        $Report.phase = 'launching_supervisor'; Save-Status
        Write-Host '4/4: Start the local tunnel supervisor and open ChatGPT plugin setup.' -ForegroundColor Cyan
        Start-UniversalSupervisor -Root $App -State $State
        $Report.launcher_verified = $true
        $Report.phase = 'remote_verification_pending'; Save-Status
        Open-UniversalPage 'https://chatgpt.com/plugins'
        Write-Host 'Keep the separate tunnel window running. Add the custom MCP plugin using Connection = Tunnel.'
        Write-Host 'Select the private tunnel, then enable the plugin in the conversation and request ping and agent_policy.'
        Write-Host 'A running local launcher does not prove remote connection. No write/shell/input grants were enabled.'
    } catch {
        $Report.failure_type = $_.Exception.GetType().Name
        Save-Status
        Write-Host ('Setup stopped at stage: ' + $Report.phase) -ForegroundColor Yellow
        Write-Host ('Safe status file: ' + $ReportPath)
        throw
    } finally {
        Save-Status
        Write-Host ('Status without credentials: ' + $ReportPath)
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    $ErrorActionPreference = 'Stop'
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Run INICIAR.cmd on the target Windows PC' }
    if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64' -and $env:PROCESSOR_ARCHITEW6432 -ne 'AMD64') {
        throw 'This standalone package includes the official Windows x64 tunnel client'
    }
    $Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    Invoke-UniversalBootstrap -SourceRoot $Root -LocalOnly:$LocalOnly -TunnelId $TunnelId -EnableStartup:$EnableStartup
}
