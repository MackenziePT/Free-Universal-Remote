# Universal Remote — authenticated public MCP gateway (release candidate, not GA)

This repo component adds a **separate public gateway** to the existing Windows
Universal Remote RC5.1. It never shares the owner's private MCP tunnel and does
not install or grant privileges on any user's computer.

## Features verified by local tests

- Streamable HTTP stateless JSON-RPC MCP `initialize`, `tools/list`, `tools/call`
- OIDC RS256/ES256 JWT validation with pinned HTTPS issuer, JWKS and resource
- OAuth-protected-resource metadata and OpenAI domain-verification endpoint
- Per-account device enrollment using owner OAuth and device Ed25519 challenge
- Per-device Ed25519 request signatures with timestamp/nonce anti-replay
- Encrypted durable single-replica SQLite queue, bounded jobs and outputs
- Per-account isolation for devices, operations and revoke
- Queue/lease results (no automatic retries of potentially destructive actions)
- Native cloud-client transport that rejects ungranted local Windows capabilities

## What is NOT yet complete

**This is not a public-certified product.** The backend and device-client
protocol pass simulated tests, not production end-to-end tests on multiple PCs.
There is NO configured real OAuth identity provider, NO active public backend,
NO Windows GUI integration/DPAPI key persistence or native dispatcher, NO full
installer certification, NO verified OpenAI publisher identity and NO store
submission or approval. Never label this deliverable as a live public release.

## Deployment preflight

Do not deploy with placeholder credentials. Prepare production settings in a
secret manager: `UR_OIDC_ISSUER`, `UR_OIDC_JWKS_URL`, `UR_OIDC_AUDIENCE`,
`UR_PUBLIC_ORIGIN`, `UR_GATEWAY_DB` set to `/state/...`, random 32-byte
`UR_QUEUE_KEY` Base64, and set `UR_REMOTE_CONTROL_ENABLED=true` only after
independent Windows permission, E2E, security review and multi-PC testing.

Configure a persistent `/state` mount with a single replica, and protect it.
Use an established OAuth 2.1 authorization provider with PKCE and MCP discovery;
follow the provider's setup for ChatGPT. Ensure the HTTPS edge and CSP are
configured. Production starts fail-closed without these settings.

**Transport**: `POST https://<host>/mcp`

**Device API**: `POST /v1/device/enrollment/begin`, `POST /finish`, signed
`GET /v1/agent/{device_id}/poll`, signed `POST /result`.

**Security invariant**: cloud OAuth is *not* a local Windows capability grant;
Windows app must separately authorize each class of access. Never emulate UAC,
Windows Hello, or approval dialogues from the cloud client.

## Automated tests

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q cloud_tests
```

## OpenAI plugin review preparation

Submit a new **With MCP** listing through OpenAI's official portal with
HTTPS URL, OAuth metadata, 5 positive/3 negative cases, verified publisher
identity, accessible privacy/support/terms/site, domain challenge and tool scan.
Personal plugins referencing `.app.json` cannot simply be made public.
