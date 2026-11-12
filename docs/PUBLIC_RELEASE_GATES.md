# Universal Remote — critérios de publicação pública

**Estado: PRE-PUBLICAÇÃO. NÃO certificado para distribuição geral.**
A RC5.0 foi validada num ASUS Windows, não em todos os PCs.

## Suporte e compatibilidade
- Windows 11 e versões suportadas do Windows 10; estabelecer build mínimo real.
- x64 e ARM64 nativos testados separadamente; x86 somente se todas as dependências forem suportadas.
- Testar contas sem admin, nomes Unicode e apóstrofos, OneDrive, ACLs, SSD/HDD/NTFS, DPI 100–300%, vários monitores e diversos fornecedores GPU/CPU.
- Linux/macOS precisam de implementações próprias das operações Windows; não prometer "todos os PCs" sem esses módulos.
- Repetir tudo em instalação limpa e em máquina virtual, não apenas no ASUS.

## Distribuição e manutenção — bloqueantes
- [ ] Um **installer** visual assinado, EXE/MSIX com identificação do editor, **signing** Authenticode e dados de versão verificáveis.
- [ ] Aplicação autónoma e self-contained: não obrigar o utilizador a instalar Python, pip, PowerShell, Git ou Node.
- [ ] Consultar a versão estável mais recente do PowerShell publicada na altura da instalação (sem limitar a versões 7.x); usar a versão verificada existente ou obter runtime privado com SHA-256 e assinatura, sem editar PATH global.
- [ ] Instalador/desinstalador sem consola; estado de operações, erros legíveis, criação guiada de workspace e configurações por utilizador.
- [ ] **Rollback** automático por falha de atualização, transação atómica, ficheiros de configuração separados do binário, dados do utilizador preservados.
- [ ] Testar instalação, reparação, atualização, desinstalação, upgrade interrompido, modo offline, sem disco, sem admin e recuperação.
- [ ] Nunca distribuir `config.json` privado, chaves, tokens, logs, `.venv`, caminhos específicos de um computador ou dados de telemetria pessoal.
- [ ] Não ativar controlo remoto ou arranque automático silenciosamente; instalação local/conta/túnel separados.

## Segurança, privacy e conformidade
- [ ] Política de **privacy** explícita, RGPD, minimização de dados, consentimento informado, exportação e apagamento.
- [ ] Modelo de ameaças, pentest independente, fuzz de paths/IPC, TOCTOU, links NTFS, ACLs, contas distintas, revogação não contornável por automação remota.
- [ ] Privilégios por capacidade com consentimento curto e revogação, audit trail sem segredos, proteção da ecrã/teclado/rato.
- [ ] Atualizações assinadas, detecção de rollback malicioso, integridade dos downloads, sem execução arbitrária de instaladores externos.
- [ ] **SBOM** CycloneDX/SPDX, dependências pinadas, licença de cada componente, análise CVE, Scan de malware e secrets.
- [ ] Segurança do transporte, autenticação de dispositivo, QR/deep-link de emparelhamento, sessão única, revogação de dispositivo, proxy e TLS.

## UI e experiência
- [ ] Designer de produto consistente: preferência WinUI 3/Windows App SDK para a UI final; motor MCP independente.
- [ ] Wizard de primeiro arranque com 5 passos: boas-vindas → pasta → permissões → conectar IA → teste.
- [ ] Indicadores separados de agente, túnel, MCP, conta, permissões e tarefas.
- [ ] PT-PT/EN, contraste alto, navegação teclado, leitor de ecrã, acessibilidade WCAG 2.2 AA, dark/light, escalamento DPI.
- [ ] Gestor de ficheiros, shell interativa com streaming, gestão de janelas, tarefas persistentes, autodiagnóstico e atualizações sem consola.
- [ ] Metas medidas de CPU/RAM/arranque, estabilidade durante semanas, crash recovery e horas de atividade prolongadas.

## GitHub, website e release engineering
- [ ] Repo público com README, CONTRIBUTING, SECURITY, CHANGELOG, LICENSE decidida pelo proprietário e CODE_OF_CONDUCT.
- [ ] CI Windows em várias versões + x64/ARM64 reais, E2E do instalador, PRs, lint e testes de regressão.
- [ ] Publicar tags/versionamento e ZIP/EXE/MSIX com SHA256, assinatura, proveniência, atestação de build e **SBOM**.
- [ ] Domínio HTTPS, site acessível e responsivo com documentação, FAQ, downloads oficiais verificados e política de privacidade.
- [ ] Auditoria de naming/marca antes do lançamento, disclaimers de terceiros (não afirmar associação oficial à OpenAI).
- [ ] Betas de teste externo com feedback; só anunciar GA depois de **todos** os itens críticos aprovados.

## Evidência atual
- RC5.0 instalada no ASUS: regressão 132/132, Windows 7/7, 27 ferramentas MCP, ping ChatGPT real.
- RC5.1-prep: implementação de seleção PowerShell e redução do consentimento em desenvolvimento.
- **Em falta**: release assinada, EXE self-contained, testes Windows/ARM64 independentes, CI/website publicados, auditoria externa.
