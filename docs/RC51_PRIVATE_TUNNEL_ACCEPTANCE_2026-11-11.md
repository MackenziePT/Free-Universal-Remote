# Universal Remote RC5.1 — integração funcional de túnel privado
Data: 2026-11-11

## Decisão
**GO para testes privados Windows x64. NO-GO para produto público certificado.**
A RC5.0 instalada mantém-se ligada ao ChatGPT. Confirmado via MCP: alive=true, version=1.0.0-rc5.0. Não foi modificada.

## Funcionalidades incluídas na nova RC5.1
- Primeira configuração em 3 ecrãs e Guia com sugestões PT-PT.
- Secção Conexões: assistente gráfico de Secure MCP Tunnel, com botões para as páginas oficiais de túnel e chave, campos de colagem, consentimento explícito, opção de arranque com o Windows e botões Iniciar/Parar.
- Cliente oficial de túnel Windows x64 v0.0.16 incluído, com SHA-256 fixado/verificado (não foi descarregado do utilizador).
- Chave de acesso cifrada pelo Windows CurrentUser DPAPI; nunca incluída no perfil YAML, linha de comandos, logs ou ZIP distribuído.
- Supervisor separado com espera progressiva e jitter, máximo de 8 tentativas consecutivas e paragem segura. Estado do túnel local não é apresentado como autenticação ChatGPT concluída.
- Dispositivo emparelhado: prova criptográfica + aprovação de leitura local da preview; permissões privilegiadas continuam com os mecanismos de consentimento existentes.
- Atualizador verifica assinaturas Ed25519, inventário de ficheiros, sequence monotónica; atualização com rollback quando o teste de saúde falha. Valida também túnel e cliente fixado.

## Testes reais no ASUS em ambiente isolado
- Regressão: **261 executados, 254 aprovados, 7 ignorados, zero falhas**, antes de dois testes adicionais ao supervisor (que passaram em separado).
- Os quatro executáveis autónomos passaram autoteste na pasta Temp normal do Windows. Um arranque do serviço de túnel na pasta de compilação falhou com erro Python encodings, apesar de DLL/ZIP íntegros; o mesmo executável copiado sem alterações para a pasta Temp normal passou. Não se desativaram proteções.
- Auditoria dos quatro bundles x64 e dos runtimes Python/VC: PASS.
- Instalador Inno: PASS.
- Instalação/reparação/desinstalação/27 ferramentas MCP: PASS, sem alterar a RC5.0.
- Teste Ed25519 de pacote válido, adulterado, downgrade e rollback: PASS, chave privada efémera **apenas de QA**.
- ZIP privado regenerado e verificado: PASS.
- Gate de publicação pública: **NO-GO, exit 3 esperado**.

## Artefactos atualizados (estes hashes substituem os anteriores)
Instalador privado não assinado:
`evidence/qa/installer-build/UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe`
SHA-256: `52b46254606597267f6274db2ee968a06a108817e30ada0ec7d6c57a8288a59e`.
Tamanho: 36.33 MiB.

ZIP privado de QA Windows x64:
`../Universal-Remote-Preview-v1.0.0-rc5.1/UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip`
SHA-256: `859b0933781ed576bc4c499102d9808bf9ce9b0421c0cd0354b513c85e372be1`.

## Limitações e trabalho externo real
1. Associação na conta ChatGPT: o utilizador deve criar/autorizar o Secure MCP Tunnel no OpenAI Platform/ChatGPT. Não se pode aprovar a ligação por ele silenciosamente; a nova RC5.1 ainda não teve um emparelhamento real end-to-end com conta ChatGPT. As funcionalidades de reconexão foram testadas por simulação controlada, não por falhas reais de Internet/Platform.
2. Certificado de assinatura Authenticode **Individual Validation** emitido ao editor em Portugal: ainda não emitido nem utilizado; não pode ser obtido sem validação pessoal do titular.
3. Chave pública de atualizações de produção: ainda não provisionada, editor deve manter a chave privada segura fora do projeto; o build atual usa modo PRIVATE_QA.
4. WACK em Windows limpo, testes em outros PCs (Windows x64 e ARM64), auditoria externa, revisão de privacidade e testes de segurança. Não concluídos.

## Uso simples previsto
Instalar → selecionar pasta recomendada → confirmar permissões mínimas → abrir Guia → ligar ao ChatGPT (introduzir dados oficiais do túnel numa só janela) → confirmar a associação na conta ChatGPT → utilizar. Reconexão após configuração é opcional; nenhuma chave é solicitada de novo no uso normal.
