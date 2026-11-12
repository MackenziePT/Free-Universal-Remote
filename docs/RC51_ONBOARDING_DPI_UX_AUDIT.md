# Universal Remote RC5.1 — Auditoria UX/DPI do primeiro arranque

**Data:** 11 de novembro de 2026. **Plataforma:** ASUS Windows 11 x64.

## Problema confirmado

O assistente de cinco etapas tinha um painel estático de 760x605 px e colocava os botões de navegação depois do conteúdo. A simulação real de escalas Tk 100%, 133%, 150% e 200% mostrou **9 de 20 combinações etapa × escala** em que a altura pedida ultrapassava a altura da janela. As opções na etapa de permissões eram especialmente afetadas.

## Correção implementada

- Conteúdo de cada etapa dentro de um canvas com barra vertical, configurado pelo tamanho real do conteúdo.
- Navegação inferior reservada primeiro no layout, sempre visível e independente do scroll.
- Roda do rato, Page Up e Page Down para deslocar o conteúdo.
- Mantêm-se cinco etapas, opções de privilégios desativadas e PowerShell atualizado opcional com consentimento.
- A janela continua ajustável; o scroll permite acesso ao conteúdo quando a geometria ou o DPI não permitem mostrar tudo ao mesmo tempo.

## Evidência

- Diagnóstico anterior: tools/qa_onboarding_dpi.py — 9/20 casos com risco de corte.
- Teste criado antes da correção: tests/test_onboarding_dpi_accessibility.py; inicialmente FAIL, depois PASS.
- Após a correção, botões finais mantiveram-se visíveis a 200% e o canvas deslocou-se quando o conteúdo excedeu o viewport.
- Regressão completa da fonte: **184 testes PASS** (evidence/qa/RC51-DPI-FULL-REGRESSION.stderr).

## Limites

O teste automatizado mede dimensões Tk e comportamento de scroll; **não substitui** validação humana, acessibilidade por leitor de ecrã, escalas Windows por monitor, disposição com janelas reduzidas, navegação com teclado num monitor real ou testes em outros PCs Windows. Publicação continua bloqueada até esses critérios serem tratados.

## Regra para futuras versões

Qualquer nova secção/checkbox adicionada ao assistente deve preservar o contentor de scroll, o painel de navegação fixo e o teste nas escalas altas. Não remover o scroll para obter uma imagem mais limpa.
