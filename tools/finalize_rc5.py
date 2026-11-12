"""Finalize standalone RC5 integration in source checkout; no live installation changes."""
from pathlib import Path

R=Path(__file__).resolve().parents[1]

def change(rel, old, new):
    p=R/rel
    s=p.read_text(encoding='utf-8-sig')
    if old not in s:
        raise RuntimeError(f"Expected original text missing: {rel}: {old[:80]!r}")
    p.write_text(s.replace(old,new),encoding='utf-8',newline='\n')
    print("UPDATED",rel)

change("server.py", '"version": "1.0.0-rc4.8"', '"version": "1.0.0-rc5.0"')
change("smoke_test.py",
       '"read_binary_chunk",\n                        "desktop_action"',
       '"read_binary_chunk",\n                        "product_capabilities", "list_windows", "focus_window",\n                        "create_folder", "copy_file", "move_file", "recycle_file",\n                        "start_task", "list_tasks", "task_status", "task_output", "stop_task",\n                        "desktop_action"')
change("smoke_test.py","len(names) != 15","len(names) != 27")
change("tests/test_mcp_integration.py","len(listing.tools), 15","len(listing.tools), 27")
change("tests/test_mcp_integration.py","'15 tools; ping OK'","'27 tools; ping OK'")
change("tests/test_server_contract.py",
       "'desktop_screenshot','desktop_action','search_files','read_binary_chunk','check_operation'}",
       "'desktop_screenshot','desktop_action','search_files','read_binary_chunk','check_operation',\n"
       "                            'product_capabilities', 'list_windows', 'focus_window', 'create_folder',\n"
       "                            'copy_file', 'move_file', 'recycle_file', 'start_task', 'list_tasks',\n"
       "                            'task_status', 'task_output', 'stop_task'}")
change("tests/test_server_contract.py","'1.0.0-rc4.8'","'1.0.0-rc5.0'")
change("requirements.txt","pyautogui==0.9.54","pyautogui==0.9.54\nSend2Trash==1.8.3")
change("scripts/Bootstrap.ps1","1.0.0-rc4.8 / standalone-8","1.0.0-rc5.0 / standalone-9")
change("scripts/Bootstrap.ps1","release='1.0.0-rc4.8'; setup_revision='standalone-8'","release='1.0.0-rc5.0'; setup_revision='standalone-9'")
change("scripts/Install.ps1",
       "'config.example.json','smoke_test.py','windows_verify.py','operation_journal.py','process_runner.py',",
       "'config.example.json','smoke_test.py','windows_verify.py','operation_journal.py','process_runner.py',\n"
       "               'native_files.py','native_jobs.py','native_windows.py','universal_remote_ui.py',")
change("scripts/Install.ps1",
       "'README.md','START-HERE-PT.md','AUDIT.md','RELEASE_NOTES.md','TEST_REPORT.md'",
       "'README.md','START-HERE-PT.md','AUDIT.md','RELEASE_NOTES.md','TEST_REPORT.md','PRODUCT_ARCHITECTURE_AND_PLAN.md','RC5_0_VERIFICATION.md'")
change("scripts/Install.ps1",
       "'INICIAR.cmd','AUTORIZAR-MCP-60MIN.cmd','REVOGAR-MCP.cmd'",
       "'INICIAR.cmd','ABRIR-UNIVERSAL-REMOTE.cmd','AUTORIZAR-MCP-60MIN.cmd','REVOGAR-MCP.cmd'")
change("scripts/Start-Tunnel.ps1",
       "$Client = Join-Path $Root 'bin\\tunnel-client.exe'",
       "$Client = Join-Path $Root 'bin\\tunnel-client.exe'\n"
       "$ProfileFile = Join-Path $env:USERPROFILE '.config\\tunnel-client\\harmony-remote.yaml'\n"
       "if (-not (Test-Path -LiteralPath $ProfileFile -PathType Leaf)) { throw 'Configured private tunnel profile missing' }")
change("scripts/Start-Tunnel.ps1",
       "& $Client run --profile harmony-remote 2>&1",
       "& $Client run --profile-file $ProfileFile 2>&1")
change("scripts/Start-Tunnel.ps1",
       "Write-TunnelLog -Path $LogFile -Message 'Tunnel client process failed to launch or exited unexpectedly.'",
       "Write-TunnelLog -Path $LogFile -Message ('Tunnel launch exception type={0} HResult={1}' -f $_.Exception.GetType().Name, $_.Exception.HResult)")
change("scripts/Test-Tunnel.ps1",
       "$Client = Join-Path $Root 'bin\\tunnel-client.exe'",
       "$Client = Join-Path $Root 'bin\\tunnel-client.exe'\n"
       "$ProfileFile = Join-Path $env:USERPROFILE '.config\\tunnel-client\\harmony-remote.yaml'\n"
       "if (-not (Test-Path -LiteralPath $ProfileFile -PathType Leaf)) { throw 'Configured private tunnel profile missing' }")
change("scripts/Test-Tunnel.ps1",
       "& $Client doctor --profile harmony-remote --explain",
       "& $Client doctor --profile-file $ProfileFile --explain")
# Honor any configured grants_path: UI was previously hardwired to shared default.
change("universal_remote_ui.py",
       'target = STATE / "grants.json"\n    expires',
       'target = Path(config.grants_path)\n    target.parent.mkdir(parents=True, exist_ok=True)\n    expires')
change("universal_remote_ui.py",
       'dir=STATE, prefix=".consent-"',
       'dir=target.parent, prefix=".consent-"')
change("universal_remote_ui.py",
       'def revoke_local():\n    (STATE / "grants.json").unlink(missing_ok=True)',
       'def revoke_local(config=None):\n    target = Path(config.grants_path) if config is not None else STATE / "grants.json"\n    target.unlink(missing_ok=True)')
change("universal_remote_ui.py",
       '            revoke_local()\n            self.show("Acesso")',
       '            revoke_local(self.config_data)\n            self.show("Acesso")')
change("native_jobs.py",
       'return {key: row[key] for key in ("job_id", "label", "executable",\n                                          "cwd", "pid", "created_at", "state", "exit_code")\n                for _ in [0]} | {"status": row["state"]}',
       'return {key: row[key] for key in ("job_id", "label", "executable",\n                                          "cwd", "pid", "created_at", "state", "exit_code")} | {"status": row["state"]}')
(R/"ABRIR-UNIVERSAL-REMOTE.cmd").write_text(r"""@echo off
setlocal
title Universal Remote
set "APP=%LOCALAPPDATA%\HarmonyRemoteMCP\app"
set "PY=%APP%\.venv\Scripts\pythonw.exe"
if not exist "%PY%" (
  echo Universal Remote nao instalado. Executa INICIAR.cmd da release.
  pause
  exit /b 1
)
if not exist "%APP%\universal_remote_ui.py" (
  echo Interface ainda nao instalada. Atualiza o Universal Remote para RC5.
  pause
  exit /b 2
)
start "Universal Remote" "%PY%" "%APP%\universal_remote_ui.py"
exit /b 0
""", encoding='utf-8',newline='\r\n')
(R/"RC5_0_VERIFICATION.md").write_text("""# Universal Remote 1.0.0-rc5.0 — relatorio de verificacao

## Arquitetura
Produto Windows nativo e independente do Desktop Commander (usado apenas como
ponte de desenvolvimento). MCP stdio como protocolo base; tunnel-client e
transporte opcional. Operacoes privilegiadas requerem configuracao e aprovacao
local temporaria; todas usam o journal at-most-once.

## Expansao RC5.0
12 novas ferramentas MCP: capabilities, list_windows, focus_window,
create_folder, copy_file, move_file, recycle_file, start_task, list_tasks,
task_status, task_output, stop_task. Total esperado 27.

GUI primeira parte: Inicio, Conexoes, Acesso, Tarefas, Janelas, Atividade.
Recolha de output e persistencia SQLite implementadas em codigo proprio.

## Correcao de reconexao
O run e doctor usam agora --profile-file com o perfil absoluto preservado
em ~/.config/tunnel-client/harmony-remote.yaml. O antigo --profile procurava
o ficheiro em %APPDATA% neste Windows. Sem mudar a chave DPAPI.

## Limites da certificacao
A aprovacao total exige regressao, handshake stdio, exercicios de instalacao,
UI e sessao ChatGPT live. Passar os testes locais nao certifica fiabilidade
absoluta, protecao contra adversarios com acesso local ou todas as variantes
de Windows.

## Estado
Ver resultados finais de teste do script de release. O original RC4.8 mantem-se
intocado ate conclusao da instalacao validada.
""",encoding='utf-8')
readme=R/"README.md"
body=readme.read_text(encoding="utf-8-sig")
readme.write_text("""# Universal Remote — 1.0.0-rc5.0

Versao Windows autonoma (sem dependencia do Desktop Commander). Aplicacao grafica
e 27 ferramentas MCP: sistema, ficheiros, tarefas persistentes, janelas e
controlo autorizado. Para abrir: ABRIR-UNIVERSAL-REMOTE.cmd depois de instalar.
Para instalar/atualizar: INICIAR.cmd. A conexao ChatGPT usa tunnel-client
em separado; operacoes privilegiadas dependem de aprovacao local.

O estado RC5.0 encontra-se em RC5_0_VERIFICATION.md.

---

"""+body,encoding="utf-8")
with (R/"RELEASE_NOTES.md").open('a',encoding='utf-8') as h:
    h.write("\n\n## 1.0.0-rc5.0\n\nFirst-party Windows GUI, 12 native MCP tools, persistent jobs,\n"
            "file copy/move/recycle, window enumeration and focus, explicit tunnel profile path,\n"
            "legacy contract updates and installed dependency Send2Trash.\n")
print("RC5_PATCH_APPLIED")
