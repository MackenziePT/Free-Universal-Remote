# Universal Remote — public listing draft (NOT YET SUBMITTED)

**Proposed display name:** Universal Remote Free

Reason: keep a concise store name while clarifying that OpenAI, third-party
cloud services and ChatGPT quotas may charge or limit usage. The user may use
“Free Unlimited” as a product slogan only when external quotas are disclosed.

**Category:** Developer Tools / Productivity

**Short description:** Trabalha no teu Windows com ferramentas MCP e autorização local.

**Long description:** Liga a tua própria instalação Windows Universal Remote ao
ChatGPT com uma conta individual e identidade de dispositivo verificada. Consulta
estado e diagnósticos e solicita operações com ficheiros, PowerShell e ecrã.
As ações sensíveis exigem permissão local do proprietário. Cada PC tem
emparelhamento e capacidade de revogação próprios. O software pode ser gratuito;
limites ou custos de serviços de terceiros aplicam-se separadamente.

**Positive review tests** (fixtures to be prepared with real demo account):
1. Authenticated account lists only its paired Windows PC.
2. Diagnostic read request returns operation ID; locally connected agent returns result.
3. PowerShell is denied by device without a current local shell grant.
4. Device may be revoked; new signed requests are blocked.
5. Two distinct accounts cannot list or access each other's devices.

**Negative review tests**:
1. Invalid, expired or wrong-audience OAuth access token receives HTTP 401.
2. A replayed Ed25519 device request is rejected.
3. Attempt to execute a shell command without independent local consent is refused.

**Required URLs (not yet provided):** website, support, privacy policy, terms.

**OpenAI verification token:** only from the actual submission dashboard.

**Security disclosure:** This is not an OpenAI-authored app; no affiliation is claimed.
No computer access without a separate native Windows permission decision.
