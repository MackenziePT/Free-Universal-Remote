@echo off
setlocal DisableDelayedExpansion
title Universal Remote MCP - autorizar 60 minutos
rem Acao local explicita; as permissoes continuam a depender do agente instalado.
set "URM_PS=pwsh.exe"
where pwsh.exe >nul 2>&1
if errorlevel 1 set "URM_PS=powershell.exe"
"%URM_PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& { $script = Join-Path $env:LOCALAPPDATA 'HarmonyRemoteMCP\app\scripts\Grant-Session.ps1'; if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { Write-Error 'Agente legacy nao instalado. Usa a interface Universal Remote.'; exit 2 }; & $script -Capabilities @('writes','shell','screen','input') -Minutes 60; if (-not $?) { exit 1 } }"
set "URM_RESULT=%ERRORLEVEL%"
echo.
if "%URM_RESULT%"=="0" (echo Pedido local de autorizacao concluido.) else (echo Falha na autorizacao; consulta a mensagem acima.)
echo Prima uma tecla para fechar.
pause >nul
exit /b %URM_RESULT%
