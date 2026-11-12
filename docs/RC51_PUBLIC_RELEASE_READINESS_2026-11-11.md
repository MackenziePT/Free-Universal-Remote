# Universal Remote RC5.1 — Dossiê real de pré-certificação

**Data:** 11/11/2026. **Decisão:** NO-GO público; GO para QA privada Windows x64.
**Identidade do editor:** ainda não verificada. **Binário:** não assinado Authenticode.
**Instalação ativa do proprietário:** RC5.0, não modificada.

## 1. Artefactos testados

- Instalador interno x64: `evidence/qa/installer-build/UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe`
- Tamanho: 31 782 606 bytes (~30,31 MiB)
- SHA-256: `3ee4c53db7de37d69f3c7e1ec82d47bd9ba47e97d504395a34662a8a39e2ff1a`
- Pacote de QA para segundo PC: `../Universal-Remote-Preview-v1.0.0-rc5.1/UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip`
- SHA-256 do ZIP: `5dcee81d004f406a06d75c7e2718d3ec7895f8713e5039e5d2a8a31b0613b883`
- Conteúdo do ZIP: somente instalador, verificador read-only, manual e manifestos de QA; sem ficheiros privados da máquina.
- Verificador ZIP: `INDEPENDENT_QA_ZIP_PASS` com correspondência integral do hash.

## 2. Verificações reais — ASUS Windows x64

| Teste | Evidência | Resultado |
|---|---|---|
| Regressão completa de código | `RC51-POSTFIX-FULL-REGRESSION.log` | 216 executados, 211 aprovados, 5 ignorados, 0 falhas |
| Emparelhamento MCP / revogação / anti-replay | testes de integração com stdio real | PASS local |
| Atualizador assinado Ed25519 com chave efémera de QA | `SIGNED_UPDATER_E2E_PASS` | PASS |
| Assinatura adulterada e downgrade | código de recusa 3 | PASS |
| Rollback de atualização com health-check falhado | recuperação do candidato anterior | PASS |
| Recompilação Inno Setup | `INNO_COMPILE_EXIT=0` | PASS |
| E2E do instalador real | `RC51-REBUILT-INSTALLER-E2E.log` | PASS |
| Instalação e reparação, 27 ferramentas MCP | `INSTALLER_E2E_PASS` | PASS |
| Desinstalação e preservação do estado pessoal | `INSTALLER_E2E_PASS` | PASS |
| Verificador para outro PC executado localmente em cópias descartáveis | `INDEPENDENT_CHECKER_LOCAL_SELFTEST_PASS` | PASS local |
| Verificação da assinatura Authenticode pública | `NotSigned` | **BLOCKED / FAIL** |
| Windows App Certification Kit em PC limpo | Kit localizado em Windows SDK, não executado em PC limpo | **PENDENTE** |
| Windows 11 ARM64 nativo | sem dispositivo/teste remoto | **PENDENTE** |
| Windows 10 noutro PC | sem dispositivo/teste remoto | **PENDENTE** |
| GitHub Actions Windows de runners independentes | workflow preparado, sem repositório acessível | **NÃO EXECUTADO** |
| Pentest independente | não realizado | **PENDENTE** |

## 3. Rota legítima para certificado de editor

A identidade jurídica do responsável pelo produto ainda não foi disponibilizada/verificada por uma autoridade de certificação. Não emitir certificados autossignados e anunciá-los como certificados públicos.

**Portugal, publicação em nome individual:**
- Via correta para pessoa singular: **Individual Validation (IV) / non-EV Code Signing para indivíduo**; algumas CAs agrupam IV com a família OV. A validação autentica a identidade civil do proprietário (não uma sociedade) e a chave privada permanece num token/HSM ou serviço de assinatura HSM conforme requisitos CA/B. Provedores verificados: SSL.com IV e Sectigo para indivíduos.
- A documentação Microsoft, no estado verificado em novembro de 2026, informa que Azure Artifact Signing de confiança pública para indivíduos está limitado aos EUA e Canadá.

**Portugal, publicação como empresa:**
- Via possível: Azure Artifact Signing (organizações da UE elegíveis), com subscrição paga, validação de identidade da organização e certificado/perfil do editor, ou OV CA.
- Utilizar SignTool com SHA-256 e carimbo temporal RFC 3161; a emissão/verificação da identidade depende de aprovação do fornecedor.

**Implementação preparada:**
- `packaging/UniversalRemote-SIGNED-CANDIDATE.iss` exige `PublisherLegalName` e `SignTool=URPublisher`, `SignedUninstaller=yes`.
- Isto permite assinar instalador, desinstalador e cópias temporárias do Inno Setup, quando existir certificado de editor legítimo.
- As três EXEs componentes (GUI, Agent, Updater) também devem ser assinadas com o mesmo editor antes de compilar.
- `tools/Test-PublisherSignature.ps1` impede publicação se instalador/componente não tiverem assinatura válida, identidade autorizada e carimbo temporal. Testado contra instalador atual, corretamente REPROVOU.
- A assinatura Ed25519 usada no atualizador é independente do Authenticode; antes do lançamento, provisionar a chave pública de confiança na instalação inicial assinada, com rotação, backup e políticas anti-downgrade.
- Não inserir certificados/segredos/chaves privadas no código-fonte, no ZIP nem em scripts de teste.

Documentação oficial:
- https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options
- https://learn.microsoft.com/en-gb/azure/artifact-signing/quickstart
- https://learn.microsoft.com/en-us/windows/win32/seccrypto/time-stamping-authenticode-signatures
- https://jrsoftware.org/ishelp/topic_setup_signtool.htm

## 4. Ensaios em outros computadores

A listagem atual de dispositivos autorizados ao Desktop Commander tem apenas o ASUS. O conector GitHub devolveu zero repositórios acessíveis. Assim, **não existe prova de teste em outro PC**, e não se deve afirmar que a matriz está concluída.

- Há um pacote QA privado x64 pronto para transportar pelo proprietário a outro computador autorizado.
- O verificador QA só escreve um JSON minimizado: não recolhe hostname, username, chaves nem ficheiros pessoais.
- O instalador não é executado automaticamente pelo verificador, nem desativa proteções.
- O workflow `.github/workflows/windows-quality.yml` cobre em intenção Windows Server 2022 x64, 2025 x64 e Windows 11 ARM64, mas NÃO tem execução verificada.
- Windows 10, SmartScreen, Advanced SystemCare, configurações empresariais e ARM64 precisam de execução em máquinas distintas. O ZIP é x64, não é build ARM64 nativa.
- Executar WACK com utilizador ativo e privilégios adequados num Windows limpo, não na instalação produtiva do proprietário, guardando XML/HTML reais.

## 5. Libertação de produto — NO-GO

Até existir uma identidade de editor legitimamente certificada, uma release assinalada e autenticada, uma matriz independente com relatórios, instalação sem conflito em PC limpo, verificação de privacidade/segurança e decisão do proprietário, não rotular o artefacto como versão pública final.

A certificação Microsoft / Microsoft Store não é concedida automaticamente por passar nos testes locais. Um certificado de assinatura de código não garante ausência de alertas SmartScreen em aplicações com reputação ainda reduzida.
