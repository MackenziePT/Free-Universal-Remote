# Universal Remote - Windows independent acceptance. Read-only except JSON report.
# NO installer execution, NO security protection changes, NO local machine identifiers.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter()][string]$InstallDir = '',
    [Parameter()][string]$ExpectedSHA256 = ''
)
$ErrorActionPreference = 'Stop'
function Digest256([string]$path) {
    $hash=[System.Security.Cryptography.SHA256]::Create()
    try {
        $stream=[System.IO.File]::OpenRead($path)
        try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
        finally { $stream.Dispose() }
    } finally { $hash.Dispose() }
}
function SafeProbe([string]$exe,[string[]]$arguments,[string]$expected) {
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { return 'MISSING' }
    try {
        $psi=New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName=$exe
        $psi.Arguments=($arguments -join ' ')
        $psi.UseShellExecute=$false
        $psi.CreateNoWindow=$true
        $psi.RedirectStandardOutput=$true
        $psi.RedirectStandardError=$true
        $proc=New-Object System.Diagnostics.Process
        $proc.StartInfo=$psi
        $null=$proc.Start()
        if(-not $proc.WaitForExit(60000)) {
            try { $proc.Kill() } catch {}
            return 'TIMEOUT'
        }
        $stdout=$proc.StandardOutput.ReadToEnd()
        if($proc.ExitCode -eq 0 -and (!$expected -or $stdout.Contains($expected))) { return 'PASS' }
        return ('FAIL_' + $proc.ExitCode)
    } catch {
        return ('ERROR_' + $_.Exception.GetType().Name)
    }
}
$record=[ordered]@{
    Product='Universal Remote'
    TestType='Uncertified independent PC acceptance'
    TimestampUtc=[DateTime]::UtcNow.ToString('o')
    Platform='Windows'
    OSBuild='UNKNOWN'
    Architecture='UNKNOWN'
    InstallerFound=$false
    InstallerSHA256=''
    ExpectedHashMatches='UNVERIFIED'
    InstallerAuthenticode='UNVERIFIED'
    SignatureGate='NOT_CERTIFIED'
    AgentHealth='NOT_INSTALLED'
    GUIHealth='NOT_INSTALLED'
    UpdaterHelp='NOT_INSTALLED'
}
try {
    $os=Get-CimInstance -ClassName Win32_OperatingSystem
    $record.OSBuild=[string]$os.BuildNumber
    $record.Architecture=[string]$os.OSArchitecture
    if(-not (Test-Path -LiteralPath $Installer -PathType Leaf)){
        throw 'Installer not found'
    }
    $record.InstallerFound=$true
    $record.InstallerSHA256=Digest256 $Installer
    if($ExpectedSHA256) {
        $record.ExpectedHashMatches=($record.InstallerSHA256 -eq $ExpectedSHA256.ToLowerInvariant())
    }
    $sigCmd=Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue
    if(-not $sigCmd){
        $module=Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1'
        if(Test-Path $module){ Import-Module $module -ErrorAction SilentlyContinue }
    }
    if(Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue) {
        $record.InstallerAuthenticode=[string](Get-AuthenticodeSignature -LiteralPath $Installer).Status
    }
    if($InstallDir -and (Test-Path -LiteralPath $InstallDir -PathType Container)){
        $record.AgentHealth=SafeProbe (Join-Path $InstallDir 'Agent\UniversalRemoteAgent-Preview.exe') @('--health-probe') 'UNIVERSAL_REMOTE_AGENT_HEALTH_OK'
        $record.GUIHealth=SafeProbe (Join-Path $InstallDir 'GUI\UniversalRemote-Preview.exe') @('--self-test') ''
        $record.UpdaterHelp=SafeProbe (Join-Path $InstallDir 'Updater\UniversalRemoteUpdater-Preview.exe') @('--help') 'recover'
    }
} catch {
    $record.ErrorType=$_.Exception.GetType().Name
}
$output=Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'Independent-PC-QA-Result.json'
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $output -Encoding UTF8
Write-Output ('QA_REPORT_WRITTEN '+$output)
$record | ConvertTo-Json -Depth 4
$badProbes=@($record.AgentHealth,$record.GUIHealth,$record.UpdaterHelp) -match '^(FAIL|ERROR|TIMEOUT|MISSING)'
if(-not $record.InstallerFound -or $record.ExpectedHashMatches -eq $false -or @($badProbes).Count -gt 0) { exit 1 }
if($InstallDir -and @($record.AgentHealth,$record.GUIHealth,$record.UpdaterHelp) -contains 'NOT_INSTALLED') { exit 2 }
exit 0
