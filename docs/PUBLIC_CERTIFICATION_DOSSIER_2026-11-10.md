# Universal Remote — Dossiê de Validação e Certificação Técnica

**Projeto:** Universal Remote, aplicação pública para Windows e integrações MCP
**Candidato analisado:** 1.0.0-rc5.1-dev (não publicado)
**Computador de ensaio:** ASUS, Windows 11 x64, PowerShell 5.1 e 7.6.9
**Data:** 10 de novembro de 2026
**Classificação do documento:** relatório INTERNO de testes executados; **não é certificado externo nem autorização para publicar**.

## 1. Resumo e decisão de publicação

O projeto ultrapassou testes locais funcionais e várias verificações de segurança, mas ainda **não está pronto para publicação geral**. Bloqueio principal: ausência de instalador gráfico autónomo, sem exigência de Python; falta também identidade/assinatura de editor, licença do produto, compatibilidade Windows em máquinas limpas e verificação Microsoft Store/Windows App Certification Kit. A RC5.0 instalada permanece operacional e inalterada.

A matriz de controlos encontra-se em `evidence/qa/certification-gates.md`: **18 PASS, 1 FAIL, 12 BLOCKED**. Os caminhos fictícios `C:\Users\O'Neil` usados nos testes são fixtures válidas; o falso positivo anterior foi corrigido.

## 2. Ensaios funcionais e dinâmicos — PASS local

- Regressão fonte e testes Windows em ambiente de desenvolvimento: 140 testes aprovados antes da auditoria de segurança adicional.
- Com Pillow 13.0.0, Python 3.14 e dependências separadas da instalação ativa: **143 testes PASS** na primeira bateria; ver `evidence/qa/patched-full-regression.log`.
- **Regressão posterior com 144 testes: 3 erros de timeout MCP (10 segundos)** em leitura/protocolo e revogação; ver `evidence/qa/FINAL-REGRESSION.log`. Reexecução focada dos 6 testes MCP: **6 PASS** em `evidence/qa/MCP-FOCUSED-RECHECK.log`. A instabilidade intermitente fica registada como bloqueio de fiabilidade até ser isolada e resolvida, mesmo que outra execução passe.
- Handshake MCP stdio e 27 ferramentas: PASS com a versão de teste em `evidence/qa/patched-smoke.log`.
- Carga de tarefas descartáveis: **20/20 PASS**, em 8,868 segundos; memória, CPU e interface em `evidence/qa/runtime-performance-local.json`.
- UI Tkinter: seis páginas abertas/navegadas, 1,956 s no processo de ensaio; RSS de 45,25 MB; 0,031 segundos CPU numa janela de três segundos de atividade mínima. **Métricas medidas apenas neste ASUS**, não SLA de produto.
- RC5.0 instalada: ping ChatGPT real confirmado antes e durante os trabalhos de preparação. Não promover RC5.1 sem instalador/rollback completos.

## 3. Cadeia de dependências — PASS na versão corrigida

Auditorias efetuadas com ferramentas de QA instaladas em ambiente isolado:
- **pip-audit 2.10.1**: Pillow 12.3.0 da RC5.0 apresentou 39 registos de vulnerabilidades conhecidos (incluindo IDs sobrepostos); pip 26.1.2 apresentou 2 registos na instalação anterior. Isto NÃO implica que existam 41 falhas independentes ou exploráveis neste fluxo de trabalho.
- **Mitigação RC5.1-dev:** pin Pillow alterado para 13.0.0; novo ambiente isolado contém pip 26.3. Análise de 43 dependências instaladas: **0 vulnerabilidades conhecidas encontradas**; resolução de `requirements.txt`: 42 dependências, também **0 registos**.
- **CycloneDX 8.0.1**: SBOM JSON de 43 componentes em `evidence/qa/patched-sbom-cyclonedx.json`.
- Evidência em `evidence/qa/patched-pip-vulnerabilities.json`, `evidence/qa/requirements-resolved-audit.json` e no SBOM.
- É necessário repetir a análise em cada build/release porque a base de dados e o grafo de dependências podem mudar.

## 4. Código e segurança — PASS limitado + ações pendentes

- **Bandit 1.9.4:** análise inicial encontrou 12 avisos (11 LOW, 1 MEDIUM). O aviso de severidade média estava associado a `urlopen` na verificação local de estado da interface. Implementada conexão explícita `HTTPConnection('127.0.0.1',8080)`, sem resolução por proxy e com tratamento de respostas HTTP inválidas; auditoria revista: **0 MEDIUM/HIGH**. Os avisos LOW, sobretudo usos deliberados de subprocessos, ainda exigem triagem individual antes da publicação.
- **Ruff 0.17.4:** análise inicial extensa encontrou 141 avisos, a maioria de ordenação de imports e limpeza. Um conjunto restrito de verificações críticas (E9/F63/F7/F82) passou; **a auditoria Ruff completa ainda não está limpa**, e não deve ser anunciada como tal.
- Scanner local de exposição em ficheiros-fonte não encontrou chaves OpenAI nem identificadores reais de túnel. Uma pesquisa por caminhos `C:\Users\...` produziu dois falsos positivos em fixtures de testes; regra refinada para distinguir o utilizador real.
- Motor MCP continua com concessões de acesso temporárias e default-deny. NÃO confundir essas salvaguardas com isolamento sandbox, pentest formal ou resistência comprovada a todas as condições TOCTOU/ACL/Win32.
- Os testes de autorização e funções de risco foram executados no ambiente QA; sessão remota ativa mantém RC5.0 separada.

## 5. PowerShell — resultado e limites

- A aplicação identifica o PowerShell 7 (`pwsh.exe`) e o mecanismo de bootstrap inclui obtenção portátil com comparação SHA-256, verificação Authenticode e restrição do assinante a **Microsoft Corporation**.
- O ASUS já dispõe de PowerShell 7.6.9, pelo que a fase efetiva de descarga automática **não foi exercitada num PC sem PowerShell**.
- A API oficial do PowerShell indicou a release estável 7.7.0 em 2026-11-10. Na verificação local, `pwsh.exe` 7.6.9 reportou assinatura **Valid** emitida para Microsoft Corporation.
- Identificada incompatibilidade da autoload do módulo Security em Windows PowerShell 5.1 quando há módulos PS7 no PSModulePath; o bootstrap passou a importar o módulo explícito compatível antes de verificar assinatura.
- A assinatura do PowerShell não substitui a futura assinatura do Universal Remote.

## 6. Compatibilidade com PCs de terceiros

- **Windows x64 no ASUS:** testes locais PASS; não equivale à compatibilidade geral.
- **Windows ARM64:** consulta de artefactos `win_arm64/cp314` obteve wheels para cinco dependências diretas (Pillow, psutil, mcp, mss, Send2Trash). A resolução completa apenas por wheels falha em `pyautogui==0.9.54`, que não ofereceu wheel pré-compilado neste teste. Isto **não prova incompatibilidade ARM64**; é necessário empacotar/builar dependências e executar num Windows ARM64 real.
- **Windows 10, múltiplos PCs, máquinas sem Python, SmartScreen, políticas empresariais, utilizadores sem admin e outras versões Windows:** ainda não demonstrados por testes separados.
- **macOS e Linux:** fora da distribuição Windows inicial; exigem adaptadores próprios e novos testes.
- **Hyper-V/Windows Sandbox:** indisponíveis no ASUS neste ensaio, sem alterações aos mecanismos de virtualização.

## 7. Certificações externas que NÃO podem ser atribuídas por testes locais

- **Windows App Certification Kit e Microsoft Store:** sem candidato final EXE/MSIX e sem kit instalado; só a avaliação/submissão adequada pode declarar aprovação. Referência: https://learn.microsoft.com/en-us/windows/uwp/debug-test-perf/windows-app-certification-kit
- **Assinatura Authenticode do produto:** falta identidade de editor e artefacto final; certificados ou assinaturas falsas não têm valor público. Referência: https://learn.microsoft.com/windows/msix/package/signing-package-overview
- **Revisão independente de cibersegurança/pentest, RGPD, acessibilidade WCAG 2.2 e certificação organizacional ISO/SOC:** requerem processos de avaliação específicos, terceiros quando aplicável, e um produto/organização no âmbito correspondente.
- **OpenSSF Scorecard, SLSA, GitHub provenance/attestation:** só podem ser medidos adequadamente após existir repositório e pipeline de build/release operacionais.
- **Site público:** `site/index.html` é uma pré-visualização local; não existe domínio live publicado, HTTPS/hosting validado nem página final de privacidade.

## 8. Ações prioritárias bloqueantes (ordem)

1. Construir o **installer Windows autónomo** com Python/runtime embutidos ou reimplementar motor nativo; sem comandos técnicos para o utilizador; incluir desinstalação e reparação.
2. Preparar builds para x64 e ARM64 com CI real em ambos os sistemas; executar matriz Windows limpa + regressão de upgrades/rollback e assinatura.
3. Maturar UI WinUI 3 ou equivalente com onboarding, legibilidade, i18n e testes com tecnologia assistiva.
4. Fechar os avisos LOW e estilo Ruff, executar testes adversariais de permissões, filesystem e automação; solicitar avaliação independente antes de permitir uso público.
5. Estabelecer licença do produto, licença dos terceiros, publisher identity, política de privacidade, documentação e inventário final de componentes.
6. Configurar repositório GitHub com secrets scanning, branch protection, CI e artefactos; só publicar releases depois da certificação e assinatura.
7. Registar domínio e publicar website acessível com downloads oficiais, informação verificável e documentos jurídicos finais.

**Decisão:** RC5.1-dev fica aprovada como base de investigação/testes locais corrigidos; **não aprovada para distribuição geral**. Esta evidência não garante ausência absoluta de defeitos.
