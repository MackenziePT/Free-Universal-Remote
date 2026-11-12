# Portable workflow test. Installation, authentication, browser and supervisor are mocked.
# Client copy/hash checks and the safe status report use real temporary files.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $Root 'scripts/Bootstrap.ps1')
$Sandbox = Join-Path ([IO.Path]::GetTempPath()) ('universal-bootstrap-test-' + [guid]::NewGuid().ToString('N'))
$PreviousLocalAppData = $env:LOCALAPPDATA
$PreviousUserProfile = $env:USERPROFILE
$SyntheticSecret = 'SYNTHETIC-SECRET-NOT-A-CREDENTIAL'
$Tunnel = 'tunnel_' + ('a' * 32)

function Invoke-UniversalStep {
    param([string]$Path, [hashtable]$Arguments = @{})
    $Name = [IO.Path]::GetFileName($Path)
    $global:UniversalBootstrapTrace.Add($Name)
    if ($Name -eq $global:UniversalBootstrapFail) { throw 'SYNTHETIC-SECRET-NOT-A-CREDENTIAL' }
    if ($Name -eq 'Initialize-Tunnel.ps1' -and $Arguments.TunnelId -ne ('tunnel_' + ('a' * 32))) {
        throw 'Tunnel ID was not forwarded correctly'
    }
}
function Open-UniversalPage {
    param([string]$Url)
    $global:UniversalBootstrapTrace.Add('page:' + $Url)
}
function Start-UniversalSupervisor {
    param([string]$Root, [string]$State)
    $global:UniversalBootstrapTrace.Add('launcher')
}
function Get-UniversalStartupLink {
    return Join-Path $env:LOCALAPPDATA 'synthetic-startup\Harmony Remote MCP.lnk'
}
function Read-Host {
    param([string]$Prompt)
    $global:UniversalBootstrapTrace.Add('prompt')
    return $global:UniversalBootstrapReply
}
function Assert-Equal {
    param($Actual, $Expected, [string]$Name)
    if ($Actual -cne $Expected) { throw "FAIL: $Name; expected [$Expected], got [$Actual]" }
}

$PlatformPage = 'page:https://platform.openai.com/settings/organization/tunnels'
$PluginPage = 'page:https://chatgpt.com/plugins'
$Prefix = 'Install.ps1,Verify-Windows.ps1'
$Cases = @(
    @{name='local_only'; args=@{LocalOnly=$true}; trace=$Prefix; phase='local_ready'},
    @{name='existing_pairing'; key=$true; trace="$Prefix,Test-Tunnel.ps1,launcher,$PluginPage"; phase='remote_verification_pending'; launcher=$true},
    @{name='new_pairing'; args=@{TunnelId=$Tunnel}; trace="$Prefix,Initialize-Tunnel.ps1,launcher,$PluginPage"; phase='remote_verification_pending'; launcher=$true},
    @{name='profile_auto_discovery'; profile=$true; trace="$Prefix,Initialize-Tunnel.ps1,launcher,$PluginPage"; phase='remote_verification_pending'; launcher=$true},
    @{name='profile_conflict'; profile=$true; args=@{TunnelId=('tunnel_' + ('b' * 32))}; trace=$Prefix; phase='client_integrity'; error=$true},
    @{name='defer_authentication'; trace="$Prefix,$PlatformPage,prompt"; phase='waiting_for_tunnel_id'},
    @{name='failed_windows_acceptance'; fail='Verify-Windows.ps1'; trace=$Prefix; phase='windows_acceptance'; error=$true; local=$false},
    @{name='tampered_client'; tamper=$true; trace=$Prefix; phase='client_integrity'; error=$true},
    @{name='failed_authentication'; args=@{TunnelId=$Tunnel}; fail='Initialize-Tunnel.ps1'; trace="$Prefix,Initialize-Tunnel.ps1"; phase='local_authentication'; error=$true},
    @{name='explicit_autostart'; key=$true; args=@{EnableStartup=$true}; trace="$Prefix,Test-Tunnel.ps1,Enable-Startup.ps1,launcher,$PluginPage"; phase='remote_verification_pending'; launcher=$true; startup=$true},
    @{name='invalid_tunnel_id'; args=@{TunnelId='invalid'}; trace=''; phase='starting'; error=$true; local=$false},
    @{name='installed_rerun'; installed=$true; args=@{LocalOnly=$true}; trace='Verify-Windows.ps1'; phase='local_ready'},
    @{name='interactive_id'; reply=$Tunnel; trace="$Prefix,$PlatformPage,prompt,Initialize-Tunnel.ps1,launcher,$PluginPage"; phase='remote_verification_pending'; launcher=$true},
    @{name='doctor_failure'; key=$true; fail='Test-Tunnel.ps1'; trace="$Prefix,Test-Tunnel.ps1"; phase='existing_tunnel_diagnostic'; error=$true}
)
try {
    foreach ($Case in $Cases) {
        $env:LOCALAPPDATA = Join-Path $Sandbox $Case.name
        $env:USERPROFILE = Join-Path $env:LOCALAPPDATA 'fake-user'
        if ($Case.profile) {
            $ProfileDir = Join-Path $env:USERPROFILE '.config\tunnel-client'
            New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
            [IO.File]::WriteAllText((Join-Path $ProfileDir 'harmony-remote.yaml'),
                ("control_plane:`n  tunnel_id: '$Tunnel'`n  api_key: 'env:CONTROL_PLANE_API_KEY'`n"))
        }
        $State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
        $App = Join-Path $State 'app'
        Copy-VerifiedTunnelClient -SourceRoot $Root -DestinationRoot $App
        if ($Case.key) { [IO.File]::WriteAllText((Join-Path $State 'tunnel-key.dpapi'), 'synthetic-ciphertext-not-decrypted') }
        if ($Case.tamper) {
            $Stream = [IO.File]::OpenWrite((Join-Path $App 'bin/tunnel-client.exe'))
            try { $Stream.WriteByte(0) } finally { $Stream.Dispose() }
        }
        $global:UniversalBootstrapTrace = [Collections.Generic.List[string]]::new()
        $global:UniversalBootstrapFail = $Case.fail
        $global:UniversalBootstrapReply = [string]$Case.reply
        $Arguments = @{}
        if ($Case.args) { $Arguments = $Case.args }
        $Source = $Root
        if ($Case.installed) { $Source = $App }
        $Failed = $false
        try { Invoke-UniversalBootstrap -SourceRoot $Source @Arguments }
        catch { $Failed = $true }
        Assert-Equal $Failed ([bool]$Case.error) ($Case.name + ': exception')
        Assert-Equal ($global:UniversalBootstrapTrace -join ',') $Case.trace ($Case.name + ': side effects/order')
        $Text = [IO.File]::ReadAllText((Join-Path $State 'bootstrap-status.json'))
        $Report = $Text | ConvertFrom-Json
        Assert-Equal $Report.phase $Case.phase ($Case.name + ': report phase')
        $LocalExpected = $true
        if ($Case.ContainsKey('local')) { $LocalExpected = $Case.local }
        Assert-Equal $Report.local_mcp_verified $LocalExpected ($Case.name + ': local acceptance')
        Assert-Equal $Report.launcher_verified ([bool]$Case.launcher) ($Case.name + ': launcher status')
        Assert-Equal $Report.autostart_configured_by_bootstrap ([bool]$Case.startup) ($Case.name + ': autostart status')
        Assert-Equal $Report.remote_mcp_verified $false ($Case.name + ': no unproven remote claim')
        if ($Text.Contains($SyntheticSecret) -or $Text.Contains($Tunnel) -or $Text.Contains('synthetic-ciphertext')) {
            throw 'FAIL: private values reached safe status report'
        }
        if ($Failed -and -not $Report.failure_type) { throw 'FAIL: failure type missing' }
        Write-Output ('PASS: ' + $Case.name)
        Remove-Item -LiteralPath $env:LOCALAPPDATA -Recurse -Force
    }
    Write-Output ('PASS: ' + $Cases.Count + ' bootstrap scenarios; external actions simulated, real pinned binary integrity checked')
} finally {
    $env:LOCALAPPDATA = $PreviousLocalAppData
    $env:USERPROFILE = $PreviousUserProfile
    if (Test-Path -LiteralPath $Sandbox) { Remove-Item -LiteralPath $Sandbox -Recurse -Force }
    Remove-Variable UniversalBootstrapTrace,UniversalBootstrapFail,UniversalBootstrapReply -Scope Global -ErrorAction SilentlyContinue
}
