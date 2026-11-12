# Linux PowerShell harness: fake client, fake CIM and fake DPAPI, real supervisor loop.
# This is not a Windows, DPAPI or OpenAI tunnel connectivity test.
param([Parameter(Mandatory=$true)][string]$Fixture)
$ErrorActionPreference = 'Stop'
$env:LOCALAPPDATA = Join-Path $Fixture 'state'
$State = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP'
New-Item -ItemType Directory -Path $State -Force | Out-Null
[IO.File]::WriteAllText((Join-Path $State 'tunnel-key.dpapi'), 'synthetic ciphertext')
$global:UniversalTestDelays = [Collections.Generic.List[int]]::new()
function ConvertTo-SecureString {
    param([Parameter(ValueFromPipeline=$true)]$String)
    process {
        $Value = [Security.SecureString]::new()
        foreach ($Character in 'SYNTHETIC_RUNTIME_SECRET'.ToCharArray()) { $Value.AppendChar($Character) }
        return $Value
    }
}
function Get-CimInstance {
    param($ClassName, $Filter)
    return [pscustomobject]@{ ProcessId=$PID; Name='pwsh.exe'; CreationDate=[datetime]::UtcNow;
        CommandLine=('pwsh -File "' + (Join-Path $Fixture 'app/scripts/Start-Tunnel.ps1') + '"') }
}
function Start-Sleep {
    param([int]$Seconds)
    $global:UniversalTestDelays.Add($Seconds)
    if ($global:UniversalTestDelays.Count -eq 4) { throw 'END_SIMULATION' }
}
$Ended = $false
try { & (Join-Path $Fixture 'app/scripts/Start-Tunnel.ps1') }
catch { if ($_.Exception.Message -ne 'END_SIMULATION') { throw }; $Ended = $true }
if (-not $Ended) { throw 'Supervisor did not enter bounded retry loop' }
if (($global:UniversalTestDelays -join ',') -ne '10,20,40,80') { throw 'Unexpected retry sequence' }
if (Test-Path Env:\CONTROL_PLANE_API_KEY) { throw 'Runtime credential left in environment' }
if (Test-Path (Join-Path $State 'tunnel-launcher.pid')) { throw 'Stale process identity left after shutdown' }
$Log = Get-Content -LiteralPath (Join-Path $State 'logs/tunnel.log') -Raw
if ($Log.Contains('SYNTHETIC_RUNTIME_SECRET')) { throw 'Runtime credential leaked into tunnel log' }
Write-Output 'PASS: four client failures retried with 10,20,40,80 second backoff (sleep simulated)'
Write-Output 'PASS: runtime credential and process identity cleared after supervisor exits'
Write-Output 'PASS: exact runtime credential redacted from client output'
