"""Immutable, build-time trust anchor for the publisher's Ed25519 update signatures.

PRIVATE_QA: accepts test-only public keys supplied externally to disposable QA.
PRODUCTION: must embed the actual vetted publisher PUBLIC keys and never
accept a caller-supplied trust store. This development tree is intentionally
not provisioned for public release. Do not put private keys in this module.
"""
RELEASE_CHANNEL = "PRIVATE_QA"
PUBLISHER_KEYRING = {}
