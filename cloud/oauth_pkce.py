"""RFC 7636 browser OAuth for Supabase, with a loopback-only Windows callback.

No OAuth Device Authorization grant: Supabase's OAuth server advertises only
authorization_code + refresh_token. No password, secret or token is logged.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser

import httpx

from .auth import public_https


class PKCEError(RuntimeError):
    pass


@dataclass(frozen=True)
class PKCERequest:
    issuer: str
    client_id: str
    redirect_uri: str
    state: str
    verifier: str
    authorization_url: str


def _validate_issuer(issuer: str) -> str:
    if not isinstance(issuer, str) or not public_https(issuer):
        raise PKCEError("Only a trusted HTTPS issuer is permitted")
    url = urlsplit(issuer)
    if url.query or url.fragment or url.username or url.password:
        raise PKCEError("Invalid OAuth issuer")
    return issuer.rstrip("/")


def _endpoint(value: str, issuer: str) -> str:
    if not isinstance(value, str) or not public_https(value):
        raise PKCEError("Untrusted OAuth endpoint")
    a, b = urlsplit(value), urlsplit(issuer)
    if (a.hostname != b.hostname or a.port != b.port or
            not a.path.startswith(b.path.rstrip("/") + "/") or a.query or a.fragment):
        raise PKCEError("OAuth endpoint does not belong to the issuer")
    return value


def create_request(issuer: str, client_id: str, redirect_uri: str) -> PKCERequest:
    issuer = _validate_issuer(issuer)
    if not isinstance(client_id, str) or not (2 <= len(client_id) <= 128):
        raise PKCEError("Registered OAuth client ID is required")
    parsed = urlsplit(redirect_uri)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or
            parsed.port != 8765 or parsed.path != "/oauth/callback" or
            parsed.query or parsed.fragment):
        raise PKCEError("Only the registered local loopback callback is allowed")
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    state = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")
    endpoint = issuer + "/oauth/authorize"
    parameters = urlencode({
        "response_type": "code", "client_id": client_id,
        "redirect_uri": redirect_uri, "scope": "openid profile",
        "code_challenge": challenge, "code_challenge_method": "S256",
        "state": state,
    })
    return PKCERequest(issuer, client_id, redirect_uri, state, verifier, endpoint+"?"+parameters)


def exchange_code(req: PKCERequest, code: str, http) -> str:
    if not isinstance(code, str) or not 1 <= len(code) <= 2048:
        raise PKCEError("Invalid OAuth authorization code")
    endpoint = req.issuer + "/oauth/token"
    try:
        resp = http.post(endpoint, data={
            "grant_type": "authorization_code", "client_id": req.client_id,
            "code": code, "code_verifier": req.verifier,
            "redirect_uri": req.redirect_uri})
        resp.raise_for_status()
        result = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PKCEError("OAuth token exchange failed") from exc
    token = result.get("access_token") if isinstance(result, dict) else None
    typ = result.get("token_type") if isinstance(result, dict) else None
    if not isinstance(token, str) or len(token) < 20 or not isinstance(typ, str) or typ.lower() != "bearer":
        raise PKCEError("Invalid OAuth bearer token")
    return token


def _loopback_callback(req: PKCERequest, timeout: float = 180, *, open_browser=None):
    """Accept an authorization code over 127.0.0.1; never expose it elsewhere."""
    result = None
    deadline = time.monotonic() + timeout
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal result
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            valid_host = self.headers.get("Host") == "127.0.0.1:8765"
            if (parsed.path == "/oauth/callback" and valid_host and
                    params.get("state") == [req.state]):
                if "code" in params and len(params["code"]) == 1:
                    result = {"state": req.state, "code": params["code"][0]}
                else:
                    result = {"state": req.state, "error": "authorization_denied"}
                self.send_response(200)
                content = b"Authorization response received. Return to Universal Remote."
            else:
                self.send_response(400)
                content = b"Invalid OAuth callback."
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_args):
            # Never persist code/state or browser query params.
            pass

    try:
        server = HTTPServer(("127.0.0.1", 8765), Handler)
    except OSError as exc:
        raise PKCEError("Local OAuth callback port unavailable") from exc
    try:
        server.timeout = 0.5
        # Bind before opening the browser: otherwise fast redirects can race
        # and lose the OAuth code on a closed loopback port.
        if open_browser is not None and open_browser(req.authorization_url) is False:
            raise PKCEError("Could not open the sign-in browser")
        while result is None:
            if time.monotonic() >= deadline:
                raise PKCEError("OAuth consent timed out")
            server.handle_request()
        return result
    finally:
        server.server_close()


def authorize(issuer: str, client_id: str, *, http=None, open_browser=None,
              wait_callback=None) -> str:
    issuer = _validate_issuer(issuer)
    own = http is None
    http = http or httpx.Client(timeout=12, verify=True, follow_redirects=False)
    open_browser = open_browser or webbrowser.open
    try:
        discovery = http.get(issuer + "/.well-known/openid-configuration")
        discovery.raise_for_status()
        metadata = discovery.json()
        if not isinstance(metadata, dict) or metadata.get("issuer") != issuer:
            raise PKCEError("OAuth issuer discovery mismatch")
        supported = metadata.get("grant_types_supported", [])
        if "authorization_code" not in supported:
            raise PKCEError("OAuth issuer does not support authorization_code")
        _endpoint(metadata.get("authorization_endpoint"), issuer)
        _endpoint(metadata.get("token_endpoint"), issuer)
        req = create_request(issuer, client_id,
                             "http://127.0.0.1:8765/oauth/callback")
        if wait_callback is None:
            callback = _loopback_callback(req, open_browser=open_browser)
        else:
            if open_browser(req.authorization_url) is False:
                raise PKCEError("Could not open the sign-in browser")
            callback = wait_callback(req)
        if (not isinstance(callback, dict) or
                callback.get("state") != req.state or
                not isinstance(callback.get("code"), str)):
            raise PKCEError("OAuth consent rejected or mismatched state")
        return exchange_code(req, callback["code"], http)
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        raise PKCEError("Secure browser OAuth sign-in failed") from exc
    finally:
        if own:
            http.close()
