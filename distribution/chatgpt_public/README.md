# Universal Remote Free Unlimited — public submission candidate

This is a portable Agent Plugins package, not a second installed plugin.
It targets the existing GitHub / Railway gateway and intentionally does not
reference the owner's private MCP application or any personal tunnel.

- plugin.json: identity and OpenAI UI metadata
- mcp.json: public HTTPS MCP with OAuth (CIMD discovery, to be validated with selected provider)
- skills/setup-universal-remote/SKILL.md: owner-controlled pairing and usage

SUBMISSION GATE: While the gateway responds with awaiting-oauth / HTTP
503, this package is NOT installable as a working public connection. Configure
a production identity provider with issuer/JWKS, trusted DCR or CIMD,
real user grants and account isolation; validate OpenAI OAuth client integration
and Windows owner enrollment end-to-end before enabling remote control.

Also required: approved developer identity, verified domain, privacy and terms,
independent multi-PC acceptance and signed Windows installer. No secrets belong
in this package. This is source for submission, not an approved store listing.