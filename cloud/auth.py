"""Validate externally issued OIDC access tokens. Never trust an unverified JWT."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient


class Unauthorized(PermissionError):
    pass


@dataclass(frozen=True)
class Principal:
    account: str
    scopes: frozenset[str]

    def requires(self, scope: str) -> None:
        if scope not in self.scopes:
            raise Unauthorized("Insufficient OAuth scope")


def public_https(value: str) -> bool:
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname) and not url.username
                and not url.password and not url.fragment and url.hostname not in
                {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
                and not url.hostname.endswith((".local", ".internal")))
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class Settings:
    issuer: str
    audience: str
    jwks_url: str
    public_origin: str

    def __post_init__(self) -> None:
        if not all(public_https(item) for item in (self.issuer, self.jwks_url, self.public_origin)):
            raise ValueError("Issuer, JWKS and origin must be public HTTPS URLs")
        if not self.audience or len(self.audience) < 8:
            raise ValueError("OAuth resource audience is required")
        if urlsplit(self.public_origin).path not in ("", "/") or urlsplit(self.public_origin).query:
            raise ValueError("Origin must not contain path or query")

    @classmethod
    def from_env(cls):
        return cls(os.environ["UR_OIDC_ISSUER"], os.environ["UR_OIDC_AUDIENCE"],
                   os.environ["UR_OIDC_JWKS_URL"], os.environ["UR_PUBLIC_ORIGIN"])


class OIDC:
    def __init__(self, settings: Settings, *, key_provider=None):
        self.settings = settings
        self.keys = key_provider or PyJWKClient(settings.jwks_url, cache_jwk_set=True,
                                               lifespan=300, timeout=5)

    def principal(self, token: str) -> Principal:
        if not isinstance(token, str) or len(token) < 20 or len(token) > 16384:
            raise Unauthorized("Malformed token")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in {"RS256", "ES256"} or not isinstance(header.get("kid"), str):
                raise Unauthorized("Unsupported token algorithm")
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=[header["alg"]],
                                audience=self.settings.audience,
                                issuer=self.settings.issuer,
                                options={"require": ["iss", "sub", "aud", "exp", "iat"],
                                         "verify_nbf": True}, leeway=10)
            sub = claims.get("sub")
            if not isinstance(sub, str) or not (1 <= len(sub) <= 256):
                raise Unauthorized("Invalid subject")
            # Stable opaque account ID; no e-mail addresses in queue storage.
            scope=claims.get("scope", "")
            if not isinstance(scope, str) or len(scope)>1024:
                raise Unauthorized("Invalid OAuth scopes")
            return Principal(hashlib.sha256((self.settings.issuer + "\0" + sub).encode()).hexdigest(),
                             frozenset(scope.split()))
        except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
            raise Unauthorized("Invalid OAuth access token") from exc


class SupabaseOIDC(OIDC):
    """Validate real Supabase OAuth access tokens without trusting JWT scopes.

    Supabase access tokens use aud='authenticated'. OAuth scopes describe OIDC
    profile data, not desktop privileges. Every signed client_id must be listed
    in the gateway's publisher-controlled capability map. Windows still makes
    a second, fresh authorization decision for every privileged operation.
    """

    ALLOWED_CAPABILITIES = frozenset({
        "ur:read", "ur:devices", "ur:control", "ur:shell", "ur:screen", "ur:input"
    })

    def __init__(self, settings: Settings, *, client_capabilities, key_provider=None):
        if settings.audience != "authenticated" or not settings.issuer.endswith("/auth/v1"):
            raise ValueError("Supabase issuer/audience configuration mismatch")
        if not isinstance(client_capabilities, dict) or not client_capabilities:
            raise ValueError("Explicit OAuth client allowlist is required")
        grants = {}
        for client_id, caps in client_capabilities.items():
            if not isinstance(client_id, str) or not 2 <= len(client_id) <= 256:
                raise ValueError("Invalid allowed OAuth client ID")
            if not isinstance(caps, (frozenset, set, list, tuple)):
                raise ValueError("OAuth client capabilities must be a collection")
            capset = frozenset(caps)
            if (not capset or not capset <= self.ALLOWED_CAPABILITIES or
                    "ur:read" not in capset):
                raise ValueError("Unknown/unsafe OAuth client capabilities")
            grants[client_id] = capset
        self.clients = grants
        super().__init__(settings, key_provider=key_provider)

    def principal(self, token: str) -> Principal:
        if not isinstance(token, str) or not 20 <= len(token) <= 16384:
            raise Unauthorized("Malformed token")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in {"RS256", "ES256"} or not isinstance(header.get("kid"), str):
                raise Unauthorized("Untrusted token signing algorithm")
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=[header["alg"]],
                                audience="authenticated", issuer=self.settings.issuer,
                                options={"require":["iss","sub","aud","exp","iat"],
                                         "verify_nbf":True}, leeway=10)
            sub = claims.get("sub")
            client_id = claims.get("client_id")
            session_id = claims.get("session_id")
            if (not isinstance(sub,str) or not 1 <= len(sub) <= 256 or
                    not isinstance(session_id,str) or not 1 <= len(session_id) <= 256 or
                    claims.get("role") != "authenticated" or
                    claims.get("is_anonymous") is True or
                    not isinstance(client_id,str) or client_id not in self.clients):
                raise Unauthorized("Supabase OAuth client/session is not authorized")
            account = hashlib.sha256((self.settings.issuer + "\0" + sub).encode()).hexdigest()
            return Principal(account, self.clients[client_id])
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise Unauthorized("Invalid Supabase OAuth access token") from exc
