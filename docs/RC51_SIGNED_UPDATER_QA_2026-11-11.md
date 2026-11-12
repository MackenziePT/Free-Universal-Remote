# Universal Remote RC5.1 — Signed Updater & Pairing QA (2026-11-11)

## Estado
**Testes de segurança e instalação local com chave efémera: PASS.**
**Distribuição pública: NÃO APROVADA.** Não existe assinatura pública Authenticode, chave Ed25519 de editor provisionada num instalador confiável, nem certificação independente de outros computadores.

## Implementação nesta árvore isolada
- `release_security.py`: valida assinatura Ed25519, inventário exato de ficheiros, tamanho/hash, validade temporal, sequência monotónica e arquitetura; instalações atómicas, lock de concorrência, diário de recuperação e backups.
- `public_update_cli.py`: comandos separados `verify`, `apply` e `recover`; a lista de chaves de editor precisa de ser instalada por uma cadeia de confiança externa ao pacote.
- `device_pairing.py` + `secure_gateway.py`: chave de dispositivo, challenge/response, aprovação local separada, escopos, nonce assinado, revogação; modo experimental `public_agent.py --paired`.
- `pairing_management_ui.py`: lista/revogação de dispositivos e aprovação apenas para leitura durante a preview. Controlo privilegiado NÃO é certificado contra um adversário que já controla a GUI. Exige confirmação independente (por exemplo, Windows Hello).
- `tools/sign_release_package.py`: preparação offline para assinar pacotes; não deve incluir chaves privadas no projeto ou no instalador.
- `tools/qa_signed_updater_e2e.py`: teste isolado com chave EFÉMERA, nunca usada em produção.

## Resultado concreto do teste E2E
Primeiras execuções do E2E na pasta `evidence/qa`: a assinatura passou, mas o teste de saúde da versão instalada falhou com `Failed to import encodings module`. Inspeção com `icacls` encontrou ficheiros extraídos sem acesso explícito ao utilizador. A aplicação copiada para `%LOCALAPPDATA%\\Temp` passou no teste de saúde (exit 0).
O Advanced SystemCare estava ativo; o utilizador reportou pedidos de autorização. Não foi estabelecido que tenha sido a causa exclusiva dos erros.

Corrigido o caminho de execução do ensaio para `tempfile.TemporaryDirectory()` (Temp normal do Windows), sem reduzir ACLs/Defender/Advanced SystemCare. Repetição real do binário `UniversalRemoteUpdater-Preview.exe`:

1. `verify` de pacote assinado em QA: **exit 0**.
2. `verify` com assinatura adulterada: **exit 3**, recusado.
3. `apply` de atualização válida: **exit 0**.
4. `verify` da mesma sequência instalada: **exit 3**, downgrade/replay recusado.
5. `apply` de nova versão defeituosa: **exit 3**, recusado após health check.
6. Instalação anterior restaurada; `update-state.json` manteve sequência 100.
7. Agente instalado `--health-probe`: **exit 0**.
8. Teste terminou com `SIGNED_UPDATER_E2E_PASS` e `UPDATED_QA_EXIT=0`.
9. Diretório temporário `urm-signed-e2e-*` removido sem resíduos na Temp normal.

A integração Universal Remote MCP instalada, separada da árvore de desenvolvimento, devolveu `version=1.0.0-rc5.0` após o ensaio. RC5.0 não foi atualizada.

## Bloqueios reais para publicação
- Certificado de assinatura Authenticode de editor legítimo e provisionamento público verificável da chave Ed25519.
- Aprovação local resistente a controlo remoto do próprio ecrã; transporte autenticado público, rotação de sessões e aprovação de dispositivo com identidade.
- Execução em Windows limpos x64/ARM64, utilizador sem admin, integração com AV/SmartScreen e teste de instalador público.
- Independência dos testes em PCs de terceiros, análise de segurança independente, revisão de privacidade/licenças, CI e cobertura de falhas de energia.
- Uma assinatura Ed25519 de pacote e um teste local NÃO substituem uma assinatura de executável nem um certificado de publicação.

## Regressão final depois da correção
Executada bateria `python -m unittest discover -s tests -p 'test_*.py' -q` com `URM_CI_HEADLESS=1`, no ambiente QA isolado: **216 testes executados; OK; 5 skipped; exit code 0**. Os cinco testes ignorados não substituem testes gráficos/Windows interativos. Evidência: `evidence/qa/RC51-POSTFIX-FULL-REGRESSION.log`.
