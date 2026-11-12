# Universal Remote RC5.1 — Ajuda e recuperação guiada (11-11-2026)

## Estado validado
- **RC5.1 privada Windows x64**: interface de Ajuda integrada, recompilada e instalada/desinstalada em ensaio isolado.
- **RC5.0 ativa**: não foi modificada.
- **Distribuição pública**: não autorizada; falta assinatura IV, cadeia de confiança e validação externa.

## Funcionalidade implementada
- Nova área «Ajuda» no menu e botão na página inicial.
- Diagnóstico local apenas de leitura, com «Verificar novamente».
- Textos PT-PT que explicam o problema, os passos para resolver e atalhos para «Conexões», «Acesso», «Tarefas».
- Lembrete do último erro da sessão até à próxima verificação.
- Cópia de resumo limitada a códigos e títulos, sem caminhos pessoais, tokens, credenciais ou exceções brutas.
- Avisos claros sobre não desativar antivírus, Defender e firewall.
- Em caso de erro de arranque, a explicação orienta a reparação; detalhes técnicos locais são minimizados.
- Não presume ligação remota por apenas detetar o agente local.
- Não aplica correções de sistema nem concede permissões automaticamente.

## Evidência
- `python -m unittest discover -s tests -p test_*.py -q` -> **233 executados; 228 PASS; 5 skipped; 0 FAIL; exit 0** (antes da pequena melhoria de apresentação do erro anterior).
- Testes da Ajuda e do arranque após último ajuste -> **PASS**.
- PyInstaller GUI rebuild -> **PASS**.
- GUI `--self-test` -> **PASS**.
- Inno Setup installer rebuild -> **PASS**.
- `tools/qa_installer_e2e.py` -> **PASS**, incluindo arranque, agente MCP 27 ferramentas, reparação, preservação do estado pessoal e desinstalação.
- `tools/qa_verify_archive.py` -> **INDEPENDENT_QA_ZIP_PASS**.

## Ficheiros atualizados — os hashes anteriores são obsoletos
Instalador: `evidence/qa/installer-build/UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe`
SHA-256 instalador: `1a73348b4313701e7073fd49a2a7eaab3c97392967f41cd8ab65b3ba27077a96`

ZIP privado: `../Universal-Remote-Preview-v1.0.0-rc5.1/UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip`
SHA-256 ZIP: `58f815713dad716c8cd514fdc6b4f7020d30713f7af3e070e3371d9e6c0e57c0`

Registo interno: `evidence/qa/RC51-ASSISTED-ERRORS-REGRESSION.log`, `RC51-HELP-INSTALLER-E2E.log` e `RC51-HELP-GUI-BUILD.log`.

## Pendente para produto público
- Certificado Authenticode IV real do editor (pessoa singular) e assinatura legítima com timestamp.
- Chave pública Ed25519 de atualizações provisionada na distribuição assinada (não confundir com chaves descartáveis QA).
- WACK em Windows limpo, testes independentes noutros PCs, avaliação externa de segurança.
- Ensaios manuais de acessibilidade/alto DPI e revisão final de linguagem de cada erro.
