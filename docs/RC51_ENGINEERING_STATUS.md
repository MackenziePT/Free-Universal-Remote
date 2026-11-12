# Universal Remote — RC5.1 pré-publicação | Auditoria de engenharia

Data da análise: 2026-11-10. **Versão de desenvolvimento, NÃO publicar como release 1.0.**

## Trabalho efetivamente efetuado
1. Criada árvore isolada `Universal-Remote-v1.0.0-rc5.1-public-prep`. A aplicação RC5.0 original não foi substituída.
2. Implementado `scripts/Resolve-PowerShell.ps1`: seleção de pwsh 7 moderno; download portátil na pasta local APENAS se não estiver instalado; GitHub oficial HTTPS, metadados de release estável, verificação SHA-256 e assinatura Authenticode; sem administrador, sem mudar PATH global. O download de raiz em PC sem PowerShell 7 ainda precisa de teste real.
3. Novo `scripts/Public-Bootstrap.ps1` e lançador `INICIAR.cmd` revisto; bootstrap antigo 5.1 deixa de ser o host principal. Bootstrap, Startup e os testes da pasta Stage usam o host moderno onde disponível.
4. `remote_core.py` prefere pwsh do PATH e suporta o runtime privado validado, recusando fallback silencioso para Windows PowerShell 5.1 nas operações do motor.
5. UI: retirada opção falsa de oito horas; limite real de autorização de até uma hora por sessão.
6. Tarefas persistentes: TaskManager.close() para desligar monitores sem matar processos, sincronização de finalização e reaping de subprocessos terminados externamente. Testes red/green introduzidos.
7. Criada documentação `docs/PUBLIC_RELEASE_GATES.md`, `docs/ARCHITECTURE_PUBLIC.md`, `docs/INSTALLER_AND_UX_SPEC.md`, `docs/WEBSITE_AND_PUBLICATION.md`.
8. Repo local: `.gitignore` defensivo, `.editorconfig`, `SECURITY.md`, `CONTRIBUTING.md`, `.github/workflows/windows-quality.yml`.
9. Website local `site/index.html`, PT-PT responsivo, com informação correta de pré-lançamento e sem download falso, script externo ou recursos de terceiros.
10. Sinalização da versão em desenvolvimento como `1.0.0-rc5.1-dev`.

## Evidência executada no ASUS
- Regressão completa: **140 testes, OK**; `evidence/RC51-VALIDATION-FINAL.txt`. Sem avisos ResourceWarning no resultado final.
- MCP stdio: **27 ferramentas**, handshake e ping OK; `evidence/RC51-smoke-final.txt`.
- PowerShell: **28 scripts sem erros de parsing**.
- PowerShell resolver: teste concreto Windows PowerShell 5.1 → `pwsh.exe` 7.6.9 no ASUS, sem download.
- Diagnóstico de fornecedor: GitHub Releases API devolveu **PowerShell v7.7.0**, publicado 2026-11-10T20:18:47Z, asset Windows x64 com digest SHA-256 oficial.
- Site estático: **5 âncoras, 6 links internos, 0 recursos de terceiros**, auditoria PASS.
- RC5.0 instalada continua ativa: ping ChatGPT reconhece `1.0.0-rc5.0`.

## Bloqueios antes de distribuição pública
- **EXE autónomo/installer assinado** ainda por construir; o instalador atual exige Python pré-instalado e não é aceitável para o público.
- UI existente é Tkinter, temporária; refazer para WinUI 3 e testes de acessibilidade, i18n PT/EN, escalonamento DPI.
- First-run wizard: escolha de pastas, criação de config, permissões, ligação com QR/link e diagnóstico — ainda sem implementação final.
- Portabilidade x64 + ARM64 testada separadamente em Windows limpos; compatibilidade Windows 10/11, UAC, OneDrive, proxy, AV e perfis múltiplos.
- Teste real do download automático PowerShell sem runtime, assinatura do EXE, crash/rollback durante atualização e desinstalação completa.
- Matriz CI local criada, **ainda não executada no GitHub**. Não há repositório remoto publicado nem domínio/website online.
- SBOM, licenciamento da aplicação e terceiros, code signing, revisão de privacidade RGPD e pentest independente.
- UI do GitHub e nome/identidade de publicador ainda dependem de decisão legítima do proprietário; não criar recursos públicos por suposição.

## Decisão de publicação
A compilação 1.0 pública só pode ocorrer depois de todos os bloqueios obrigatórios estarem aprovados. O 100% deve ser definido por requisitos verificáveis e cobertura de compatibilidade, nunca por uma promessa literal de ausência de defeitos.
