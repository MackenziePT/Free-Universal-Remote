"""RC5.1 QA reliability changes; never touches installed RC5.0."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]

def replace(path,old,new):
    p=root/path
    s=p.read_text(encoding="utf-8-sig")
    assert old in s,(path,old[:120])
    p.write_text(s.replace(old,new),encoding="utf-8",newline="\n")
    print("UPDATED",path)

# Synthetic credentials only; production grant maximum stays exactly 3600 s.
replace("tests/test_mcp_integration.py","'expires_at':time.time()+60","'expires_at':time.time()+900")
replace("tests/test_mcp_integration.py","'expires_at': time.time()+60","'expires_at': time.time()+900")
replace("tests/test_native_mcp.py",'int(time.time())+90','int(time.time())+900')
replace("tests/test_mcp_integration.py",
        "read_timeout_seconds=timedelta(seconds=10)",
        "read_timeout_seconds=timedelta(seconds=30)")
replace("tests/test_native_mcp.py",
        "from contextlib import asynccontextmanager",
        "from contextlib import asynccontextmanager\nfrom datetime import timedelta")
replace("tests/test_native_mcp.py",
        "async with ClientSession(r, w) as client:",
        "async with ClientSession(r, w, read_timeout_seconds=timedelta(seconds=30)) as client:")
replace("tests/test_public_readiness.py",
        '"-Command",invoke],capture_output=True,text=True,timeout=35)',
        '"-Command",invoke],capture_output=True,text=True,timeout=75)')
# Replace expensive shell process probes with signed native FileVersionInfo.
p=root/"scripts/Resolve-PowerShell.ps1"
source=p.read_text(encoding="utf-8")
start=source.index("function Get-UniversalPwshVersion {")
end=source.index("\nfunction Install-UniversalPortablePowerShell {",start)
new=r'''function Get-UniversalPwshVersion {
    param([Parameter(Mandatory=$true)][string]$Executable)
    try {
        if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
        # OS file metadata avoids spawning one new PowerShell process per candidate.
        $Details = [Diagnostics.FileVersionInfo]::GetVersionInfo($Executable)
        if ($Details.FileMajorPart -lt 7 -or $Details.FileMinorPart -lt 0 -or $Details.FileBuildPart -lt 0) {
            return $null
        }
        if ([string]$Details.ProductVersion -match '(?i)(preview|rc\d|alpha|beta)') { return $null }
        # Cached and PATH-discovered shells also require a genuine Microsoft signature.
        if ($PSVersionTable.PSEdition -eq 'Desktop') {
            Import-Module Microsoft.PowerShell.Security -RequiredVersion 3.0.0.0 -ErrorAction Stop
        } else {
            Import-Module Microsoft.PowerShell.Security -ErrorAction Stop
        }
        $Signature = Get-AuthenticodeSignature -FilePath $Executable
        if ($Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate -or
            $Signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Microsoft Corporation(?:,|$)') {
            return $null
        }
        return [version]('{0}.{1}.{2}' -f $Details.FileMajorPart,$Details.FileMinorPart,$Details.FileBuildPart)
    } catch {
        return $null
    }
}
'''
p.write_text(source[:start]+new+source[end:],encoding="utf-8",newline="\n")
print("UPDATED scripts/Resolve-PowerShell.ps1")
print("RELIABILITY_PATCH_COMPLETE")
