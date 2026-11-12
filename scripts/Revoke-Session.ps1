[CmdletBinding()]
param()
$Grant = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\grants.json'
if (Test-Path -LiteralPath $Grant) { Remove-Item -LiteralPath $Grant -Force }
Write-Host 'Local privileged capabilities revoked.' -ForegroundColor Green
