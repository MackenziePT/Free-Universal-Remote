@echo off
setlocal DisableDelayedExpansion
title Universal Remote - instalador
rem scripts\Resolve-PowerShell.ps1 detects the modern host and can provision a verified portable copy.
where pwsh.exe >nul 2>&1
if errorlevel 1 (
  set "URM_BOOTSTRAP=powershell.exe"
) else (
  set "URM_BOOTSTRAP=pwsh.exe"
)
"%URM_BOOTSTRAP%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Public-Bootstrap.ps1"
set "URM_RESULT=%ERRORLEVEL%"
echo.
if not "%URM_RESULT%"=="0" echo Instalacao nao concluida. Le o erro indicado acima.
echo Prima uma tecla para fechar.
pause >nul
exit /b %URM_RESULT%
