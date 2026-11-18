# Universal Remote Free Unlimited — public submission candidate

This is a portable Agent Plugins package, not a second installed plugin.
It targets the existing GitHub / Railway gateway and intentionally does not
reference the owner's private MCP application or any personal tunnel.

- plugin.json: identity and OpenAI UI metadata
- mcp.json: public HTTPS MCP with OAuth (CIMD discovery, to be validated with selected provider)
- skills/setup-universal-remote/SKILL.md: owner-controlled pairing and usage

SUBMISSION GATE: The gateway and owner Windows pairing work with Supabase
Authorization Code + PKCE. Supabase advertises DCR, so this manifest selects
DCR and only supported OIDC scopes. OpenAI's independently registered OAuth
client is not yet allowlisted or verified end-to-end, and publisher-gated
remote commands remain disabled. Do not claim official store approval.

Also required: approved developer identity, verified domain, privacy and terms,
independent multi-PC acceptance and signed Windows installer. No secrets belong
in this package. This is source for submission, not an approved store listing.