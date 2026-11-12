# Windows App Certification Kit desktop-install acceptance. DESTRUCTIVE on VM.
# Never run on the owner's live ASUS/RC5.0. Must use a clean disposable VM.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ReportDirectory,
    [switch]$ConfirmCleanDisposableVM
)
$ErrorActionPreference='Stop'
if(-not $ConfirmCleanDisposableVM) {
    throw 'WACK_BLOCKED: explicit confirmation of clean disposable VM required'
}
if(Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\app') -PathType Container) {
    throw 'WACK_BLOCKED: active RC5.0 Universal Remote installation detected'
}
if(Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'Programs\UniversalRemote') -PathType Container) {
    throw 'WACK_BLOCKED: existing Universal Remote installation detected'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'WACK_BLOCKED: AppCert requires an elevated interactive test session'
}
if(-not [Environment]::UserInteractive) { throw 'WACK_BLOCKED: must run in interactive user session' }
if(-not (Test-Path -LiteralPath $Installer -PathType Leaf)) { throw 'Installer not found' }
$kit='C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe'
if(-not (Test-Path -LiteralPath $kit -PathType Leaf)) { throw 'Windows App Certification Kit not installed' }
$reportRoot=[IO.Path]::GetFullPath($ReportDirectory)
if($reportRoot -eq [IO.Path]::GetPathRoot($reportRoot)) { throw 'Refusing disk root for report' }
if(Test-Path -LiteralPath $reportRoot) { throw 'Report directory must not exist: no overwrite' }
[IO.Directory]::CreateDirectory($reportRoot) | Out-Null
$report=Join-Path $reportRoot 'UniversalRemote-WACK.xml'
Write-Output 'WACK_VM_ONLY: AppCert may install/uninstall programs and change test machine state'
& $kit reset
if($LASTEXITCODE -ne 0) { throw 'WACK reset failed' }
& $kit test -apptype desktop -setuppath $Installer -appusage peruser -reportoutputpath $report
if($LASTEXITCODE -ne 0) { throw ('WACK reported a failure; inspect XML report, exit '+$LASTEXITCODE) }
if(-not (Test-Path -LiteralPath $report -PathType Leaf)) {
    throw 'WACK did not generate a report'
}
Write-Output ('WACK_LOCAL_REPORT_CREATED '+$report)
Write-Output 'WACK report is local evidence; NOT Microsoft Store certification or publisher identity verification'
