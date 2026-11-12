# Universal Remote RC5.1 — verificação final da preview privada

**Data:** 11 de novembro de 2026
**Estado de engenharia:** GO para preview privada Windows x64
**Estado público:** NO-GO — assinatura IV de editor, chave de atualizações de produção, WACK e computadores independentes pendentes
**PC ativo:** RC5.0 mantida, sem atualização automática

## Artefactos atuais — substituem hashes dos dossiês anteriores

**Instalador:** `evidence/qa/installer-build/UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe`
**SHA-256 do instalador:** `1dd6c4c523a4f586fe7670d7971c025442883b1c8202a038b8bc68af8472c282`
**ZIP privado:** `../Universal-Remote-Preview-v1.0.0-rc5.1/UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip`
**SHA-256 do ZIP:** `7a245a234c8afba4bc010591b7e0fa9fa29ee62c3f7a4980aa6aaea4334ee2cf`
**Importante:** Ambos são NÃO ASSINADOS. Não enviar como downloads públicos e não desativar antivírus/SmartScreen.

## Verificações executadas nesta revisão

- `RC51-RELEASE-HARDENING-REGRESSION.log`: **225 testes, 220 PASS, 5 skipped, 0 FAIL, exit 0**
- `RC51-TRUST-PINNED-UPDATER-E2E.log`: executável QA refeito, assinatura Ed25519 de teste aceite; adulteração e downgrade recusados; recuperação após falha de saúde passou; exit 0
- `RC51-TRUST-PINNED-INSTALLER-E2E.log`: instalação, 27 ferramentas MCP, primeira execução, GUI, reparação, desinstalação e preservação do estado; exit 0
- `tools/qa_verify_archive.py`: `INDEPENDENT_QA_ZIP_PASS`, ZIP e SHA verificados depois de atualizar binário
- `UniversalRemoteUpdater-Preview.exe trust-profile`: `{"channel":"PRIVATE_QA","embedded_keys":0}`
- `tools/public_release_gate.py`: `PUBLIC_RELEASE_NO_GO`, exit 3 como esperado
- `tools/Invoke-IVReleaseSigning.ps1 -Mode Preflight`: nenhum certificado IV válido disponível, exit 3
- Compilação do instalador com Inno Setup: `RC51_REBUILT_INSTALLER_EXIT=0`

## Defesa adicional de confiança de atualizações

O atualizador passa a carregar `release_trust_anchor.py`. Na versão privada, uma chave de teste externa é permitida apenas explicitamente no canal `PRIVATE_QA`; no canal `PRODUCTION`, o código rejeita uma chave fornecida por parâmetro e exige a chave pública incorporada. Não existe chave privada embutida.

`tools/build_pinned_updater.py`: prepara fonte e compilação isolada de atualizador com chaves públicas Ed25519 do editor fornecidas por canal externo. Não está executado em produção porque nenhuma chave real foi provisionada; não gerar chaves privadas automaticamente.

`tools/Invoke-IVReleaseSigning.ps1` exige **três componentes na árvore de produção** (`evidence/qa/publisher-ready-bundle`) e recusa o perfil `PRIVATE_QA`. Uma assinatura Authenticode pública tem de ser emitida por autoridade certificadora ao titular (Individual Validation, Portugal), com armazenamento seguro em token/HSM ou eSigner. Não selecionar certificados automaticamente.

A eventual chave pública Ed25519 para atualizações e o certificado Authenticode do software são dois mecanismos separados.

## Bloqueios que não podem ser simulados

1. Emissão e validação de identidade pessoal IV pela SSL.com / Sectigo ou CA de confiança; processo contratual e financeiro do titular, sem partilhar documentos/PIN/OTP/chaves no chat
2. Chave de assinatura de atualizações Ed25519 mantida pelo editor em ambiente seguro; incorporar apenas chave pública real e compilar a versão PRODUCTION
3. SignTool Authenticode com SHA-256 e timestamp RFC 3161 no instalador, no desinstalador e nas EXEs; testar cadeia de confiança e identidade civil exata
4. Windows App Certification Kit em Windows limpo e independente; relatório real, não simulado
5. Testes em pelo menos uma máquina Windows x64 separada e numa configuração ARM64 adequada, com evidência de regressão e SmartScreen; o artefacto atual é x64, não ARM64 nativo
6. Validação externa de segurança, privacidade e superfície de emparelhamento remoto, incluindo a integração real de cliente ChatGPT a pedidos assinados
7. Decisão de publicação com revisão de licenças, política de atualizações, documentação e testes de recuperação de emergência

## Decisão

A preview RC5.1 está preparada para QA privada; **não está certificada para o público**. A instalação RC5.0 do ASUS mantém-se independente e funcional.
