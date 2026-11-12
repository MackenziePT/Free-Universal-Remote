# Teste de compatibilidade local para Windows limpo, sem Python instalado.
# Nunca instala, modifica permissões, abre portas ou recolhe identificadores pessoais.
[CmdletBinding()]
param(
    [Parameter()][string]$Root = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = 'Stop'
$Report = [ordered]@{
    Product = 'Universal Remote RC5.1 Internal Security Preview'
    DateUTC = [DateTime]::UtcNow.ToString('o')
    Result = 'FAIL'
    Platform = 'unknown'
    WindowsBuild = 'unknown'
    AgentHealth = $false
    GUIHealth = $false
    UpdaterHelp = $false
    PublisherSignature = 'UNVERIFIED'
    Errors = @()
}
try {
    $Root = [IO.Path]::GetFullPath($Root)
    $OS = Get-CimInstance Win32_OperatingSystem
    $Report.Platform = $OS.OSArchitecture
    $Report.WindowsBuild = [string]$OS.BuildNumber
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows 64-bit e obrigatorio' }
    $Agent = Join-Path $Root 'Agent\UniversalRemoteAgent-Preview.exe'
    $GUI = Join-Path $Root 'GUI\UniversalRemote-Preview.exe'
    $Updater = Join-Path $Root 'Updater\UniversalRemoteUpdater-Preview.exe'
    foreach ($Item in @($Agent,$GUI,$Updater)) {
        if (-not (Test-Path -LiteralPath $Item -PathType Leaf)) {
            throw 'Componente da preview em falta.'
        }
    }
    $AgentOutput = @(& $Agent '--health-probe' 2>&1)
    $Report.AgentHealth = ($LASTEXITCODE -eq 0) -and
         ([string]::Join(' ',[string[]]$AgentOutput) -match 'UNIVERSAL_REMOTE_AGENT_HEALTH_OK')
    $HelpOutput = @(& $Updater '--help' 2>&1)
    $Report.UpdaterHelp = ($LASTEXITCODE -eq 0) -and
        ([string]::Join(' ',[string[]]$HelpOutput) -match 'recover')
    & $GUI '--self-test' 2>$null | Out-Null
    $Report.GUIHealth = ($LASTEXITCODE -eq 0)
    if (-not (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue)) {
        $SecurityModule = Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1'
        if (Test-Path -LiteralPath $SecurityModule) {
            Import-Module -Name $SecurityModule -ErrorAction SilentlyContinue
        }
    }
    if (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue) {
        $Authenticode = Get-AuthenticodeSignature -LiteralPath $Agent
        $Report.PublisherSignature = [string]$Authenticode.Status
    } else {
        $Report.PublisherSignature = 'UNAVAILABLE'
    }
    if (-not $Report.AgentHealth) { $Report.Errors += 'Falha do agente local' }
    if (-not $Report.UpdaterHelp) { $Report.Errors += 'Falha do atualizador' }
    if (-not $Report.GUIHealth) { $Report.Errors += 'Falha da GUI' }
    if ($Report.AgentHealth -and $Report.UpdaterHelp -and $Report.GUIHealth) {
        $Report.Result='LOCAL_PASS_UNCERTIFIED'
    }
} catch {
    $Report.Errors += ('Erro: '+$_.Exception.GetType().Name)
}
$Report | ConvertTo-Json -Depth 4
if ($Report.Result -ne 'LOCAL_PASS_UNCERTIFIED') { exit 1 }
exit 0
