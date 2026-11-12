# Universal Remote — RC5.1: recuperação automática e primeira configuração

Data: 2026-11-12. Relatório técnico de testes privados no Windows x64.

## Implementações desta revisão

1. O supervisor de túnel já não termina após oito falhas de transporte transitórias: continua em intervalo de 15 minutos por tentativa depois de atingir o limiar. Retentativas iniciais mantêm backoff exponencial. O utilizador pode interromper a qualquer altura; só existe um supervisor por instalação.
2. O estado do supervisor é renovado em intervalos de 10 segundos durante esperas longas, evitando apresentação de informação desatualizada.
3. A preparação de um perfil inicial inválido deixa de manter o ficheiro de perfil órfão, permitindo repetir a configuração.
4. As capacidades writes, shell, screen e input ficam PREPARADAS por omissão durante o primeiro onboarding, podendo ser desativadas. Nenhuma autorização de sessão é concedida automaticamente; o grant temporário continua a exigir aceitação local.
5. Mantêm-se o link de abertura local universal-remote://connect e a desinstalação limpa.

## Testes TDD e validação

Novos testes específicos foram executados primeiro em RED, demonstrando a falha de recuperação, limpeza do perfil, status antigo e preset de onboarding. Após implementação, os testes em GREEN passaram.

- Regressão integral: 272 testes, 265 aprovados, 7 ignorados, sem falhas.
- Quatro executáveis standalone PyInstaller recompilados e auditados: PASS.
- Testes frozen Windows Temp: PASS.
- Instalador Inno, instalação/reparação/desinstalação em ambiente temporário: PASS.
- 27 ferramentas MCP testadas no agente de QA: PASS.
- Atualizador assinado com chave efémera de QA: PASS; rejeição de adulteração e downgrade; rollback após falha: PASS.
- Arquivo ZIP QA privado reconstruído e verificado: PASS.
- Public release gate: NO-GO esperado (não é uma certificação pública).

Instalador QA: evidence/qa/installer-build/UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe
SHA-256: 3a8a1c2cc985997f4494208e39d0f6e0a5aa24011323668cbbbdb470323a960c
ZIP QA: ../Universal-Remote-Preview-v1.0.0-rc5.1/UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip
SHA-256: 46e14c5b5bb3d72c5397415482a8323c63cada18aefa5fd39d54250d6d4c98a8

## Estado real da ligação ChatGPT

A ferramenta do conector anterior devolveu 'Session terminated' em 2026-11-12. A RC5.1 QA não foi instalada por cima da RC5.0 e nenhuma associação ChatGPT nova foi confirmada. A validação real ainda exige instalação pelo proprietário, configuração do túnel dentro do Windows, confirmação da ligação na conta ChatGPT e uma chamada MCP efetiva. Autorização temporária local para operações sensíveis continua obrigatória. O plugin pessoal v0.1.0 foi criado, mas por si só não reinicia uma sessão MCP indisponível.

## Proteções e trabalho pendente

Não expor portas de entrada na Internet; não ler nem mostrar chaves privadas. Publicação exige assinatura do editor, âncora de confiança para atualizações de produção, teste independente e revisão de segurança. O modo remoto com provas de dispositivo independentes requer validação do fluxo de autenticação ponta a ponta; não o considerar validado apenas por passar nos autotestes locais.
