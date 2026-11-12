# Universal Remote RC5.1 — Estado atual e experiência simples
**Atualizado: 11/11/2026 · Candidato privado Windows x64 · NÃO CERTIFICADO PARA PUBLICAÇÃO**

## O que o utilizador vê
- **Primeira utilização: 3 ecrãs**: pasta de trabalho sugerida, permissões mínimas com avançadas recolhidas, confirmar e começar.
- Ferramenta PowerShell opcional **não é descarregada automaticamente**.
- Depois da configuração abre o **Guia**, com próximos passos sugeridos e Ajuda PT-PT.
- Verificação de saúde do motor **automática e por botão**, em segundo plano, sem bloquear a interface, abrir portas, instalar software ou executar ações privilegiadas.
- Prova real de saúde: executa o agente com `--health-probe` e `--version` em subprocesso controlado; não expõe a saída de erros nem credenciais.
- Distingue três estados essenciais: instalação local pronta, primeira configuração e **ligação remota ao ChatGPT por confirmar**. Nunca declara emparelhamento apenas por encontrar um executável ou porta local.
- Ligações: orientações em português, botão para abrir o site oficial do ChatGPT (não cria autorização), teste local e gestão de dispositivos.
- Ajuda: explicações orientadas, códigos sem dados pessoais, diagnóstico e sugestões de reparação.
- **Permissões avançadas** desativadas por defeito; escondê-las desmarca escolhas anteriores. Requer consentimento local para operações sensíveis.

## Evidência da última revisão
- `python -m unittest discover -s tests -p test_*.py -q`: **248 testes executados, 242 aprovados, 6 ignorados, 0 falhas**.
- Teste de `public_agent.py` com perfil temporário e subprocessos reais: PASS.
- Assistente inicial em Tk com perfil temporário e sem guardar configuração: PASS.
- PyInstaller GUI: PASS.
- Executável GUI `--self-test`: PASS.
- Inno Setup: PASS.
- `qa_installer_e2e.py`: **INSTALLER_E2E_PASS**; instalação, arranque, agente MCP 27 ferramentas, reparação e desinstalação, preservando estado pessoal.
- ZIP privado reconstruído e verificado por `qa_verify_archive.py`: **INDEPENDENT_QA_ZIP_PASS**.
- `public_release_gate.py`: **PUBLIC_RELEASE_NO_GO**, código 3 esperado.

## Ficheiros válidos — hashes substituem todos os anteriores
- Instalador: `evidence/qa/installer-build/UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe`
- SHA-256: `21e7c6600edaf604dce750a2dd2ebc56de3b35da7ff9eb9682fc9145420eddd4`
- ZIP privado: `../Universal-Remote-Preview-v1.0.0-rc5.1/UniversalRemote-rc5.1-x64-PRIVATE-QA-UNSIGNED.zip`
- SHA-256: `328c7ca6c7c91bddd67d41c8d9a909570b4a6e8f539bc879ed18d4f79d027950`
- Estes binários **não possuem assinatura Authenticode de editor**. Não são artefactos públicos certificados.

## O que ainda depende de recursos externos
1. **Emparelhamento ChatGPT totalmente automático:** o fluxo oficial de conta/túnel e autorização ainda precisa de ser implementado e comprovado em instalações independentes; o Guia não o substitui.
2. **Certificado de editor IV:** requer validação real de identidade, contrato, pagamento e emissão por CA. Sem estes atos o software NÃO pode ser assinado como editor verificado em nome próprio.
3. **Chave Ed25519 de atualização de produção:** é preciso provisionar uma chave legítima do editor e compilar o atualizador com a chave pública fixada; o modo `PRIVATE_QA` aceita somente chaves de ensaio.
4. **Matriz externa:** pelo menos outros PCs/VMs Windows independentes, WACK e revisão de segurança/privacidade, com evidência real.

## Proteção da instalação ativa
A RC5.0 não foi substituída. Testes realizados em ambientes descartáveis e na árvore RC5.1 isolada. Continua a ser a via operacional existente.
