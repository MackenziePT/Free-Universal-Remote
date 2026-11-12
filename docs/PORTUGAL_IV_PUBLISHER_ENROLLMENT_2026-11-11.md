# Universal Remote — assinatura individual legítima (Portugal, 11/11/2026)

**Publicação em nome próprio:** escolher um certificado de assinatura de código **Individual Validation (IV)**, também denominado non-EV Code Signing for Individual Applicants. **Não é necessário abrir empresa** para esta modalidade. "OV" é um rótulo genérico utilizado por algumas autoridades certificadoras, mas certificados de organização e certificados de indivíduo distinguem-se pelo titular validado.

## Via recomendada para iniciar o pedido
- SSL.com — https://ssl.com/pt/products/software-integrity/code-signing/iv/
  - Produto IV específico para pessoas singulares, com certificado em nome pessoal verificado.
  - Opções: token físico FIPS ou eSigner (HSM na nuvem + subscrição adicional). Para CI/CD sem token físico, escolher eSigner; para assinatura local esporádica, token físico poderá servir.
  - eSigner CKA integra-se com Windows Certificate Store/CNG e Microsoft SignTool; autenticação local/OTP é feita no fornecedor, nunca no repositório.
  - A oferta e elegibilidade territorial e o preço final devem ser confirmados no checkout antes da compra.
- Sectigo — https://www.sectigo.com/faqs/detail/OV-Code-Signing-Validation-for-Organizations-and-Individuals
  - Documentação oficial de junho de 2026 confirma aceitação de pessoas singulares e validação de identidade/endereços/contactos.
  - Comparar condições de emissão, token/HSM, custo de renovação e suporte em Portugal com o fornecedor.

## O que o titular faz no portal seguro da CA
1. Abrir exclusivamente o portal oficial da CA, selecionar **Individual Validation / Individual / natural person**.
2. Confirmar que a CA aceita **Portugal** e indivíduos sem empresa, e que a emissão tem cobertura Authenticode e uso Code Signing EKU 1.3.6.1.5.5.7.3.3.
3. Introduzir o **nome civil legal** exatamente como no documento oficial. Esse nome aparecerá publicamente como editor nos executáveis; não é nome de fantasia. Confirmar esta exposição antes de comprar.
4. Confirmar preço total, IVA, token/expedição se aplicável, subscrição eSigner, política de renovação e número de assinaturas incluídas. Não assumir preços.
5. Completar pessoalmente o pagamento, acordo de subscritor e validação de identidade da CA (por exemplo, cartão de cidadão/passaporte e eventual vídeo/callback). **Nunca enviar documentos de identidade, PIN, OTP ou chave privada ao ChatGPT**, nem colocar no projeto.
6. Escolher armazenamento não exportável em token/HSM; para automatização futura, eSigner CKA é adequado se o fornecedor confirmar integração e política de autorizações.
7. Após emissão, instalar o middleware/token/CKA apenas a partir do fornecedor oficial, autenticar-se localmente e confirmar a presença de um certificado de assinatura de código na conta Windows.
8. Executar apenas o pré-teste `tools/Invoke-IVReleaseSigning.ps1 -Mode Preflight` e escolher a impressão digital exata do certificado, sem colar PINs ou credenciais no terminal remoto.
9. Na fase de assinatura aprovada, usar `-Mode Sign -CertificateThumbprint <...> -PublisherLegalName <nome-exato-do-certificado> -ConfirmIdentityValidated -ConfirmSecureKeyProvider` localmente. O fornecedor pedirá autenticação segura; **esta fase não está pronta sem o certificado emitido**.
10. Validar Authenticode, carimbo temporal RFC 3161, correspondência exata do editor e integridade pós-instalação. A assinatura Ed25519 do atualizador é independente e requer uma chave pública de release provisionada por um instalador de confiança.

## Baseline oficial aplicável
- CA/Browser Forum Code Signing BR v3.11.0 (junho de 2026): proteção de chaves em hardware/HSM; período máximo do certificado emitido desde 1/3/2026: **458 dias** (conforme orientação atual da SSL.com; confirmar sempre o requisito CA/Browser Forum e a validade emitida pela CA), sujeito a prazos mais restritos do emissor.
- Microsoft: `signtool sign /fd SHA256 /tr <endpoint> /td SHA256`; `/sha1 <thumbprint>` seleciona o certificado (o hash SHA1 do thumbprint não é o algoritmo de assinatura).
- SSL.com: endpoint RFC 3161 recomendado `http://ts.ssl.com` (assinatura da resposta da TSA deve ser verificada).
- A reputação SmartScreen constrói-se ao longo do tempo, mesmo com um certificado IV legítimo. Um alerta não autoriza desativar proteção.

Fontes:
- https://cabforum.org/working-groups/code-signing/requirements/
- https://www.ssl.com/products/software-integrity/code-signing/
- https://www.ssl.com/how-to/using-your-code-signing-certificate/
- https://www.ssl.com/downloads/
- https://www.sectigo.com/faqs/detail/OV-Code-Signing-Validation-for-Organizations-and-Individuals
- https://learn.microsoft.com/windows/win32/seccrypto/signtool
- https://jrsoftware.org/ishelp/topic_setup_signtool.htm

## Estado interno do projeto
- `tools/Invoke-IVReleaseSigning.ps1`: modo pré-teste read-only, assinatura local apenas com certificado emitido/selecionado e consentimento explícito; não mexe na RC5.0.
- `packaging/UniversalRemote-SIGNED-CANDIDATE.iss`: precisa de PublisherLegalName e árvore separada de binários já assinados; inclui SignTool para instalador/desinstalador.
- `tools/Test-PublisherSignature.ps1`: gate exacto para nome do titular e assinatura timestamped, com verificação SignTool.
- Em 11/11/2026, **zero certificados CA de assinatura de código** detectados no Windows, e nenhum pedido/compra/emissão submetido por esta ferramenta. A publicação continua **BLOQUEADA**.
