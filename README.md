# Universal Remote (Windows) — public source preview

Universal Remote is a Windows application for locally approved MCP workflows.
It offers a desktop interface, a guided first run, local Windows diagnostics,
authorized file and shell operations, and a supervised private connection.

## Simple experience

1. Install the verified Windows release from GitHub Releases when published.
2. Open Universal Remote, configure the private connection through its wizard.
3. Confirm access in the Windows application. Stop or revoke access at any time.

The universal-remote://connect link opens the local connection wizard after
installation. The link itself does not authorize remote actions.

## Development status

Not yet a general-public release. The current RC5.1 is an unsigned,
privately tested Windows x64 preview. Public signed installers, independent
security review and an authenticated multiuser plugin connection are not yet
certified or complete. A source repository on GitHub does not by itself
provide the ChatGPT-to-Windows relay.

The personal OpenAI Secure MCP Tunnel can provide the remote transport without
Railway, a custom public server or inbound Windows ports. Each owner must
complete their own setup and consent.

This repository does not contain user configuration, secrets, runtime state,
private telemetry, generated executables or certificate keys.

## Building / testing

Python 3.14 (development only), pinned project dependencies and Windows.
See packaging/BUILD_AND_RELEASE.md and docs/PUBLIC_RELEASE_GATES.md.
Local tests: python -m unittest discover -s tests -q.

## Security

Remote shell, keyboard and screen access require current owner authorization.
Never forward API keys, grant files or pairing secrets into GitHub issues.
No Windows Defender, UAC or firewall bypass is required.

## License

Source code is licensed under MIT (see LICENSE). Third-party libraries and bundled tools retain their respective license terms.