---
name: setup-universal-remote
description: Emparelhar um PC Windows com o Universal Remote Free Unlimited, garantindo isolamento de contas e autorizações locais.
---

# Universal Remote Free Unlimited — configuração

O plugin público requer uma ligação MCP HTTPS autenticada e um agente Windows do Universal Remote instalado pelo proprietário. Não reutilizes ligações privadas de outras contas.

1. Confirma autenticação OAuth do servidor público. Um 503 ou awaiting-oauth significa indisponibilidade, nunca sucesso.
2. Guia o utilizador a instalar o agente Windows oficial e abrir Conexões > Ligar este PC ao ChatGPT.
3. O agente abre o navegador para identificação e aprovação. Nunca peças códigos OAuth ou tokens na conversa.
4. Após emparelhamento, consulta list_windows_devices e confirma o dispositivo correto. Um dispositivo registado não prova que está online.
5. Para diagnósticos e ficheiros, mantém as permissões localmente permitidas. Para PowerShell, captura de ecrã, rato e teclado, exige o scope OAuth adequado e uma concessão local fresca.
6. Nunca derives chaves Ed25519, ignores Windows Hello/UAC, ou contornes o controlo de acesso nativo.
7. A ligação entre o agente e o gateway é sempre iniciada de saída pelo próprio PC. Não exponhas portas do Windows à Internet.
8. Em ações de alteração, verifica operação, backup e resultado; ao falhar, não repitas uma operação com o mesmo ID.

A infraestrutura requer ainda autenticação OAuth de produção, assinatura do instalador e revisão oficial para disponibilização pública. Não anuncies este pacote como já aprovado na loja.