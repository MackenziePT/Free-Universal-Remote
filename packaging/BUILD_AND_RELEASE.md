# Guia de compilação e publicação — Universal Remote

## Tipos de artefacto

- `UniversalRemote-Preview.exe`: aplicação Tkinter com onboarding e painel.
- `UniversalRemoteAgent-Preview.exe`: processo MCP stdio autónomo, sem portas abertas por defeito.
- `UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED.exe`: instalador Inno Setup x64, **apenas testes internos**.
- `site/index.html`: website estático em pré-visualização.
- `evidence/qa`: evidência de desenvolvimento, **nunca incluir como pasta bruta numa release**.

## Ambiente de compilação atual

- Windows 11 x64, Python 3.14 em venv isolada.
- PyInstaller 6.22.3, bundles one-dir, sem UPX, sem compressão de executáveis por terceiros.
- Inno Setup 7.1.0 x64, adquirido de `jrsoftware/issrc` e verificado pela assinatura `Pyrsys B.V.`.
- Se a distribuição for comercial, confirmar e respeitar os termos de licenciamento do Inno Setup antes da publicação.

## Build interno

1. Atualizar `requirements.txt` com versões analisadas e registos de vulnerabilidades.
2. Executar `python -m unittest discover -s tests -q`.
3. Executar `python tools/build_public_prototype.py`.
4. Executar `python tools/accept_public_prototype.py`, com PATH restrito e configurações temporárias.
5. Executar `ISCC.exe packaging/UniversalRemote-Preview.iss`.
6. Executar `python tools/qa_installer_e2e.py` (instala, inicia, testa MCP e desinstala em pasta descartável).
7. Registar SHA-256 da distribuição, assinatura, manifesto de componentes, lista de licenças e resultados de antivírus.
8. Repetir CVE scan e SBOM **após** construir os artefactos finais; não reutilizar uma análise de um ambiente antigo.
9. Nunca enviar `evidence/qa` completo, tokens DPAPI, caches, `config.json` pessoal, logs ou dados de usuário ao repositório público.

## Gates de uma versão oficial

- [ ] Compilação e testes x64 e ARM64 em máquinas Windows reais distintas.
- [ ] Windows 10/11 suportados em builds reais, utilizador sem admin, proxy, Unicode, OneDrive e Defender/SmartScreen.
- [ ] Instalação inicial, reinstalação, reparação, upgrade interrompido, rollback, desinstalação e tratamento de dados.
- [ ] Assinatura Authenticode vinculada ao editor e validação de SmartScreen.
- [ ] Aviso de privacidade, RGPD, licença da aplicação e das dependências, SBOM final e security disclosure.
- [ ] Teste de acessibilidade com tecnologia assistiva; UI PT-PT e inglês.
- [ ] Autenticação e emparelhamento remoto: não confundir stdio local com ChatGPT remoto.
- [ ] Revisão de segurança independente e Windows App Certification Kit quando aplicável.
- [ ] Pipeline GitHub com builds reproduzíveis, dependências fixadas, secrets scanning, assinaturas, atestação e aprovação manual.

Até cumprir estes gates, nenhum ficheiro deve ser rotulado como release pública certificada.
