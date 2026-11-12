# Universal Remote RC5.1 — endurecimento de segurança (11/11/2026)

**Estado:** implementação em árvore isolada, NÃO publicada; RC5.0 privada permanece instalada e ligada ao ChatGPT. Os testes finais e as compilações devem ser consultados nos relatórios de execução mais recentes. Não confundir protótipo funcional com produto certificado.

## 1. Registo e autenticidade de dispositivos

- `device_pairing.py`: dispositivos Ed25519, challenge aleatório de 256 bits, prova de posse, expiração de 120 s, limite de cinco pedidos pendentes, aprovação exclusivamente local, capacidades separadas, revogação durável e anti-replay SQLite com janela temporal de 60 s.
- `secure_gateway.py`: bloqueio *fail closed* antes da execução MCP em Python SDK 1.30.0, para TODAS as ferramentas não públicas. O pedido assinado contém nome da ferramenta, hash canónico dos argumentos, ID do dispositivo, UUIDv4 e instante.
- `public_agent.py --paired`: variante protegida de stdio, não ativa automaticamente qualquer túnel, porta pública ou permissão privilegiada.
- `pairing_management_ui.py`: interface local para ver pedidos, comparar fingerprint, aprovar somente leitura e revogar dispositivos. Por segurança, o teste de preview NÃO permite conceder `shell`, `writes`, `screen` ou `input` através desta interface.
- Não incluir chaves privadas do cliente nem tokens em configurações copiáveis. O estado `security/devices.sqlite3` é persistente no perfil local do utilizador.
- **Limitação deliberada:** o botão de aprovação local não é prova forte de presença física contra quem já controle o desktop. Para produto público, requer Windows Hello via `UserConsentVerifierInterop.RequestVerificationForWindowAsync` ou mecanismo externo equivalente e o teste no Windows real. A integração OpenAI tunnel/ChatGPT deve manter autenticação de conta e assinatura por dispositivo; a interface atual do túnel não fornece, por si só, prova criptográfica individual por chamada.

## 2. Atualizações criptograficamente autenticadas

- `release_security.py`: verificação Ed25519 com chave pública FIXADA fora do pacote; metadata canónica, versão/sequence monotónica, expiração, SHA-256 do ZIP e de todos os ficheiros; recusa entradas não canónicas, links, colisões case-insensitive, caminhos Win32 reservados, conteúdo extra e rácios de descompressão excessivos.
- `tools/sign_release_package.py`: assinatura em máquina do publicador, chave privada Ed25519 encriptada, fora do código e do artefacto. Não gera uma chave de produção automaticamente.
- `public_update_cli.py`: `verify`, `apply`, `recover`. O worker só aplica updates a partir de um conjunto de chaves aprovado por instalação de confiança. Verifica assinatura e payload ANTES de executar qualquer conteúdo.
- O `apply` faz staging na mesma unidade, bloqueio exclusivo, backup sem apagar dados, troca controlada, health check do agente (`--health-probe`) e GUI (`--self-test`), commit durável e recuperação de interrupções.
- **Política de trust:** o `publisher-keys.json` não pode vir de ZIP desconhecido; a primeira instalação precisa de bootstrap/instalador Autenticado (Authenticode válido) ou confirmação da identidade fora de banda.
- **Limites:** não existe ainda certificado público Authenticode do editor nem endpoint de distribuição confiável. Teste com chave gerada temporariamente NÃO equivale a assinatura pública. Acesso à internet/auto-update em background está desativado até existir origem HTTPS autenticada, feed e autenticação de editor.

## 3. Testes efetuáveis

1. Regressão fonte: `python -m unittest discover -s tests -p "test_*.py" -q`.
2. Testes isolados: `tests/test_device_pairing.py`, `tests/test_secure_gateway.py`, `tests/test_secure_gateway_stdio.py`, `tests/test_release_security.py`, `tests/test_signed_publisher_pipeline.py`.
3. Teste real de stdio: 29 ferramentas no modo `--paired`, acesso inicialmente negado, request/challenge, assinatura do cliente, aprovação local sintética apenas em diretório temporário, leitura assinada, replay e revogação.
4. Assinador de teste: chave TEMPORÁRIA e pasta descartável; alterar bytes, assinatura, chave, versão/sequence e comprovar rejeição. Nenhuma chave de produção gerada no PC em teste.
5. Update em pasta TEMPORÁRIA com versão anterior e health check positivo/negativo; garantir reversão dos binários e estado persistente.
6. Instalar preview x64 em pasta temporária; verificar `Agent --health-probe`, `GUI --self-test`, `Updater --help`, desinstalar sem afetar a RC5.0 em `HarmonyRemoteMCP`.

## 4. Bloqueios necessários para a versão pública

- Certificado de assinatura de código Authenticode vinculado ao editor legítimo, timestamp RFC3161 e auditoria da cadeia; identidade do publicador e política de rotação/revogação das chaves Ed25519.
- Teste real de Windows Hello/consentimento que não possa ser autorizado apenas por um agente remoto.
- Relay/autenticação remota para clientes concretos; demonstrar transporte TLS, ligação, reconexão e revogação numa sessão de ChatGPT real sem conceder direitos automaticamente.
- Testes independentes em Windows 10/11 x64, ARM64, perfis standard, disco bloqueado/sem espaço, arranque/reboot, proxy, Defender e SmartScreen; preferencialmente CI, VMs e beta externa.
- Teste adversarial e auditoria externa do agente, da assinatura, do updater e do emparelhamento.
- Licenças, privacidade/RGPD, acessibilidade e artefactos assinados/publicação. Não anunciar certificação antes de evidência real.

## 5. Invariantes

- Nunca alterar `%LOCALAPPDATA%\\HarmonyRemoteMCP\\app` durante esta revisão.
- Nenhuma permissão de shell/ecrã/input deve ser concedida por código de instalação, testes ou emparelhamento.
- Nunca inserir assinatura/chave privada real na árvore de origem, ZIP, código-fonte ou conversa.
- Qualquer pacote cujo manifesto não valide com chave pinada deve ser rejeitado ANTES de ser iniciado.
- O teste noutra máquina tem de ocorrer realmente noutra máquina; testes locais não substituem compatibilidade independente.
