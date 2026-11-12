# Universal Remote RC5.1 — Automatic prerequisites & user-friendly distribution

**Data:** 11 de novembro de 2026  
**Classificação:** RC5.1-dev, preview Windows x64 para testes privados. **Não é uma versão pública assinada ou certificada.**

## Política decidida: zero trabalho técnico do utilizador

1. Descarregar o instalador EXE, instalar e abrir; não é preciso terminal.
2. O Python 3.14, runtime CPython, biblioteca base, DLLs VCRUNTIME/UCRT e dependências Python ficam embutidos nos binários PyInstaller one-dir. **Nunca instalar Python, pip ou Visual C++ globalmente como pré-requisito deste pacote.**
3. Diagnóstico de componentes durante a configuração e no painel: se faltar um componente do binário, avisar claramente e recomendar **Reparar** com o instalador. Não descarregar código binário arbitrário ou sobrescrever DLLs em tempo de execução.
4. PowerShell 7 é opcional. A configuração inicial permite preparar a versão estável mais recente de forma automática quando não existe runtime, com opção visível de desativação. Descarregamento do GitHub oficial da Microsoft, SHA-256 e assinatura Authenticode Microsoft; runtime instalado em `%LOCALAPPDATA%\UniversalRemote\runtime\powershell`. O PowerShell global do Windows não é substituído.
5. Arranque automático e serviços Windows contínuos NÃO são necessários para integração MCP local stdio. Acesso remoto permanente exigirá uma opção separada com consentimento/autenticação, nunca ativação oculta.
6. Escrita, terminal, captura de ecrã e controlo de input ficam desativados por defeito; a seleção de capacidades não equivale a concessões remotas temporárias.

## Experiência do primeiro arranque

Cinco ecrãs: apresentação → escolher workspace → permissões → configuração IA/PowerShell → confirmação. Botão final **Concluir e abrir**. Estado do motor local separado de qualquer alegação de conectividade remota; um processo a escutar na porta 8080 não é prova de emparelhamento com ChatGPT.

Diagnóstico na interface: **Verificar componentes instalados**, com estados e texto legível, sem jargão obrigatório para utilização normal. Verificação antes de avançar na primeira configuração. Tarefas existentes não são terminadas só por sair do painel.

## Evidência executada no ASUS Windows 11 x64

| Gate interno | Resultado |
|---|---|
| Testes Python/Windows completos da árvore RC5.1 | **176/176 PASS**, `evidence/qa/RC51-AUTO-PREREQ-FULL-REGRESSION.log` |
| Diagnóstico de dependências e primeiros passos | 6 + 6 testes direcionados PASS |
| Validação PE/arquitetura e DLLs embutidas em ambos os EXEs | PASS (`tools/audit_bundled_runtime.py`) |
| Recompilação completa de GUI + agente, com auditoria de bundle bloqueante | PASS (`evidence/qa/RC51-FINAL-AUTO-BUILD.log`) |
| Execução do EXE com PATH sem Python e perfil temporário | PASS, seis secções GUI + 27 ferramentas MCP (`evidence/qa/RC51-AUTO-BINARIES-ACCEPTANCE.log`) |
| Instalador x64 EXE + reparação/reinstalação + desinstalação | PASS (`evidence/qa/RC51-AUTO-INSTALLER-E2E.log`) |
| Segurança padrão: recusa sem configuração | PASS |
| Preservação dos dados pessoais na reparação e desinstalação | PASS |
| PowerShell 7 portátil — instalação inicial x64 usando Windows PowerShell 5.1 | PASS, runtime 7.7.0 verificado (`evidence/qa/powershell-first-run.log`) |
| Matriz interna de publicação | **21 PASS, 0 FAIL, 12 BLOCKED** (`evidence/qa/certification-gates.md`) |
| RC5.0 previamente instalada | Continua operacional, ping ChatGPT confirmou versão 1.0.0-rc5.0 |

O teste de execução com PATH limitado **não substitui um ensaio num Windows completamente limpo**. Os 12 bloqueios documentados permanecem.

## Artefactos de teste Windows x64

Diretório de entrega local: `Desktop\Universal remote\Universal-Remote-Preview-v1.0.0-rc5.1`.

- **Instalador (24,53 MB):** `UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe`.
- **ZIP portátil (45,92 MB):** `UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED-AUTO.zip`.
- Manifestos e `SHA256SUMS.txt`, `LEIA-PRIMEIRO.md`, `certification-gates.md`.

Hashes SHA-256:
- Installer: `2fa0e9ef7672e7c989f530cebaf59bcccc562746a32e9231a7c19beb3725adee`
- ZIP portátil: `9b47fc89b2a848e31bf7b95111439a2ae316414ef35a1874abe0b9c8c19c02c7`

## Bloqueios antes da publicação pública

- Assinatura Authenticode de editor verificado e SmartScreen/reputação; não é legítimo declarar certificação Microsoft sem processo formal.
- Matriz real Windows 10/11 em PCs diferentes, utilizadores sem admin, ARM64 nativo, políticas corporativas e ambientes com proxy/OneDrive.
- Revisão de segurança independente (incluindo IPC, permissões, NTFS e ataques à interface local), modelo de atualização seguro com rollback de falhas/energia.
- Emparelhamento remoto independente com autenticação adequada; esta preview contém MCP stdio local, não um serviço remoto público pronto.
- Testes com leitores de ecrã, DPI e navegação por teclado; localização EN além de PT-PT.
- Licença do produto e revisão de licenças Inno Setup/terceiros, política de privacidade RGPD, repositório GitHub público e site HTTPS com downloads assinados.

**Conclusão:** base local funcional, instalável, autónoma e dotada de deteção de pré-requisitos; não publicar como versão geral até fechar os restantes gates.
