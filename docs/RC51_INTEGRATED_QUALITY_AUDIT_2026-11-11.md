# Universal Remote RC5.1 — Auditoria integrada de segurança, UX e desempenho

**Data:** 11 de novembro de 2026. **Plataforma:** ASUS Windows 11 x64.
**Classificação:** Preview privada de engenharia, sem assinatura de editor, não certificada para publicação.

## Correções verificadas

### Segurança: dupla autorização
A capacidade privilegiada só é permitida quando estão simultaneamente presentes a flag permanente ativa e a autorização local temporária válida. Operações de escrita, shell, ecrã, input e consultas de tarefas respeitam esta interseção. Uma autorização anterior não reativa uma capacidade desligada. Operações recusadas não reclamam um identificador durável.

Evidência: tests/test_persistent_capability_gate.py e tests/test_stale_grant_mcp.py.

### Segurança: alteração da configuração em sessão ativa
Se o ficheiro config.json mudar, o MCP antigo nega novas operações dependentes da política anterior até à reconexão. agent_policy apresenta requires_restart e effective_permissions. A consulta de identificadores de operações permanece disponível após a revogação, para esclarecer resultados incertos.

Evidência: tests/test_live_policy_revocation.py, comunicação MCP real com pastas descartáveis.

Limitação: a revogação não mata automaticamente tarefas já iniciadas nem torna os acessos ao NTFS atomicamente imunes a corridas TOCTOU.

### Privacidade: logs do servidor isolados
Um logger próprio sem propagação evita capturar mensagens de bibliotecas externas no ficheiro privado do produto. O servidor guarda nomes de operações e classes de erro, não conteúdos nem argumentos.

Evidência: tests/test_logging_isolation.py.

### Usabilidade: DPI elevado e navegação
As páginas Início, Conexões e Acesso passaram a suportar scroll vertical, mantendo a barra lateral fixa. Em Atividade, o botão Atualizar foi reservado antes da expansão do histórico. O assistente inicial de cinco etapas já tinha sido corrigido para scroll com botões Voltar/Continuar acessíveis.

Evidência: tests/test_main_ui_dpi_accessibility.py, tests/test_onboarding_dpi_accessibility.py, tools/audit_main_ui_geometry.py.

Limitação: geometria Tk não substitui testes com leitores de ecrã, avaliação humana, navegação integral por teclado, WCAG 2.2 ou experiências multimonitor.

## Benchmark local de MCP autónomo (amostra única)

| Métrica | Resultado |
|---|---:|
| Arranque e inicialização MCP via EXE | 1,590 s |
| Ping, 120 pedidos: p50 | 2,669 ms |
| Ping, 120 pedidos: p95 | 4,011 ms |
| 180 pedidos ping, concorrência máxima 8: throughput | 644,2 ops/s |
| Concorrência 8: p95 | 17,256 ms |
| Leitura de 16 KiB, 70 pedidos: p50 | 10,945 ms |
| Leitura de 16 KiB, 70 pedidos: p95 | 12,170 ms |
| Throughput de payload útil em leitura | 1,36 MiB/s |

Fonte: evidence/qa/mcp-latency-frozen.json. Benchmark apenas no ASUS; não equivale a garantia em outros computadores, nem contém repetições, carga prolongada ou perfis térmicos.

## Dependências / Supply chain

Consulta OSV.dev para os pacotes de execução identificados a partir dos seis requisitos diretos: 39 pacotes, 0 vulnerabilidades correspondentes devolvidas pela API nessa consulta e 0 dependências em falta. O relatório está em evidence/qa/dependency-osv-runtime.json. Isto não comprova ausência universal de falhas nem legalidade de todas as licenças, e não substitui a verificação de artefactos finais.

## Regressão

A árvore-fonte passou 191 testes após as correções de segurança, privacidade e interface. Evidência: evidence/qa/RC51-FULL-QUALITY-REGRESSION.stderr.

O bundle Windows x64 autónomo foi reconstruído com Python e VC runtime embutidos, mas cada distribuição final continua a exigir aceitação dos binários, instalação, reparação, desinstalação e hashes verificados.

## Bloqueios para publicação oficial

1. Certificado de assinatura de código de editor verificado, reputação SmartScreen, atualizações autenticadas e rollback.
2. Emparelhamento remoto robusto e independente para ChatGPT e outros clientes; o produto atual possui MCP local por stdio.
3. Revisão de segurança independente: NTFS, ACL, reparse points, TOCTOU, consentimento local, shell, IPC e adversários na sessão gráfica.
4. Testes de instalação limpa em Windows 10/11, ARM64 nativo, utilizadores sem admin, empresas, proxies, OneDrive e equipamentos de outras marcas.
5. UI PT-PT/EN, modo claro/escuro, acesso completo por teclado e leitores de ecrã, 100–300% DPI e testes com utilizadores novos.
6. Ensaios prolongados de latência, throughput, memória, energia, suspensão, falha de rede, disco, crash, recuperação e interrupção de atualização.
7. Revisão de licenças, política de privacidade RGPD, marca, site HTTPS, GitHub público e pipeline final de assinatura e publicação.

**O objetivo de imaculação é progresso testado e mensurável. Não declarar certificação pública ou compatibilidade universal com base numa única estação de ensaios.**
