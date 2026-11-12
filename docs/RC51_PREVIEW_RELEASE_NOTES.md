# Universal Remote — RC5.1 Preview (Windows x64)

**Estado:** build privado de desenvolvimento, **não assinado**.  
**Data da auditoria:** 11 de novembro de 2026.

## Incluído nesta preview

- Aplicação Windows autónoma com instalador gráfico, atalhos opcionais, reparação e desinstalador.
- Python 3.14 e runtime C/C++ incluídos. Não é necessário instalar Python, pip, Git ou SDKs no computador do utilizador.
- Assistente de primeira configuração com cinco passos, por defeito sem permissões privilegiadas e sem túnel remoto aberto.
- Interface de seis secções com MCP local e 27 ferramentas.
- PowerShell opcional: a aplicação consulta a versão estável mais recente publicada **no momento do primeiro arranque**, compara com o runtime existente, não faz downgrade e descarrega apenas quando precisa. Verificação SHA-256 e assinatura Microsoft. O PowerShell global do Windows não é alterado.
- Interface de primeiro arranque corrigida para escala DPI elevada, com scroll de conteúdo e navegação inferior sempre visível.
- Logs locais de falhas de arranque sem copiar argumentos ou segredos.
- Página de pré-visualização HTML em português, sem rastreadores, scripts ou downloads públicos.

## Evidência verificada neste ASUS Windows 11 x64

| Verificação | Resultado |
|---|---|
| Regressão do código após alteração de DPI | 184 testes PASS |
| Teste de scroll e botões de navegação a 200% DPI | PASS |
| Compilação PyInstaller dos dois módulos + DLLs embutidas | PASS |
| Execução autónoma, sem Python no PATH, UI e 27 ferramentas MCP | PASS |
| Instalar / configurar / testar agente / reparar / desinstalar | PASS |
| Preservar dados do utilizador e negar ações sem configuração | PASS |
| ZIP portátil, CRC e SHA-256 de 2133 entradas do manifesto | PASS |
| Website estático: âncoras, foco, sem scripts, forms ou URLs externas | PASS |
| Runtime PowerShell 7.7.0 privado, vindo da release estável oficial | PASS |
| Seleção de 7.7.0 privado em vez de 7.6.9 global | PASS |
| Política simulada para futura versão principal 8 | PASS |
| Continuidade do conector RC5.0 instalado no ASUS | PASS |

**Artefactos:** os hashes SHA-256 completos encontram-se em SHA256SUMS.txt.

## Compatibilidade não comprovada / publicação ainda bloqueada

- Sem assinatura digital do editor nem reputação SmartScreen estabilizada.
- Não testado independentemente em Windows 10, ARM64, outros PCs, utilizadores sem admin ou ambientes empresariais.
- Emparelhamento remoto público com ChatGPT e serviço privado de ligação ainda não implementados nesta preview; MCP local funciona por stdio.
- Sem atualização automática completa da aplicação com rollback em caso de interrupção.
- Acessibilidade não auditada com leitores de ecrã nem em laboratórios externos; teste de DPI não substitui essa validação.
- Falta revisão independente de segurança, licenciamento definitivo, conformidade RGPD e critérios de distribuição pública.

**Não publicar os executáveis como release oficial até fechar os critérios de publicação.**
