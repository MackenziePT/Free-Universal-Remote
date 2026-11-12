# Universal Remote — política de PowerShell atualizado dinamicamente

**Data:** 11/11/2026  
**Requisito:** nunca fixar a distribuição à versão 7, 7.7.0 ou outra versão histórica. Obter a **versão estável mais recente publicada no momento do primeiro arranque**, independentemente do ramo principal (7, 8, 9, ...).

## Descoberta e atualização

1. O assistente de primeiro arranque apresenta a opção pré-selecionada **«Verificar e atualizar automaticamente o PowerShell após a configuração»**, que o utilizador pode desmarcar.
2. Quando autorizada, consulta em tempo real a fonte oficial `https://api.github.com/repos/PowerShell/PowerShell/releases/latest` por HTTPS. **Não existem números de versão de release embutidos**. A versão 7.7.0 é apenas a versão verificada em 11/11/2026, não o limite.
3. Aceita apenas o formato semântico `v<major>.<minor>.<patch>`, com `draft=false`, `prerelease=false` e versão mínima compatível. A restrição mínima atualmente definida é 7.4.0, e não um máximo 7.x.
4. Pesquisa instalações existentes válidas e assinadas, incluindo pasta privada, PATH, PowerShell padrão no Program Files e futuras pastas de versão principal.
5. **Se já existir versão igual/superior à release estável anunciada, reutiliza-a. Não reinstala nem faz downgrade.**
6. Se for inferior, seleciona o ZIP oficial correspondente à arquitetura Windows (`x64`, `arm64` ou `x86`), exige o digest SHA-256 fornecido para esse asset e valida o hash depois da transferência.
7. Extrai para staging privado, verifica `pwsh.exe`, assinatura Authenticode da Microsoft Corporation e versão do binário, e só então promove a pasta. Não atualiza registo do sistema, PATH global nem o PowerShell do Windows.
8. O motor de comandos escolhe o PowerShell de versão mais elevada disponível, incluindo uma cópia privada mais nova do que a versão global.
9. Em caso de rede offline ou falha de validação, não executa downloads não verificados. Mantém o PowerShell previamente verificado, se existir, e reporta que a pesquisa pode não ter confirmado a release mais recente.
10. A GUI continua utilizável sem qualquer PowerShell opcional. O runtime Python/Visual C++ já está incluído no próprio executável.

## Confirmações de QA

- Consulta real em 11/11/2026: GitHub oficial anunciou **v7.7.0** estável e assets ZIP x64/ARM64/x86 com SHA-256.
- Download real da release 7.7.0 de forma privada, com hash e assinatura Microsoft verificados: PASS na estação ASUS Windows x64.
- Consulta repetida com 7.7.0 já presente: PASS, retorno da cópia existente, sem download.
- API simulada de uma futura release v8.1.0 com 8.1.1 já instalado: PASS, sem downgrade nem download.
- Seleção de execução: 7.7.0 privado escolhido em vez de 7.6.9 global no ASUS, execução real PASS.
- Descoberta de versão 8 instalada no Program Files sem PATH: PASS em testes sintéticos.
- Regressão de software com política atualizada: **183 testes PASS**.
- Versão de distribuição resultante continua não assinada e sujeita aos restantes critérios de publicação.

## Restrições e manutenção futura

A política suporta futuras versões principais **enquanto a Microsoft conservar o contrato de release, os nomes dos assets Windows e a assinatura esperada**. Uma alteração do fornecedor exige atualização validada do programa, em vez de aceitar automaticamente ficheiros de origem desconhecida.

A opção manual «Verificar ou atualizar PowerShell» permanece disponível na secção Conexões. Uma nova versão de software pode continuar a oferecer a verificação na primeira configuração; não há instalação invisível de componentes durante sessões já configuradas sem autorização expressa.

## Documentos relacionados

- `scripts/Resolve-PowerShell.ps1`
- `scripts/Prepare-PowerShell.ps1`
- `public_runtime.py`
- `remote_core.py`
- `tests/test_latest_powershell_policy.py`
- `docs/PUBLIC_RELEASE_GATES.md`
