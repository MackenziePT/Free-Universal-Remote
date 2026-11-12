# Website e publicação — execução planeada

O site local de pré-visualização está em `site/index.html`. Não está publicado, nem oferece downloads antes da certificação. É estático, responsivo, em PT-PT e sem chamadas a serviços terceiros.

## Publicação após decisão sobre a marca e o domínio
- Registar domínio e configurar HTTPS e DNS. Evitar dados falsos de contacto.
- Documentação: instalação, compatibilidade, política de permissões, transportes suportados, segurança, privacidade, changelog, FAQ, suporte, acessibilidade.
- Downloads servidos de GitHub Releases ou CDN autenticada, com hashes e assinatura/atestação de cada artefacto.
- Nenhum botão aponta para URL inexistente, sem anúncio de MSIX/Store não aprovado.
- Metadados SEO corretos, OpenGraph, sitemap, site bilíngue PT-PT/EN, WCAG 2.2 AA, mobile responsivo.
- Formulários apenas depois de política RGPD/cookies e mecanismo de privacidade.
- Automatizar deployment com branch protegida; nunca enviar segredos para repositório.
