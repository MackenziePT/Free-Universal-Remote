# Universal Remote — modelo de segurança e limites

**Versão: RC5.1-dev, preview sem certificação externa.**

## Fronteiras de confiança

| Área | Fronteira | Requisito |
|---|---|---|
| Utilizador Windows | Processo instalado com os privilégios do utilizador | Nunca assumir admin ou SYSTEM |
| Workspace | `allowed_roots` explicitamente escolhido | Não partilhar disco inteiro; negar junctions/symlinks e hardlinks relevantes |
| MCP local | Stdio entre cliente e processo da aplicação | Cliente local pode emitir pedidos; cada ferramenta aplica política |
| Autorizações | `grants.json` separado, tempo limitado a uma hora | Confirmação local por capacidade; revogação |
| Shell | Comandos podem sair das pastas aprovadas | Capacidades perigosas; não é sandbox de execução |
| Estado | `%LOCALAPPDATA%\UniversalRemote` | Separado do código; nenhum token no instalador |
| PowerShell | Download oficial GitHub de Microsoft PowerShell | SHA-256+assinatura Microsoft; instalação privada |
| Túnel remoto | Não incluído neste pacote público | Requer identidade, TLS, pairing, rotação, revogação e supervisão |

## Ameaças prioritárias

1. **Prompt injection**: conteúdo de ficheiros e ferramentas não é instrução para o agente; o produto aplica permissões independentemente do texto apresentado.
2. **Execução arbitrária**: permitir shell é deliberadamente privilegiado e incompatível com promessas de isolamento no workspace. Requer autenticação e aprovação local forte numa versão pública.
3. **Escalada por interface gráfica remota**: escrever uma palavra de confirmação numa caixa Tk não é prova criptográfica de presença física. Até existir proteção adicional, não anunciar autorização contra um adversário que já controla a sessão gráfica.
4. **Troca de paths/TOCTOU/ACLs**: a verificação lexical e de reparse points reduz riscos, mas não fornece garantias de handles de kernel à prova de corridas. Exige testes adversariais e modelo de objeto por handle.
5. **Processos filhos**: tarefas persistentes devem validar PID + hora de criação, limitar recursos e considerar Job Objects; o terminador atual é best-effort, não uma sandbox.
6. **Aprovação/revogação**: revogar novas ações não mata tarefas já em execução. Interface e documentação devem distinguir os dois atos.
7. **Supply chain**: binários de preview não assinados; nunca anunciar downloads públicos sem assinatura Authenticode e atestação de artefactos.
8. **Antivírus e SmartScreen**: falsos positivos podem acontecer em bundles PyInstaller não assinados. Nunca recomendar desativar proteções globais.
9. **Atualizações**: é proibido executar código de release apenas por confiar numa URL. Exigir autenticidade do editor, hashes, proteções contra downgrade e rollback.
10. **Privacidade**: logs devem omitir segredos, conteúdos, comandos e argumentos. Exportações de suporte exigem revisão do utilizador.

## Critérios para acesso remoto público

- Autenticação de conta e dispositivo com pairing explícito; rotação e revogação;
- Relay privado autorizado, TLS, controlo de replays, quotas e rate limiting;
- Consentimento forte não acionável por um cliente remoto malicioso;
- Logs auditáveis sem conteúdos sensíveis, princípio do mínimo privilégio e proteção de atualizações;
- Pentest externo e testes reais de recuperação antes de liberar shell, ecrã ou input remoto.

## Revogação imediata e privacidade de logs

- Cada operação de acesso a ficheiros e tarefa sensível compara a política carregada com o ficheiro de configuração atual. Se o utilizador alterar o workspace ou uma permissão, a sessão fica bloqueada até reiniciar a ligação MCP; uma sessão antiga não continua com acesso anterior.
- Cada capacidade privilegiada exige flag permanente ativa **e** autorização temporária válida. Os pedidos recusados não reservam um identificador de operação.
- O servidor escreve apenas nomes de operações e tipos de erros num logger dedicado que não propaga para o logger global do Python. Nunca registar conteúdos, argumentos, caminhos nem mensagens arbitrárias de bibliotecas externas.
- O estado de emparelhamento com ChatGPT continua independente do MCP local. Nenhuma ligação remota pública está configurada nesta preview.

## Resultado atual

O MCP local autónomo e os fluxos de autorização foram testados. Não foi realizado um pentest independente, não existe certificação Microsoft, nem está incluído um relay remoto público. O objetivo da publicação exige fechar estas condições.
