@echo off
setlocal DisableDelayedExpansion
title Universal Remote MCP - revogar autorizacao
rem Revoga apenas os direitos locais desta aplicacao.
set "URM_PS=pwsh.exe"
where pwsh.exe >nul 2>&1
if errorlevel 1 set "URM_PS=powershell.exe"
set "URM_REVOKE=%LOCALAPPDATA%\HarmonyRemoteMCP\app\scripts\Revoke-Session.ps1"
if not exist "%URM_REVOKE%" (
  echo Agente legacy nao instalado. Usa Revogar na interface Universal Remote.
  echo Prima uma tecla para fechar.
  pause >nul
  exit /b 2
)
"%URM_PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%URM_REVOKE%"
set "URM_RESULT=%ERRORLEVEL%"
echo.
if "%URM_RESULT%"=="0" (echo Pedido de revogacao local concluido.) else (echo Falha na revogacao; consulta a mensagem acima.)
echo Prima uma tecla para fechar.
pause >nul
exit /b %URM_RESULT%
