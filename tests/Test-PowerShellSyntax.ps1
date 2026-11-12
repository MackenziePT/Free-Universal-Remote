$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Files = @((Get-ChildItem -LiteralPath (Join-Path $Root 'scripts') -Filter *.ps1),
           (Get-ChildItem -LiteralPath $PSScriptRoot -Filter *.ps1)) | ForEach-Object { $_ }
$Count = 0
foreach ($File in $Files) {
    $Tokens = $null
    $Errors = $null
    [Management.Automation.Language.Parser]::ParseFile($File.FullName, [ref]$Tokens, [ref]$Errors) | Out-Null
    if ($Errors.Count -gt 0) { throw "PowerShell parser rejected $($File.Name): $Errors" }
    $Count++
}
Write-Output "PASS: PowerShell parser accepted $Count scripts; this does not prove Windows runtime behavior"
