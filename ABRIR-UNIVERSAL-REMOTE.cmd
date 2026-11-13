@echo off
setlocal DisableDelayedExpansion
title Universal Remote
rem RC5.1 standalone first, legacy fallback only when no new installation exists.
set "UR_GUI=%LOCALAPPDATA%\Programs\UniversalRemote\GUI\UniversalRemote-Preview.exe"
if exist "%UR_GUI%" goto URM_START_STANDALONE
set "APP=%LOCALAPPDATA%\HarmonyRemoteMCP\app"
set "PY=%APP%\.venv\Scripts\pythonw.exe"
if not exist "%PY%" (
  echo Universal Remote nao instalado. Usa INICIAR.cmd ou o instalador RC5.1.
  echo Prima uma tecla para fechar.
  pause >nul
  exit /b 1
)
if not exist "%APP%\universal_remote_ui.py" (
  echo Interface legacy em falta. Verifica a instalacao.
  echo Prima uma tecla para fechar.
  pause >nul
  exit /b 2
)
start "Universal Remote" "%PY%" "%APP%\universal_remote_ui.py"
if errorlevel 1 exit /b 1
exit /b 0
:URM_START_STANDALONE
start "Universal Remote" "%UR_GUI%"
if errorlevel 1 exit /b 1
exit /b 0
