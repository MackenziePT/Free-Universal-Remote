"""Transition pre-public RC5.1 to explicit PS7 bootstrap and safe consent limits."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def update(name,a,b):
 p=R/name
 s=p.read_text(encoding="utf-8-sig")
 if a not in s: raise RuntimeError("Missing expected source in "+name+": "+a[:70])
 p.write_text(s.replace(a,b),encoding="utf-8",newline="\n")
 print("MODIFIED",name)

update("scripts/Resolve-PowerShell.ps1",
       "if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {",
       "if ($PSVersionTable.PSEdition -eq 'Core' -and -not $IsWindows) {")
update("universal_remote_ui.py",
       "if minutes not in (15, 60, 480):",
       "if minutes not in (15, 60):")
update("universal_remote_ui.py",
       '        self._button(actions, "8 horas", lambda: self._grant(480)).pack(side="left")',
       '        self._label(actions, "Máximo 60 minutos por sessão; renova com confirmação local.", 9, MUTED).pack(side="left", padx=(7, 0))')
update("scripts/Bootstrap.ps1",
       "$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source",
       ". (Join-Path $Root 'scripts\\Resolve-PowerShell.ps1')\n    $PowerShell = Resolve-UniversalPowerShell -NoDownload")
update("scripts/Enable-Startup.ps1",
       "$Shortcut.TargetPath = (Get-Command powershell.exe).Source",
       ". (Join-Path $PSScriptRoot 'Resolve-PowerShell.ps1')\n$Shortcut.TargetPath = Resolve-UniversalPowerShell -NoDownload")
update("scripts/Prepare-Stage.ps1",
       "& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Stage 'tests\\Test-DPAPI-RoundTrip.ps1')",
       "& (Get-Process -Id $PID).Path -NoLogo -NoProfile -File (Join-Path $Stage 'tests\\Test-DPAPI-RoundTrip.ps1')")
update("scripts/Verify-Windows.ps1",
       "& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'tests\\Test-DPAPI-RoundTrip.ps1')",
       "& (Get-Process -Id $PID).Path -NoLogo -NoProfile -File (Join-Path $Root 'tests\\Test-DPAPI-RoundTrip.ps1')")
# For distribution, a small .cmd only calls the signed Microsoft shell to resolve PS7.
(R/"INICIAR.cmd").write_text("""@echo off
setlocal DisableDelayedExpansion
title Universal Remote - instalador
rem scripts\\Resolve-PowerShell.ps1 detects the modern host and can provision a verified portable copy.
where pwsh.exe >nul 2>&1
if errorlevel 1 (
  set "URM_BOOTSTRAP=powershell.exe"
) else (
  set "URM_BOOTSTRAP=pwsh.exe"
)
"%URM_BOOTSTRAP%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\Public-Bootstrap.ps1"
set "URM_RESULT=%ERRORLEVEL%"
echo.
if not "%URM_RESULT%"=="0" echo Instalacao nao concluida. Le o erro indicado acima.
echo Prima uma tecla para fechar.
pause >nul
exit /b %URM_RESULT%
""",encoding="utf-8",newline="\r\n")
print("MODIFIED INICIAR.cmd")
(R/"scripts/Public-Bootstrap.ps1").write_text("""# Minimal machine-independent entry point. Never edits the system-wide PowerShell installation.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Resolve-PowerShell.ps1')
$ModernShell = Resolve-UniversalPowerShell
Write-Host ('Universal Remote: PowerShell runtime: ' + $ModernShell) -ForegroundColor Cyan
& $ModernShell -NoLogo -NoProfile -File (Join-Path $PSScriptRoot 'Bootstrap.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
""",encoding="utf-8")
print("CREATED Public-Bootstrap.ps1")
# Keep recovery CMD files as legacy-compatible bootstrappers; routine consent/revoke use PS7 when present.
for name,old,new in (
 ("AUTORIZAR-MCP-60MIN.cmd",
  'powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command',
  '%URM_PS% -NoLogo -NoProfile -ExecutionPolicy Bypass -Command'),
 ("REVOGAR-MCP.cmd",
  'powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File',
  '%URM_PS% -NoLogo -NoProfile -ExecutionPolicy Bypass -File')):
    p=R/name;s=p.read_text(encoding="utf-8")
    if old not in s: raise RuntimeError(name)
    s=s.replace(old,new).replace("title Universal Remote MCP -",
        "title Universal Remote MCP -",1)
    at="title Universal Remote MCP -"
    index=s.find("\n",s.index(at))+1
    s=s[:index]+"""set "URM_PS=pwsh.exe"
where pwsh.exe >nul 2>&1
if errorlevel 1 set "URM_PS=powershell.exe"
"""+s[index:]
    s=s.replace("%URM_PS% -NoLogo",'"%URM_PS%" -NoLogo')
    p.write_text(s,encoding="utf-8",newline="\r\n")
    print("MODIFIED",name)
print("PUBLIC_BOOTSTRAP_PATCH_COMPLETE")
