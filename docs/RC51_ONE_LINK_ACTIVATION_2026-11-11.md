# Universal Remote RC5.1 — ligação com um único link
Data: 2026-11-11

## Experiência
Depois de instalar a RC5.1, o utilizador pode copiar e colar `universal-remote://connect` em Win + R. O Windows abre o executável UniversalRemote-Preview.exe na secção Conexões e apresenta o assistente de túnel. A interface inclui 'Copiar link de abertura rápida'.

## Proteções
- Apenas os links literais `universal-remote://connect` e `universal-remote://open` são aceites.
- Links com parâmetros, comandos, outros hosts, URLs externas ou múltiplos argumentos são recusados.
- O instalador regista a associação na conta Windows atual, apenas se o protocolo não existir; não substitui a associação de outro software.
- A desinstalação só remove a associação se ainda apontar para o executável desta instalação.
- Abrir o link NÃO concede controlo remoto, NÃO gera tokens e NÃO aprova a ligação ChatGPT.
- Primeira utilização pode ainda exigir o identificador do túnel e a respetiva chave, confirmação oficial no ChatGPT e aprovação local de permissões.
- RC5.0 já instalada permanece intocada.

## Validação desta sessão
- **266 testes executados, 259 aprovados, 7 ignorados, zero falhas**.
- GUI standalone reconstruída e autotestes dos quatro componentes em ambiente descartável: PASS.
- Instalação real de QA verificou URL em HKCU apontando para o executável instalado: PASS.
- Reparação, 27 ferramentas MCP, preservação de configuração e desinstalação: PASS.
- Arquivo privado refeito e verificado: PASS.
- Public release gate: NO-GO esperado até assinatura de editor, confiança de atualizações de produção, segurança e QA externa.

## Artefactos
Instalador QA não assinado (36.33 MiB):
`evidence/qa/installer-build/UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe`
SHA-256: `557fdcf756d5e7d5e4c554da483ffac928b1466d6682c07c63f2d4dc3485cc34`

ZIP de QA privado:
`../Universal-Remote-Preview-v1.0.0-rc5.1/UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip`
SHA-256: `db6f3be48c79e6dd2b7502c1533471e215d42d7a3825d3931b2362909862787b`

## Seguimento
Não há URL HTTP pública de download verificada. O link de protocolo apenas abre uma instalação já existente; não substitui o instalador. A RC5.1 desta sessão NÃO foi colocada no lugar da RC5.0 operacional.
