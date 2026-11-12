# Apply redaction before persistent storage; rotate during long-running clients.
function Write-TunnelLog {
    param([string]$Path, [AllowEmptyString()][string]$Message)
    if ($env:CONTROL_PLANE_API_KEY) { $Message = $Message.Replace($env:CONTROL_PLANE_API_KEY, '[REDACTED]') }
    $Message = [regex]::Replace($Message, '(?i)(Bearer\s+)[^\s"\x27]+', '$1[REDACTED]')
    if ($Message.Length -gt 8192) { $Message = $Message.Substring(0, 8192) + ' [TRUNCATED]' }
    if ((Test-Path -LiteralPath $Path) -and (Get-Item -LiteralPath $Path).Length -ge 10485760) {
        Move-Item -LiteralPath $Path -Destination (Join-Path (Split-Path $Path) 'tunnel.previous.log') -Force
    }
    Add-Content -LiteralPath $Path -Value $Message -Encoding UTF8
}
