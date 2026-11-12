# Universal Remote — especificação de instalador e UX

## Distribuição recomendada
1. UI nativa moderna WinUI 3 com Windows App SDK (versão e requisitos fixados no build).
2. Motor nativo/empacotado independente do IDE; EXE autónomo sem Python no PC do utilizador.
3. GitHub Releases com instalador EXE/MSIX assinado, SBOM, hashes e release notes.
4. Microsoft Store como canal adicional a avaliar após assinatura, testes e identidade do editor.
5. ARM64 e x64 separados; nunca reutilizar um pacote x64 como se fosse universal.

## Primeiro arranque: 5 passos
**Bem-vindo:** o que faz e não faz; instruções curtas, sem jargão.
**Escolher pasta:** FilePicker para workspace inicial (nunca disco inteiro como predefinição).
**Permissões:** tudo desativado; controlar ficheiros, shell, ecrã e input separadamente.
**Ligar à IA:** seleção de MCP local/transportes autorizados, credenciais em armazenamento OS, teste de conectividade real.
**Finalizar:** estado, opções de autoarranque DESLIGADAS, explicar revogação e desinstalação.

## Estados independentes
O ecrã 'Estado' distingue instalado, serviço ativo, rede local, túnel autenticado, sessão MCP funcional, cliente remoto emparelhado e privilégios concedidos.

## Erros e recuperação
Interface explica erro + causa + ação específica, nunca apresenta apenas exception/code. Botão "Diagnosticar" exporta relatório sanitizado. Atualizador guarda versão anterior e reverte perante falha do healthcheck; mostra se atualização exigiu elevação.

## Acessibilidade e idiomas
PT-PT e EN, navegação completa por teclado, alto contraste, leitor de ecrã, indicador de foco, escala DPI, modo claro/escuro e preferências de movimento reduzido. Sem diálogo atrás da janela ativa.

## Privacidade e segurança
Confirmar cada categoria de privilégio; consentimento com expiração real e sempre observável. Nunca permitir que a interface de aprovação seja acionada por uma sessão remota que ainda não tem autorização apropriada. O botão de revogação mantém-se disponível mesmo offline.

## PowerShell
O consumidor não vê uma consola. O bootstrap primeiro escolhe `pwsh.exe`; se não existir, pode usar `powershell.exe` apenas para descarregar/validar o runtime moderno, que fica em pasta local privada. Não atualiza globalmente o PowerShell instalado pelo utilizador. O runtime é verificado com SHA256 oficial e Authenticode.

## Critérios de UX
Instalação sem comando manual; equipamento limpo sem Python; teste acessibilidade assistiva; onboarding concluível em 5 minutos por utilizador sem formação; uninstall limpa programa e permite conservar/remover dados pessoais.
