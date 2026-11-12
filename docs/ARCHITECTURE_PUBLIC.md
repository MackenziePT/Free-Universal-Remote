# Universal Remote — arquitetura de produto público

O objetivo é uma aplicação independente para PCs de terceiros. Desktop Commander é apenas uma ferramenta de desenvolvimento, nunca dependência runtime.

## Separação de camadas
1. **Aplicação gráfica** WinUI 3/Windows App SDK (fase final), gestão de conta, onboarding, consentimentos, tarefas e diagnósticos.
2. **Motor local** com API interna tipada e versionada; o código Python atual é referência transitória a preservar por testes e migração, não uma exigência para o consumidor.
3. **Adaptadores do SO** para ficheiros/NTFS, processos Job Objects, janelas Win32, input, captura, rede e credenciais DPAPI.
4. **Gateway MCP** standard; clientes externos com acesso e ferramentas limitados; versionamento do schema e capacidade negociada.
5. **Transportes** opcionais e autenticados: OpenAI private tunnel como adaptador, local stdio, extensões futuras. O produto não deve depender de fornecedor único.
6. **Instalação/Atualização**: binário assinado, configuração por utilizador, operações reversíveis, controlo de integridade e logs locais filtrados.

## Política de segurança
Tudo READ-ONLY até autorização local explícita. A permissão de shell é privilegiada e não se torna confinada às pastas apenas por ter `allowed_roots`. Consentimento expirável, revogação, limite de concorrência, proteção de operações repetidas e processos filhos. Nenhum agente pode alargar as suas próprias permissões.

## Instalação de terceiros
Sem consola para o utilizador; sem Python pré-instalado. Primeiro arranque cria workspace privado e pede que o utilizador escolha pastas. Não acoplar configuração a um diretório de utilizador literal nem ao hardware de desenvolvimento. ARM64 e x64 são artefactos distintos.

## PowerShell
No Windows, `powershell.exe` é o host de compatibilidade antigo. `pwsh.exe` é o host moderno. O CMD de bootstrap pode usar Windows PowerShell apenas para descobrir/obter uma cópia verificada e executar o instalador no host moderno. Não atualizar PowerShell global silenciosamente nem modificar variáveis de ambiente globais. Versão suportada e assinatura verificadas.

## Manutenção do projeto
Permanecer em RC5.1-public-prep até existir compilação self-contained, instalador assinado e matriz Windows testada. Nunca sobrepor a RC5.0 operacional sem ciclo de release e rollback.
