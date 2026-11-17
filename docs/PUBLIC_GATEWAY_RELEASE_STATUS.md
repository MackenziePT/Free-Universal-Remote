# Release readiness — 2026-11-17

Status: **PRE-PRODUCTION RC; NOT PUBLIC-READY**.

## Verified in this package
- 50 tests passed on Windows Python 3.13, including a real read-only RC5.1 dispatcher check.
- Real FastAPI HTTP endpoints including MCP initialize/list/call, OAuth metadata and domain-verification hook.
- RS256/ES256 OIDC token checks (pinned issuer/audience/key source), scope gates.
- Account/device isolation; per-device signed agent transport; anti-replay; revocation.
- Durable encrypted command queue; lease-at-most-once behavior; simulated round-trip.
- Native RC5.1 adapter which checks the existing agent policy and local temporary grants.

## Blockers for external/public launch
- A production OAuth provider must be configured and tested in ChatGPT, with PKCE and correct resource audience.
- Runtime must be deployed behind HTTPS, with persistent disk and secrets, health-checked.
- Native Windows GUI needs the OAuth device enrollment flow and DPAPI identity integrated.
- Existing Windows installer needs to package the new cloud client and native dispatcher.
- End-to-end Windows 10/11 and independent multiuser/multi-PC testing; revocation and interruption tests.
- Security audit, privacy/terms/support URLs, disclosure, code signing and publisher identity.
- OpenAI domain challenge, tool scan, public submission review and approval.
- GitHub push connector returned 403 in previous task; local repository may need authorized Git credentials.

## Safety
All simulated test account names/keys are generated locally. No API keys, personal
configuration, private system logs, or existing Universal Remote tunnel identity
are shipped in this package. The user's existing private MCP is unchanged.

A public listing should not be created by binding the owner's private
`plugin_asdk_app` ID to other users. Submit a new endpoint under With MCP.
